from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from lead_scraper.ocean import OceanSearchPage
from lead_scraper.web import (
    OceanSearchRequest,
    app,
    build_company_filters,
    dashboard,
    execute_ocean_search,
    normalize_revenues,
)


class FakeOceanClient:
    def __init__(self) -> None:
        self.company_kwargs = {}
        self.people_kwargs = {}
        self.reveal_requests = []

    def search_companies(self, **kwargs):
        self.company_kwargs = kwargs
        return OceanSearchPage(
            records=[
                {"domain": "apex.com", "name": "Apex Pools", "score": 0.94},
                {"domain": "blue.com", "name": "Blue Water Pools"},
            ],
            total=200,
            search_after=None,
        )

    def search_people(self, **kwargs):
        self.people_kwargs = kwargs
        return OceanSearchPage(
            records=[
                {
                    "id": "person-1",
                    "name": "Avery Stone",
                    "jobTitle": "Owner",
                    "domain": "apex.com",
                    "linkedinUrl": "https://linkedin.com/in/avery-stone",
                },
                {
                    "id": "person-2",
                    "name": "Morgan Lake",
                    "jobTitle": "President",
                    "domain": "blue.com",
                },
            ],
            total=2,
            search_after=None,
        )

    def reveal_emails(self, person_ids, webhook_url):
        self.reveal_requests.append((person_ids, webhook_url))
        return {"status": "in progress"}


class FakeOceanStore:
    def __init__(self) -> None:
        self.exported = []
        self.person_ids = []

    def recent_domains(self, _months):
        return {"seen.example"}

    def recent_people(self, _months):
        return {"old-person"}

    def new_reveal(self, person_ids):
        self.person_ids = person_ids
        return "secure-callback"

    def wait_for_reveal(self, _token, _timeout, progress=None):
        if progress:
            progress(2, 2)
        return {
            "person-1": {"address": "avery@apex.com", "status": "verified"},
            "person-2": {"address": "morgan@blue.com", "status": "guessed"},
        }

    def record_exports(self, rows):
        self.exported = rows


class OceanDashboardTests(unittest.TestCase):
    def test_dashboard_is_ocean_native(self) -> None:
        response = dashboard()
        html = response.body.decode("utf-8")
        self.assertIn("Ocean lead search", html)
        self.assertIn('placeholder="0-1M, 1-10M, 10-50M"', html)
        self.assertIn("normalizedRevenueValue", html)
        self.assertEqual("no-store, max-age=0", response.headers["cache-control"])
        self.assertIn('id="reference_domains"', html)
        self.assertIn('id="seniorities"', html)
        self.assertIn('id="people_per_company"', html)
        self.assertIn('id="target_count"', html)
        self.assertIn('max="1000"', html)
        self.assertNotIn("Google Maps Connected", html)
        self.assertNotIn("OpenAI Connected", html)

    def test_company_filters_use_ocean_location_and_keyword_shapes(self) -> None:
        request = OceanSearchRequest(
            mode="filters",
            keywords_any="pool builder, pool contractor",
            keywords_none="software",
            industries_any="Construction",
            industries_none="Software, SaaS",
            city="San Antonio",
            state="TX",
            country="us",
            company_sizes="2-10, 11-50",
            revenues="$1M-$10M, 50m",
        )
        filters = build_company_filters(request)
        self.assertEqual(["2-10", "11-50"], filters["companySizes"])
        self.assertEqual(["1-10M", "50-100M"], filters["revenues"])
        self.assertEqual(["Software", "SaaS"], filters["excludeIndustries"])
        self.assertNotIn("excludeIndustries", filters["industries"])
        self.assertEqual(["pool builder", "pool contractor"], filters["keywords"]["anyOf"])
        self.assertEqual("San Antonio", filters["primaryLocations"]["includeCities"][0]["city"])
        self.assertEqual("TX", filters["primaryLocations"]["includeRegions"][0]["abbreviation"])

    def test_revenue_normalization_rejects_unknown_ranges(self) -> None:
        self.assertEqual(["1-10M"], normalize_revenues("1m"))
        self.assertEqual(["1-10M", "10-50M"], normalize_revenues("1, 10"))
        with self.assertRaisesRegex(ValueError, "Revenue range"):
            normalize_revenues("lots of revenue")

    def test_company_filters_reject_same_include_and_exclude_value(self) -> None:
        request = OceanSearchRequest(
            mode="filters",
            industries_any="Marketing",
            industries_none="marketing",
        )
        with self.assertRaisesRegex(ValueError, "same value cannot be in both"):
            build_company_filters(request)

    def test_thousand_email_target_overcollects_company_pool(self) -> None:
        client = FakeOceanClient()
        store = FakeOceanStore()
        request = OceanSearchRequest(
            mode="lookalike",
            reference_domains="ideal.com",
            target_type="emails",
            target_count=1000,
            find_contacts=False,
        )

        execute_ocean_search(request, client=client, store=store)

        self.assertEqual(1539, client.company_kwargs["size"])

    @patch.dict("os.environ", {"OCEAN_REVEAL_WAIT_SECONDS": "1"})
    def test_search_merges_companies_people_and_revealed_emails(self) -> None:
        client = FakeOceanClient()
        store = FakeOceanStore()
        request = OceanSearchRequest(
            mode="lookalike",
            reference_domains="ideal.com",
            target_type="emails",
            target_count=2,
        )
        result = execute_ocean_search(request, client=client, store=store)

        self.assertEqual(2, result["match_count"])
        self.assertEqual(1, result["direct_count"])
        self.assertFalse(result["target_met"])
        self.assertIn("verified_email", result["csv"])
        self.assertIn("avery@apex.com", result["csv"])
        self.assertNotIn("morgan@blue.com", result["csv"])
        self.assertEqual(["ideal.com"], client.company_kwargs["lookalike_domains"])
        self.assertIn("seen.example", client.company_kwargs["exclude_domains"])
        self.assertEqual(
            ["apex.com", "blue.com"],
            client.people_kwargs["companies_filters"]["includeDomains"],
        )
        self.assertIn("old-person", client.people_kwargs["people_filters"]["excludePeopleIds"])
        self.assertTrue(client.reveal_requests[0][1].endswith("/secure-callback"))
        self.assertEqual(1, len(store.exported))
        self.assertEqual("avery@apex.com", store.exported[0]["verified_email"])

    @patch.dict("os.environ", {"OCEAN_REVEAL_WAIT_SECONDS": "1"})
    def test_email_target_keeps_searching_until_verified_target_met(self) -> None:
        class RefillOceanClient(FakeOceanClient):
            def __init__(self) -> None:
                super().__init__()
                self.company_calls = 0
                self.batches = [
                    [{"domain": "apex.com", "name": "Apex Pools"}],
                    [{"domain": "blue.com", "name": "Blue Water Pools"}],
                ]

            def search_companies(self, **kwargs):
                self.company_kwargs = kwargs
                self.company_calls += 1
                records = self.batches.pop(0) if self.batches else []
                return OceanSearchPage(records=records, total=200, search_after=None)

            def search_people(self, **kwargs):
                self.people_kwargs = kwargs
                domain = kwargs["companies_filters"]["includeDomains"][0]
                person = {
                    "id": f"person-{domain}",
                    "name": "Lead Owner",
                    "jobTitle": "Owner",
                    "domain": domain,
                }
                return OceanSearchPage(records=[person], total=1, search_after=None)

        class RefillOceanStore(FakeOceanStore):
            def wait_for_reveal(self, _token, _timeout, progress=None):
                return {
                    "person-apex.com": {"address": "owner@apex.com", "status": "guessed"},
                    "person-blue.com": {"address": "owner@blue.com", "status": "verified"},
                }

        client = RefillOceanClient()
        store = RefillOceanStore()
        request = OceanSearchRequest(
            mode="lookalike",
            reference_domains="ideal.com",
            target_type="emails",
            target_count=1,
        )
        result = execute_ocean_search(request, client=client, store=store)

        self.assertEqual(2, client.company_calls)
        self.assertIn("apex.com", client.company_kwargs["exclude_domains"])
        self.assertEqual(1, result["direct_count"])
        self.assertTrue(result["target_met"])
        self.assertIn("owner@blue.com", result["csv"])
        self.assertNotIn("owner@apex.com", result["csv"])

    def test_background_ocean_job_can_be_polled_and_downloaded(self) -> None:
        client = TestClient(app)
        fake_result = {
            "match_count": 1,
            "direct_count": 1,
            "matches": [],
            "contacts": [],
            "csv": "business_name,verified_email\nApex,a@apex.com\n",
        }
        with patch("lead_scraper.web.execute_locked_ocean_search", return_value=fake_result):
            started = client.post(
                "/api/jobs/ocean",
                json={"mode": "lookalike", "reference_domains": "ideal.com"},
            )
            self.assertEqual(202, started.status_code)
            job_id = started.json()["job_id"]
            for _attempt in range(100):
                job = client.get(f"/api/jobs/{job_id}").json()
                if job["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.01)

        self.assertEqual("completed", job["status"])
        self.assertTrue(job["download_url"])

    def test_ocean_routes_are_registered(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/api/jobs/ocean", paths)
        self.assertIn("/api/ocean/search", paths)
        self.assertIn("/api/ocean/credits", paths)
        self.assertIn("/api/webhooks/ocean/emails/{callback_token}", paths)


if __name__ == "__main__":
    unittest.main()

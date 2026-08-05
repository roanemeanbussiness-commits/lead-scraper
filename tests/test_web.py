from __future__ import annotations

import unittest
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from lead_scraper.lookalike import LookalikeRun
from lead_scraper.web import (
    LookalikeRequest,
    ScrapeRequest,
    app,
    dashboard,
    execute_lookalike_search,
)


class DashboardTests(unittest.TestCase):
    def test_custom_thousand_company_and_email_targets_are_accepted(self) -> None:
        lookalike = LookalikeRequest(
            reference_urls="https://example.com",
            target_type="companies",
            target_count=1000,
            max_candidates=3000,
            max_results=1000,
            updated_within_months=120,
        )
        keyword = ScrapeRequest(target_type="emails", target_count=1000, max_results=1000)

        self.assertEqual(1000, lookalike.target_count)
        self.assertEqual("emails", keyword.target_type)

    def test_email_target_overcollects_company_candidates(self) -> None:
        empty_run = LookalikeRun(
            query_id="query-123456",
            candidates_discovered=0,
            catalog_size=0,
            ranked=[],
            pages_by_domain={},
            discovery_queries=[],
            filtered_count=0,
            usage={},
        )
        request = LookalikeRequest(
            reference_urls="https://ideal.example",
            target_type="emails",
            target_count=100,
            max_candidates=160,
        )
        with (
            patch("lead_scraper.web.parse_public_urls", side_effect=[["https://ideal.example"], []]),
            patch("lead_scraper.web.find_lookalikes", return_value=empty_run) as find,
        ):
            result = execute_lookalike_search(request)

        self.assertEqual(600, find.call_args.kwargs["max_results"])
        self.assertEqual(1200, find.call_args.kwargs["max_candidates"])
        self.assertEqual(100, result["target_count"])

    def test_lookalike_mode_is_the_default_dashboard_experience(self) -> None:
        html = dashboard()
        self.assertIn('id="lookalike-form"', html)
        self.assertIn("Lookalike companies", html)
        self.assertIn('data-view="companies"', html)
        self.assertIn('data-view="contacts"', html)
        self.assertIn('id="progress-panel"', html)
        self.assertIn('id="lookalike_target_count"', html)
        self.assertIn('id="keyword_target_count"', html)
        self.assertIn('id="freshness"', html)
        self.assertIn('max="1000"', html)
        self.assertIn('id="keyword-form" class="filter-form hidden"', html)

    def test_lookalike_api_route_is_registered(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/api/lookalikes", paths)
        self.assertIn("/api/lookalike-feedback", paths)
        self.assertIn("/api/scrape", paths)
        self.assertIn("/api/jobs/lookalikes", paths)
        self.assertIn("/api/jobs/{job_id}", paths)

    def test_background_scrape_job_can_be_polled_to_completion(self) -> None:
        client = TestClient(app)
        fake_result = {
            "discovery_count": 1,
            "direct_count": 1,
            "matches": [],
            "contacts": [],
            "csv": "business_name,verified_email\nApex,a@apex.com\n",
        }
        with patch("lead_scraper.web.execute_scrape", return_value=fake_result):
            started = client.post("/api/jobs/scrape", json={"urls": "https://example.com"})
            self.assertEqual(202, started.status_code)
            job_id = started.json()["job_id"]
            for _attempt in range(100):
                status = client.get(f"/api/jobs/{job_id}").json()
                if status["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.01)

        self.assertEqual("completed", status["status"])
        self.assertTrue(status["download_url"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from lead_scraper.google_places import PlaceLead
from lead_scraper.places_search import (
    STATUS_GENERIC,
    STATUS_PERSONAL,
    STATUS_PERSONAL_MX,
    rank_emails,
)
from lead_scraper.web import OceanSearchRequest, execute_ocean_search


class FakeStore:
    def __init__(self) -> None:
        self.exported = []

    def recent_domains(self, _months):
        return set()

    def recent_people(self, _months):
        return set()

    def record_exports(self, rows):
        self.exported = rows


class RankEmailsTests(unittest.TestCase):
    def test_personal_on_domain_email_wins_over_generic(self) -> None:
        ranked = rank_emails(
            {"info@apex.com", "jane.doe@apex.com"}, "apex.com", verify_mx=False
        )
        self.assertEqual("jane.doe@apex.com", ranked[0][0])
        self.assertEqual(STATUS_PERSONAL, ranked[0][1])
        self.assertEqual(STATUS_GENERIC, ranked[1][1])

    def test_mx_checked_emails_are_marked_deliverable(self) -> None:
        with patch("lead_scraper.places_search.has_mx_record", return_value=True):
            ranked = rank_emails({"jane@apex.com"}, "apex.com", verify_mx=True)
        self.assertEqual(STATUS_PERSONAL_MX, ranked[0][1])

    def test_noise_addresses_are_dropped(self) -> None:
        ranked = rank_emails({"someone@example.com", "a@2x.png"}, "apex.com", verify_mx=False)
        self.assertEqual([], ranked)


class PlacesSearchRouteTests(unittest.TestCase):
    def request(self, **overrides) -> OceanSearchRequest:
        values = {
            "provider": "google_places",
            "places_query": "pool builder",
            "places_location": "San Antonio, TX",
            "target_type": "emails",
            "target_count": 2,
        }
        values.update(overrides)
        return OceanSearchRequest(**values)

    def test_places_search_exports_scraped_emails_without_ocean_credits(self) -> None:
        place = PlaceLead(
            place_id="p1",
            business_name="Apex Pools",
            website="https://apex.com",
            phone="210-555-0100",
            address="San Antonio, TX",
            category="Pool contractor",
        )
        enriched = {
            "business_name": "Apex Pools",
            "domain": "apex.com",
            "website": "https://apex.com",
            "phone": "210-555-0100",
            "location": "San Antonio, TX",
            "industry": "Pool contractor",
            "owner_name": "Jane Doe",
            "owner_role": "Owner",
            "verified_email": "jane@apex.com",
            "email_status": STATUS_PERSONAL_MX,
            "linkedin_profile_url": "",
            "source": "Google Places + site crawl",
        }
        store = FakeStore()
        with patch("lead_scraper.web.google_places_configured", return_value=True), patch(
            "lead_scraper.places_search.search_google_places_queries", return_value=[place]
        ), patch(
            "lead_scraper.places_search.enrich_place", return_value=enriched
        ):
            result = execute_ocean_search(self.request(), store=store)

        self.assertEqual("Google Places", result["provider"])
        self.assertEqual(0, result["estimated_email_credits"])
        self.assertEqual(1, result["direct_count"])
        self.assertIn("jane@apex.com", result["csv"])
        self.assertEqual(1, len(store.exported))
        self.assertEqual(STATUS_PERSONAL_MX, store.exported[0]["email_status"])

    def test_places_search_requires_a_query(self) -> None:
        with patch("lead_scraper.web.google_places_configured", return_value=True):
            with self.assertRaises(HTTPException) as caught:
                execute_ocean_search(self.request(places_query=""), store=FakeStore())
        self.assertEqual(400, caught.exception.status_code)

    def test_places_search_reports_missing_api_key(self) -> None:
        with patch("lead_scraper.web.google_places_configured", return_value=False):
            with self.assertRaises(HTTPException) as caught:
                execute_ocean_search(self.request(), store=FakeStore())
        self.assertIn("GooglePlacesAPI", str(caught.exception.detail))


if __name__ == "__main__":
    unittest.main()

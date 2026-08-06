from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from lead_scraper.google_places import (
    PlaceLead,
    keyword_discovery_queries,
    search_google_places,
    search_google_places_queries,
)


class GooglePlacesTests(unittest.TestCase):
    def test_large_keyword_target_expands_trade_queries(self) -> None:
        queries = keyword_discovery_queries("pool constrution", 1000)

        self.assertGreaterEqual(len(queries), 20)
        self.assertIn("pool builder", queries)
        self.assertIn("swimming pool contractor", queries)

    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=True)
    @patch("lead_scraper.google_places.httpx.Client")
    def test_follows_page_tokens_and_returns_place_ids(self, client_class: MagicMock) -> None:
        first = MagicMock()
        first.status_code = 200
        first.json.return_value = {
            "places": [
                {
                    "id": "places/one",
                    "displayName": {"text": "One Roofing"},
                    "websiteUri": "https://one.example",
                }
            ],
            "nextPageToken": "next-token",
        }
        second = MagicMock()
        second.status_code = 200
        second.json.return_value = {
            "places": [
                {
                    "id": "places/two",
                    "displayName": {"text": "Two Roofing"},
                    "websiteUri": "https://two.example",
                }
            ]
        }
        client = client_class.return_value.__enter__.return_value
        client.post.side_effect = [first, second]

        leads = search_google_places("roofer", "San Antonio, TX", max_results=2)

        self.assertEqual(["places/one", "places/two"], [lead.place_id for lead in leads])
        self.assertEqual("next-token", client.post.call_args_list[1].kwargs["json"]["pageToken"])
        self.assertEqual(2, client.post.call_count)

    @patch("lead_scraper.google_places.search_google_places")
    def test_multi_query_search_deduplicates_shared_domains(self, search: MagicMock) -> None:
        search.side_effect = [
            [PlaceLead("places/one", "One", "https://one.example")],
            [
                PlaceLead("places/one", "One duplicate", "https://one.example"),
                PlaceLead("places/two", "Two", "https://two.example"),
            ],
        ]

        leads = search_google_places_queries(["roof repair", "commercial roofer"], "San Antonio, TX", 10)

        self.assertEqual(["places/one", "places/two"], [lead.place_id for lead in leads])



class PlacesResilienceTests(unittest.TestCase):
    def test_transient_5xx_is_retried_then_skipped(self) -> None:
        from lead_scraper.google_places import request_places_page

        calls = []

        class FlakyClient:
            def post(self, *_args, **_kwargs):
                calls.append(1)
                return httpx.Response(503, request=httpx.Request("POST", "https://x"))

        with patch("lead_scraper.google_places.time.sleep"):
            result = request_places_page(FlakyClient(), {}, {})

        self.assertIsNone(result)
        self.assertEqual(4, len(calls))

    def test_client_error_is_raised_with_detail(self) -> None:
        from lead_scraper.google_places import GooglePlacesError, request_places_page

        class DeniedClient:
            def post(self, *_args, **_kwargs):
                return httpx.Response(
                    403,
                    json={"error": {"message": "API key not authorized"}},
                    request=httpx.Request("POST", "https://x"),
                )

        with self.assertRaisesRegex(GooglePlacesError, "API key not authorized"):
            request_places_page(DeniedClient(), {}, {})

    def test_one_failing_query_does_not_end_the_sweep(self) -> None:
        from lead_scraper.google_places import PlaceLead, search_google_places_queries

        good = PlaceLead(place_id="p1", business_name="Apex", website="https://apex.com")

        def fake_search(query, _location, max_results=20):
            if query == "bad":
                raise httpx.ConnectError("boom")
            return [good]

        with patch("lead_scraper.google_places.search_google_places", side_effect=fake_search):
            found = search_google_places_queries(["bad", "good"], "San Antonio, TX", 10)

        self.assertEqual(1, len(found))

    def test_total_failure_raises(self) -> None:
        from lead_scraper.google_places import GooglePlacesError, search_google_places_queries

        with patch(
            "lead_scraper.google_places.search_google_places",
            side_effect=httpx.ConnectError("boom"),
        ):
            with self.assertRaisesRegex(GooglePlacesError, "unavailable"):
                search_google_places_queries(["a", "b"], "San Antonio, TX", 10)

if __name__ == "__main__":
    unittest.main()

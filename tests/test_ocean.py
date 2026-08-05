from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from lead_scraper.ocean import OceanClient, OceanLeadStore, ocean_api_token


class OceanClientTests(unittest.TestCase):
    def test_fly_secret_alias_is_supported(self) -> None:
        with patch.dict("os.environ", {"Oceanio": "test-token"}, clear=True):
            self.assertEqual("test-token", ocean_api_token())

    def test_company_search_sends_token_and_normalizes_nested_company(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["token"] = request.headers.get("x-api-token")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "companies": [
                        {"company": {"domain": "apex.com", "name": "Apex"}, "score": 0.9}
                    ],
                    "total": 1,
                    "searchAfter": ["apex.com"],
                },
            )

        client = OceanClient(token="secret", transport=httpx.MockTransport(handler))
        page = client.search_companies(
            size=100,
            companies_filters={"companySizes": ["2-10"]},
            lookalike_domains=["ideal.com"],
            exclude_domains=["seen.com"],
        )

        self.assertEqual("secret", captured["token"])
        self.assertEqual(100, captured["payload"]["size"])
        self.assertEqual(["ideal.com"], captured["payload"]["lookalikeDomains"])
        self.assertEqual("apex.com", page.records[0]["domain"])
        self.assertEqual(0.9, page.records[0]["score"])

    def test_reveal_store_accepts_results_and_tracks_recent_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OceanLeadStore(Path(tmp) / "ocean.db")
            token = store.new_reveal(["p1", "p2"])
            saved = store.save_reveal(
                token,
                {
                    "results": [
                        {"personId": "p1", "email": {"address": "a@apex.com", "status": "verified"}},
                        {"personId": "p2", "email": {"address": None, "status": "notFound"}},
                    ]
                },
            )
            expected, results = store.reveal_results(token)
            store.record_exports(
                [{"domain": "apex.com", "person_id": "p1", "verified_email": "a@apex.com"}]
            )

            self.assertEqual(2, saved)
            self.assertEqual(2, expected)
            self.assertEqual("verified", results["p1"]["status"])
            self.assertEqual({"apex.com"}, store.recent_domains(12))
            self.assertEqual({"p1"}, store.recent_people(12))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from lead_scraper.google_places import search_google_places


class GooglePlacesTests(unittest.TestCase):
    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=True)
    @patch("lead_scraper.google_places.httpx.Client")
    def test_follows_page_tokens_and_returns_place_ids(self, client_class: MagicMock) -> None:
        first = MagicMock()
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
        first.raise_for_status.assert_called_once()
        second.raise_for_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from lead_scraper.ai_enrichment import get_openai_api_key, openai_configured
from lead_scraper.google_places import get_google_maps_api_key, google_places_configured


class ConfigAliasTests(unittest.TestCase):
    def test_google_places_legacy_secret_alias_is_supported(self) -> None:
        with patch.dict(os.environ, {"GooglePlacesAPI": "maps-key"}, clear=True):
            self.assertEqual("maps-key", get_google_maps_api_key())
            self.assertTrue(google_places_configured())

    def test_openai_legacy_secret_alias_is_supported(self) -> None:
        with patch.dict(os.environ, {"OpenAI_api": "openai-key"}, clear=True):
            self.assertEqual("openai-key", get_openai_api_key())
            self.assertTrue(openai_configured())


if __name__ == "__main__":
    unittest.main()


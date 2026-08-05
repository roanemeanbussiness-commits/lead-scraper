from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lead_scraper.history import LeadHistory
from lead_scraper.models import Lead


class LeadHistoryTests(unittest.TestCase):
    def test_sqlite_history_persists_email_domain_and_place_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lead_history.db"
            history = LeadHistory.load(path)
            history.append(
                [
                    Lead(
                        email="owner@example.com",
                        domain="example.com",
                        source_url="https://example.com/contact",
                        place_id="places/test-123",
                    )
                ]
            )

            reloaded = LeadHistory.load(path)

            self.assertTrue(reloaded.has_seen("owner@example.com", "new.example", "email"))
            self.assertTrue(reloaded.has_seen("new@other.example", "example.com", "domain"))
            self.assertTrue(reloaded.has_seen("", "unseen.example", "email", "places/test-123"))


if __name__ == "__main__":
    unittest.main()

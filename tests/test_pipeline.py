from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lead_scraper.crawler import CrawledPage
from lead_scraper.pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_sitewide_owner_evidence_is_attached_to_contact_email(self) -> None:
        pages = [
            CrawledPage(
                "https://roofco.com/about",
                "<p>Owned and operated by Maria Garcia since 2012.</p>",
            ),
            CrawledPage(
                "https://roofco.com/contact",
                '<a href="mailto:maria@roofco.com">Email Maria</a>',
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seeds = root / "seeds.csv"
            seeds.write_text(
                "url,place_id,business_name,city,state,category\n"
                "https://roofco.com,places/roofco,Roof Co,San Antonio,TX,Roofing\n",
                encoding="utf-8",
            )
            output = root / "leads.csv"

            with (
                patch("lead_scraper.pipeline.validate_public_url", side_effect=lambda value: value),
                patch("lead_scraper.pipeline.crawl_site", return_value=pages),
                patch("lead_scraper.pipeline.openai_configured", return_value=False),
            ):
                count = run_pipeline(
                    seeds_path=seeds,
                    out_path=output,
                    history_path=root / "history.db",
                    dedupe="email",
                    max_pages=8,
                    timeout=1,
                )

            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(1, count)
            self.assertEqual("Maria Garcia", rows[0]["possible_owner"])
            self.assertEqual("https://roofco.com/about", rows[0]["owner_source_url"])
            self.assertEqual("places/roofco", rows[0]["place_id"])


if __name__ == "__main__":
    unittest.main()

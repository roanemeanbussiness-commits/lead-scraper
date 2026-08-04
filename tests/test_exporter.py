from __future__ import annotations

import unittest

from lead_scraper.exporter import clean_direct_leads
from lead_scraper.extract import is_generic_email


class ExporterTests(unittest.TestCase):
    def test_filters_generic_emails_and_formats_campaign_fields(self) -> None:
        leads = [
            {
                "business_name": "apex landscaping",
                "possible_owner": "marcus vance",
                "email": "marcus@apexlandscaping.com",
                "phone": "704-555-0199",
                "source_url": "https://apexlandscaping.com",
                "city": "Charlotte",
                "state": "NC",
                "category": "landscaping",
            },
            {"business_name": "green thumb", "email": "info@greenthumb.com"},
            {"business_name": "summit lawn", "email": "sales-us@summitlawn.com"},
            {"business_name": "duplicate", "email": "marcus@apexlandscaping.com"},
        ]

        cleaned, dropped = clean_direct_leads(leads)

        self.assertEqual(1, len(cleaned))
        self.assertEqual(3, dropped)
        self.assertEqual("Apex Landscaping", cleaned[0]["business_name"])
        self.assertEqual("Marcus", cleaned[0]["first_name"])
        self.assertEqual("Charlotte, NC", cleaned[0]["location"])
        self.assertEqual("marcus@apexlandscaping.com", cleaned[0]["verified_email"])

    def test_generic_email_detection_handles_prefix_variants(self) -> None:
        self.assertFalse(is_generic_email("owner@example.com"))
        self.assertTrue(is_generic_email("info@example.com"))
        self.assertTrue(is_generic_email("contact-us@example.com"))
        self.assertTrue(is_generic_email("sales.us@example.com"))


if __name__ == "__main__":
    unittest.main()


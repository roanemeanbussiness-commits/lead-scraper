from __future__ import annotations

import unittest

from lead_scraper.extract import extract_possible_owners


class OwnerExtractionTests(unittest.TestCase):
    def test_extracts_owner_phrases_from_visible_text(self) -> None:
        html = """
        <main>
          <p>Owned and operated by Maria Garcia since 2012.</p>
          <p>John Smith, Owner</p>
          <p>Founded by Luis Martinez.</p>
        </main>
        """

        owners = extract_possible_owners(html)

        self.assertIn("Maria Garcia", owners)
        self.assertIn("John Smith", owners)
        self.assertIn("Luis Martinez", owners)

    def test_extracts_founder_from_json_ld(self) -> None:
        html = """
        <script type="application/ld+json">
        {
          "@type": "LocalBusiness",
          "name": "Apex Roofing",
          "founder": {"@type": "Person", "name": "Sarah Miller"}
        }
        </script>
        """

        self.assertIn("Sarah Miller", extract_possible_owners(html))

    def test_rejects_obvious_non_people(self) -> None:
        html = "<p>Owner: The Business Team</p><p>Our Services, Owner</p>"

        self.assertEqual(set(), extract_possible_owners(html))


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import unittest

from lead_scraper.extract import extract_emails, extract_owner_candidates, extract_possible_owners


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

    def test_schema_employee_is_not_mislabeled_as_owner(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type":"Organization","employee":{"@type":"Person","name":"Taylor Worker"}}
        </script>
        """

        self.assertEqual(set(), extract_possible_owners(html))

    def test_owner_candidate_includes_evidence_and_source(self) -> None:
        html = "<p>Owned and operated by Maria Garcia since 2012.</p>"

        candidate = extract_owner_candidates(html, "https://example.com/about")[0]

        self.assertEqual("Maria Garcia", candidate.name)
        self.assertEqual("https://example.com/about", candidate.source_url)
        self.assertGreaterEqual(candidate.confidence, 90)
        self.assertIn("Owned and operated by Maria Garcia", candidate.evidence)

    def test_extracts_obfuscated_and_cloudflare_emails(self) -> None:
        key = 0x12
        email = "owner@roofco.com"
        encoded = f"{key:02x}" + "".join(f"{ord(char) ^ key:02x}" for char in email)
        html = f"""
        <p>salesperson [at] roofco [dot] com</p>
        <span data-cfemail="{encoded}"></span>
        """

        emails = extract_emails(html)

        self.assertIn("owner@roofco.com", emails)
        self.assertIn("salesperson@roofco.com", emails)


if __name__ == "__main__":
    unittest.main()

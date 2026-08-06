from __future__ import annotations

import unittest

from lead_scraper.extract import (
    extract_emails,
    extract_linkedin_profile_urls,
    extract_owner_candidates,
    extract_possible_owners,
)


class OwnerExtractionTests(unittest.TestCase):
    def test_extracts_personal_linkedin_links_published_by_company_site(self) -> None:
        html = (
            '<a href="https://www.linkedin.com/in/maria-garcia/">Maria</a>'
            '<a href="https://www.linkedin.com/company/roof-co/">Company</a>'
        )

        self.assertEqual(
            ["https://www.linkedin.com/in/maria-garcia"],
            extract_linkedin_profile_urls(html),
        )

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

    def test_extracts_decision_maker_job_title_from_schema_person(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type":"Person","name":"Daniel Ortiz","jobTitle":"General Manager"}
        </script>
        """

        candidates = extract_owner_candidates(html, "https://example.com/team")

        self.assertEqual("Daniel Ortiz", candidates[0].name)
        self.assertEqual("General Manager", candidates[0].role)

    def test_rejects_obvious_non_people(self) -> None:
        html = (
            "<p>Owner: The Business Team</p><p>Our Services, Owner</p>"
            "<p>Owner: stays involved in</p><p>President: ship if you</p>"
            "<p>Founder: in San Antonio</p><p>Owner: of Custom Pools</p>"
        )

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


class JunkEmailFilterTests(unittest.TestCase):
    """Regression coverage for scraped junk that reached ocean_leads_2.csv
    labelled as best-tier verified addresses: Sentry tracking pixels,
    website-builder placeholder text, and a corrupted JS-escape leak."""

    def test_sentry_tracking_hash_is_rejected(self) -> None:
        from lead_scraper.extract import is_business_email

        self.assertFalse(is_business_email("8c4075d5481d476e945486754f783364@sentry.io"))
        self.assertFalse(
            is_business_email("18d2f96d279149989b95faf0a4b41882@sentry-next.wixpress.com")
        )

    def test_website_builder_placeholders_are_rejected(self) -> None:
        from lead_scraper.extract import is_business_email

        for email in ("filler@godaddy.com", "mymail@mailservice.com", "user@domain.com"):
            self.assertFalse(is_business_email(email), email)

    def test_corrupted_js_escape_is_rejected(self) -> None:
        from lead_scraper.extract import is_business_email

        self.assertFalse(is_business_email("u002fxtremepaintconway@gmail.com"))

    def test_real_business_addresses_still_pass(self) -> None:
        from lead_scraper.extract import is_business_email

        for email in (
            "ashburnautocare@gmail.com",
            "info@djsautorepair.com",
            "johnathan@autoclinicjonesboro.com",
            "kevin@sherwoodtirepros.com",
        ):
            self.assertTrue(is_business_email(email), email)

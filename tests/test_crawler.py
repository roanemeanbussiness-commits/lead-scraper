from __future__ import annotations

import unittest

from lead_scraper.crawler import UnsafeURL, validate_public_url


class CrawlerSafetyTests(unittest.TestCase):
    def test_rejects_private_and_local_urls(self) -> None:
        for url in (
            "http://127.0.0.1/admin",
            "http://10.0.0.4/metadata",
            "http://169.254.169.254/latest/meta-data",
            "http://localhost:8080",
        ):
            with self.subTest(url=url), self.assertRaises(UnsafeURL):
                validate_public_url(url)

    def test_rejects_credentials_and_nonstandard_ports(self) -> None:
        with self.assertRaises(UnsafeURL):
            validate_public_url("https://user:password@example.com")
        with self.assertRaises(UnsafeURL):
            validate_public_url("https://8.8.8.8:8443")


if __name__ == "__main__":
    unittest.main()

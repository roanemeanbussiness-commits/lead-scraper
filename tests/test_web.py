from __future__ import annotations

import unittest
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from lead_scraper.web import app, dashboard


class DashboardTests(unittest.TestCase):
    def test_lookalike_mode_is_the_default_dashboard_experience(self) -> None:
        html = dashboard()
        self.assertIn('id="lookalike-form"', html)
        self.assertIn("Lookalike companies", html)
        self.assertIn('data-view="companies"', html)
        self.assertIn('data-view="contacts"', html)
        self.assertIn('id="progress-panel"', html)
        self.assertIn('id="keyword-form" class="filter-form hidden"', html)

    def test_lookalike_api_route_is_registered(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/api/lookalikes", paths)
        self.assertIn("/api/lookalike-feedback", paths)
        self.assertIn("/api/scrape", paths)
        self.assertIn("/api/jobs/lookalikes", paths)
        self.assertIn("/api/jobs/{job_id}", paths)

    def test_background_scrape_job_can_be_polled_to_completion(self) -> None:
        client = TestClient(app)
        fake_result = {
            "discovery_count": 1,
            "direct_count": 1,
            "matches": [],
            "contacts": [],
            "csv": "business_name,verified_email\nApex,a@apex.com\n",
        }
        with patch("lead_scraper.web.execute_scrape", return_value=fake_result):
            started = client.post("/api/jobs/scrape", json={"urls": "https://example.com"})
            self.assertEqual(202, started.status_code)
            job_id = started.json()["job_id"]
            for _attempt in range(100):
                status = client.get(f"/api/jobs/{job_id}").json()
                if status["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.01)

        self.assertEqual("completed", status["status"])
        self.assertTrue(status["download_url"])


if __name__ == "__main__":
    unittest.main()

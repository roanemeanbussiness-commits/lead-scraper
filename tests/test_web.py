from __future__ import annotations

import unittest

from lead_scraper.web import app, dashboard


class DashboardTests(unittest.TestCase):
    def test_lookalike_mode_is_the_default_dashboard_experience(self) -> None:
        html = dashboard()
        self.assertIn('id="lookalike-form"', html)
        self.assertIn("Company lookalikes", html)
        self.assertIn("Preview matches", html)
        self.assertIn('id="keyword-form" class="filter-form hidden"', html)

    def test_lookalike_api_route_is_registered(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/api/lookalikes", paths)
        self.assertIn("/api/lookalike-feedback", paths)
        self.assertIn("/api/scrape", paths)


if __name__ == "__main__":
    unittest.main()

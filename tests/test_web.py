from __future__ import annotations

import unittest

from lead_scraper.web import app, dashboard


class DashboardTests(unittest.TestCase):
    def test_lookalike_mode_is_the_default_dashboard_experience(self) -> None:
        html = dashboard()
        self.assertIn('id="lookalike-form"', html)
        self.assertIn("Ideal company websites", html)
        self.assertIn("Find Similar Companies", html)
        self.assertIn('id="scrape-form" class="mode-panel hidden"', html)

    def test_lookalike_api_route_is_registered(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/api/lookalikes", paths)
        self.assertIn("/api/scrape", paths)


if __name__ == "__main__":
    unittest.main()

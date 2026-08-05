from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lead_scraper.company_catalog import CatalogCompany, CompanyCatalog
from lead_scraper.company_profile import CompanyProfile, merge_profiles
from lead_scraper.crawler import CrawledPage
from lead_scraper.google_places import PlaceLead
from lead_scraper.lookalike import cosine_similarity, find_lookalikes, score_company
from lead_scraper.models import Seed


class LookalikeScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ideal = CompanyProfile(
            industry="plumbing contractor",
            services=["water heater repair", "drain cleaning"],
            customer_types=["residential homeowners"],
            business_model=["local b2c service"],
            specialties=["emergency plumbing"],
            keywords=["plumber", "water heater", "drain"],
        )
        self.candidate_profile = CompanyProfile(
            industry="plumbing contractor",
            services=["water heater installation", "drain cleaning"],
            customer_types=["residential homeowners"],
            business_model=["local b2c service"],
            specialties=["emergency plumbing"],
            keywords=["plumber", "water heater", "drain"],
        )
        self.company = CatalogCompany(
            domain="candidate.example",
            url="https://candidate.example",
            place_id="places/candidate",
            business_name="Candidate Plumbing",
            phone="",
            address="",
            city="San Antonio",
            state="TX",
            category="Plumber",
            profile=self.candidate_profile,
            embedding=[1.0, 0.0, 0.0],
            embedding_model="test",
        )

    def test_cosine_similarity_handles_orthogonal_vectors(self) -> None:
        self.assertAlmostEqual(1.0, cosine_similarity([1.0, 0.0], [1.0, 0.0]))
        self.assertAlmostEqual(0.0, cosine_similarity([1.0, 0.0], [0.0, 1.0]))

    def test_negative_example_reduces_final_score(self) -> None:
        positive_only = score_company(self.company, [self.ideal], [[1.0, 0.0, 0.0]], [], [])
        with_negative = score_company(
            self.company,
            [self.ideal],
            [[1.0, 0.0, 0.0]],
            [self.candidate_profile],
            [[1.0, 0.0, 0.0]],
        )
        self.assertGreater(positive_only.score, with_negative.score)
        self.assertGreater(with_negative.negative_penalty, 0)

    def test_merge_profiles_keeps_shared_icp_signals(self) -> None:
        merged = merge_profiles([self.ideal, self.candidate_profile])
        self.assertIn("drain cleaning", merged.services)
        self.assertIn("residential homeowners", merged.customer_types)


class CompanyCatalogTests(unittest.TestCase):
    def test_profile_and_float32_embedding_persist(self) -> None:
        profile = CompanyProfile(industry="roofing", services=["roof repair"])
        company = CatalogCompany(
            domain="roofer.example",
            url="https://roofer.example",
            place_id="places/roofer",
            business_name="Roofer",
            phone="210-555-0100",
            address="San Antonio, TX",
            city="San Antonio",
            state="TX",
            category="Roofing contractor",
            profile=profile,
            embedding=[0.125, 0.5, -0.25],
            embedding_model="test-model",
        )
        with tempfile.TemporaryDirectory() as tmp:
            catalog = CompanyCatalog(Path(tmp) / "catalog.db")
            catalog.upsert(company)
            loaded = catalog.get("roofer.example")

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual("roofing", loaded.profile.industry)
        self.assertEqual("places/roofer", loaded.place_id)
        self.assertAlmostEqual(0.125, loaded.embedding[0], places=5)


class LookalikeFlowTests(unittest.TestCase):
    def test_new_candidate_is_profiled_saved_and_ranked(self) -> None:
        ideal = CompanyProfile(
            industry="roofing contractor",
            services=["roof repair"],
            customer_types=["homeowners"],
            business_model=["local b2c service"],
            discovery_queries=["residential roof repair"],
        )
        candidate = CompanyProfile(
            industry="roofing contractor",
            services=["roof repair"],
            customer_types=["homeowners"],
            business_model=["local b2c service"],
        )
        seed = Seed(
            url="https://candidate.example",
            place_id="places/candidate",
            business_name="Candidate Roofing",
            city="San Antonio",
            state="TX",
            category="Roofing contractor",
        )
        pages = [CrawledPage("https://candidate.example", "<p>Roof repair</p>")]
        place = PlaceLead("places/candidate", "Candidate Roofing", "https://candidate.example")

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("lead_scraper.lookalike.get_openai_api_key", return_value="test-key"),
                patch(
                    "lead_scraper.lookalike.build_reference_set",
                    return_value=([ideal], [[1.0, 0.0]], {"ideal.example"}),
                ),
                patch("lead_scraper.lookalike.search_google_places_queries", return_value=[place]),
                patch("lead_scraper.lookalike.profile_candidate", return_value=(seed, candidate, pages)),
                patch("lead_scraper.lookalike.embed_texts", return_value=[[1.0, 0.0]]),
                patch("lead_scraper.lookalike.rerank_top", side_effect=lambda ranked, *_args: ranked),
            ):
                run = find_lookalikes(
                    reference_urls=["https://ideal.example"],
                    negative_urls=[],
                    location="San Antonio, TX",
                    city="San Antonio",
                    state="TX",
                    max_candidates=10,
                    max_results=5,
                    max_pages=4,
                    min_score=0,
                    catalog_path=Path(tmp) / "catalog.db",
                )

        self.assertEqual(1, len(run.ranked))
        self.assertEqual("candidate.example", run.ranked[0].company.domain)
        self.assertGreater(run.ranked[0].score, 80)
        self.assertIn("candidate.example", run.pages_by_domain)


if __name__ == "__main__":
    unittest.main()

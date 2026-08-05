from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import httpx

from .ai_enrichment import get_openai_api_key
from .company_catalog import CatalogCompany, CompanyCatalog
from .company_profile import CompanyProfile, merge_profiles, profile_company
from .crawler import CrawledPage, crawl_site, domain_of, validate_public_url
from .google_places import PlaceLead, search_google_places_queries
from .models import Seed


@dataclass(frozen=True)
class RankedCompany:
    company: CatalogCompany
    score: float
    semantic_score: float
    profile_score: float
    lexical_score: float
    negative_penalty: float
    reasons: list[str]


@dataclass(frozen=True)
class LookalikeFilters:
    matching_mode: str = "precise"
    industries_any: tuple[str, ...] = ()
    industries_none: tuple[str, ...] = ()
    keywords_any: tuple[str, ...] = ()
    keywords_all: tuple[str, ...] = ()
    keywords_none: tuple[str, ...] = ()
    technologies_any: tuple[str, ...] = ()
    technologies_all: tuple[str, ...] = ()
    technologies_none: tuple[str, ...] = ()
    tags_any: tuple[str, ...] = ()
    tags_none: tuple[str, ...] = ()
    require_hiring: bool = False
    ecommerce_only: bool = False
    updated_within_months: int = 12


@dataclass(frozen=True)
class LookalikeRun:
    query_id: str
    candidates_discovered: int
    catalog_size: int
    ranked: list[RankedCompany]
    pages_by_domain: dict[str, list[CrawledPage]]
    discovery_queries: list[str]
    filtered_count: int
    usage: dict[str, int | float]


def find_lookalikes(
    reference_urls: list[str],
    negative_urls: list[str],
    location: str,
    city: str,
    state: str,
    max_candidates: int,
    max_results: int,
    max_pages: int,
    min_score: float,
    catalog_path: Path,
    filters: LookalikeFilters | None = None,
    progress: Callable[[int, str, str], None] | None = None,
) -> LookalikeRun:
    if not get_openai_api_key():
        raise ValueError("OPENAI_API_KEY is required for like-for-like company embeddings.")
    if not reference_urls:
        raise ValueError("Add at least one ideal company website.")

    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    filters = filters or LookalikeFilters()
    if filters.matching_mode not in {"precise", "broad"}:
        raise ValueError("matching_mode must be precise or broad")
    catalog = CompanyCatalog(catalog_path)
    pages_by_domain: dict[str, list[CrawledPage]] = {}
    report = progress or (lambda _value, _stage, _message: None)

    report(6, "Ideal profile", "Reading and profiling the reference companies")
    positive_profiles, positive_embeddings, positive_domains, positive_cached = build_reference_set(
        reference_urls, max_pages=max_pages, model=model, pages_by_domain=pages_by_domain, catalog=catalog
    )
    negative_profiles, negative_embeddings, negative_domains, negative_cached = build_reference_set(
        negative_urls, max_pages=max_pages, model=model, pages_by_domain=pages_by_domain, catalog=catalog
    ) if negative_urls else ([], [], set(), 0)

    query_id = hashlib.sha256(
        ("|".join(sorted(positive_domains)) + "::" + "|".join(sorted(negative_domains))).encode("utf-8")
    ).hexdigest()[:16]

    combined = merge_profiles(positive_profiles)
    queries = discovery_queries(combined)
    report(16, "Discovery", f"Running {len(queries)} semantic Google Places searches")
    places = search_google_places_queries(queries, location, max_results=max_candidates)
    report(26, "Discovery", f"Found {len(places)} unique company candidates")
    excluded = positive_domains | negative_domains

    existing = {company.domain: company for company in catalog.list(state=state)}
    candidate_seeds: list[Seed] = []
    for place in places:
        domain = domain_of(place.website)
        if not domain or domain in excluded or domain in existing:
            continue
        candidate_seeds.append(seed_from_place(place, city=city, state=state))

    new_companies: list[tuple[Seed, CompanyProfile]] = []
    worker_count = min(int(os.getenv("LOOKALIKE_PROFILE_WORKERS", "8")), len(candidate_seeds))
    if worker_count:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(profile_candidate, seed, max_pages): seed
                for seed in candidate_seeds
            }
            completed = 0
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                if result is None:
                    continue
                seed, profile = result
                new_companies.append((seed, profile))
                report(
                    26 + round(34 * completed / max(1, len(candidate_seeds))),
                    "Company profiles",
                    f"Profiled {completed} of {len(candidate_seeds)} new websites",
                )

    if new_companies:
        report(62, "Company profiles", "Embedding the candidate company fingerprints")
        embeddings = embed_texts([profile.canonical_text() for _seed, profile in new_companies], model)
        for (seed, profile), embedding in zip(new_companies, embeddings):
            company = catalog_company(seed, profile, embedding, model)
            catalog.upsert(company)
            existing[company.domain] = company

    all_candidates = [company for domain, company in existing.items() if domain not in excluded and company.embedding]
    candidates = [company for company in all_candidates if company_matches_filters(company, filters)]
    report(70, "Ranking", f"Scoring {len(candidates)} companies against the ideal profile")
    ranked = [
        score_company(
            company, positive_profiles, positive_embeddings, negative_profiles, negative_embeddings,
            matching_mode=filters.matching_mode,
        )
        for company in candidates
    ]
    feedback = catalog.feedback_for_query(query_id)
    ranked = [apply_feedback(item, feedback.get(item.company.domain, "")) for item in ranked]
    ranked.sort(key=lambda item: (-item.score, item.company.business_name, item.company.domain))
    reranked = rerank_top(
        ranked[: min(60, max(15, max_results * 2))],
        positive_profiles,
        negative_profiles,
        filters.matching_mode,
    )
    rerank_by_domain = {item.company.domain: item for item in reranked}
    ranked = [rerank_by_domain.get(item.company.domain, item) for item in ranked]
    ranked.sort(key=lambda item: (-item.score, item.company.business_name, item.company.domain))
    ranked = [item for item in ranked if item.score >= min_score][:max_results]
    report(78, "Ranking", f"Selected {len(ranked)} best-fit companies for contact enrichment")

    return LookalikeRun(
        query_id=query_id,
        candidates_discovered=len(places),
        catalog_size=catalog.count(),
        ranked=ranked,
        pages_by_domain=pages_by_domain,
        discovery_queries=queries,
        filtered_count=len(all_candidates) - len(candidates),
        usage={
            "google_queries": len(queries),
            "fresh_candidates": len(places),
            "websites_profiled": len(new_companies) + len(reference_urls) + len(negative_urls) - positive_cached - negative_cached,
            "reference_cache_hits": positive_cached + negative_cached,
            "embedding_batches": 1 + (1 if new_companies else 0),
            "estimated_openai_calls": (
                (len(new_companies) if candidate_ai_enabled() else 0)
                + len(reference_urls) + len(negative_urls) - positive_cached - negative_cached + 2
            ),
        },
    )


def build_reference_set(
    urls: list[str], max_pages: int, model: str, pages_by_domain: dict[str, list[CrawledPage]],
    catalog: CompanyCatalog,
) -> tuple[list[CompanyProfile], list[list[float]], set[str], int]:
    profiles: list[CompanyProfile] = []
    embeddings: list[list[float]] = []
    domains: set[str] = set()
    cache_hits = 0
    for url in urls:
        valid = validate_public_url(url)
        domain = domain_of(valid)
        if domain in domains:
            continue
        cached = catalog.get(domain)
        if cached and cached.embedding_model == model and is_fresh(cached.updated_at, months=6):
            domains.add(domain)
            profiles.append(cached.profile)
            embeddings.append(cached.embedding)
            cache_hits += 1
            continue
        pages = crawl_site(valid, max_pages=max_pages, timeout=12.0)
        if not pages:
            raise ValueError(f"Could not read the reference website: {domain}")
        domains.add(domain)
        pages_by_domain[domain] = pages
        seed = Seed(url=valid, business_name=domain)
        profile = profile_company(seed, pages)
        embedding = embed_texts([profile.canonical_text()], model)[0]
        profiles.append(profile)
        embeddings.append(embedding)
        catalog.upsert(catalog_company(seed, profile, embedding, model))
    return profiles, embeddings, domains, cache_hits


def profile_candidate(seed: Seed, max_pages: int) -> tuple[Seed, CompanyProfile] | None:
    try:
        pages = crawl_site(str(seed.url), max_pages=max_pages, timeout=12.0)
        if not pages:
            return None
        return seed, profile_company(seed, pages, use_ai=candidate_ai_enabled())
    except Exception:
        return None


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    if not texts:
        return []
    api_key = get_openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for embeddings.")
    response = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"), "input": texts},
        timeout=60.0,
    )
    response.raise_for_status()
    data = sorted(response.json()["data"], key=lambda item: item["index"])
    return [[float(value) for value in item["embedding"]] for item in data]


def score_company(
    company: CatalogCompany,
    positive_profiles: list[CompanyProfile],
    positive_embeddings: list[list[float]],
    negative_profiles: list[CompanyProfile],
    negative_embeddings: list[list[float]],
    matching_mode: str = "precise",
) -> RankedCompany:
    similarities = [cosine_similarity(company.embedding, embedding) for embedding in positive_embeddings]
    semantic = 0.6 * statistics.median(similarities) + 0.4 * max(similarities)
    profile_scores = [structured_similarity(company.profile, profile) for profile in positive_profiles]
    profile_score = 0.6 * statistics.median(profile_scores) + 0.4 * max(profile_scores)
    lexical_scores = [lexical_similarity(company.profile, profile) for profile in positive_profiles]
    lexical = 0.6 * statistics.median(lexical_scores) + 0.4 * max(lexical_scores)

    negative = max(
        [
            0.7 * cosine_similarity(company.embedding, embedding)
            + 0.3 * structured_similarity(company.profile, profile)
            for profile, embedding in zip(negative_profiles, negative_embeddings)
        ],
        default=0.0,
    )
    if matching_mode == "broad":
        industry_overlap = phrase_overlap(
            [company.profile.industry, company.category],
            [profile.industry for profile in positive_profiles],
        ) or 0.0
        raw = 0.45 * semantic + 0.25 * profile_score + 0.20 * industry_overlap + 0.10 * lexical - 0.20 * negative
    else:
        raw = 0.62 * semantic + 0.25 * profile_score + 0.13 * lexical - 0.20 * negative
    score = round(max(0.0, min(100.0, raw * 100)), 1)
    return RankedCompany(
        company=company,
        score=score,
        semantic_score=round(semantic * 100, 1),
        profile_score=round(profile_score * 100, 1),
        lexical_score=round(lexical * 100, 1),
        negative_penalty=round(negative * 20, 1),
        reasons=similarity_reasons(company.profile, merge_profiles(positive_profiles)),
    )


def rerank_top(
    ranked: list[RankedCompany], positives: list[CompanyProfile], negatives: list[CompanyProfile],
    matching_mode: str = "precise",
) -> list[RankedCompany]:
    if not ranked or not get_openai_api_key():
        return ranked
    payload = {
        "ideal_companies": [profile.model_dump() for profile in positives],
        "not_like_companies": [profile.model_dump() for profile in negatives],
        "matching_mode": matching_mode,
        "candidates": [
            {
                "domain": item.company.domain,
                "base_score": item.score,
                "profile": item.company.profile.model_dump(),
            }
            for item in ranked
        ],
        "instructions": (
            "Judge like-for-like company fit from 0 to 100. In precise mode, strongly reward matching products, "
            "services, customer type, business model, and specialties. In broad mode, allow companies in the same "
            "industry family even when specialties differ. Penalize contradictions and similarity to not-like examples. "
            "Do not reward geography or shared generic words by themselves. Give 1 to 3 factual reasons."
        ),
    }
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {get_openai_api_key()}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "lookalike_ranking",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "results": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "domain": {"type": "string"},
                                            "score": {"type": "number"},
                                            "reasons": {"type": "array", "items": {"type": "string"}},
                                        },
                                        "required": ["domain", "score", "reasons"],
                                    },
                                }
                            },
                            "required": ["results"],
                        },
                    },
                },
                "messages": [
                    {"role": "system", "content": "You are a conservative B2B company-similarity reranker."},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                "temperature": 0.0,
            },
            timeout=50.0,
        )
        response.raise_for_status()
        values = json.loads(response.json()["choices"][0]["message"]["content"])["results"]
        by_domain = {str(value["domain"]).lower(): value for value in values}
    except Exception:
        return ranked

    output: list[RankedCompany] = []
    for item in ranked:
        review = by_domain.get(item.company.domain)
        if not review:
            output.append(item)
            continue
        llm_score = max(0.0, min(100.0, float(review.get("score", item.score))))
        reasons = [" ".join(str(value).split())[:160] for value in review.get("reasons", []) if str(value).strip()]
        output.append(
            RankedCompany(
                company=item.company,
                score=round(0.75 * item.score + 0.25 * llm_score, 1),
                semantic_score=item.semantic_score,
                profile_score=item.profile_score,
                lexical_score=item.lexical_score,
                negative_penalty=item.negative_penalty,
                reasons=reasons[:3] or item.reasons,
            )
        )
    return output


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def structured_similarity(left: CompanyProfile, right: CompanyProfile) -> float:
    scores = [
        (0.34, phrase_overlap(left.services, right.services)),
        (0.16, phrase_overlap([left.industry], [right.industry])),
        (0.20, phrase_overlap(left.customer_types, right.customer_types)),
        (0.15, phrase_overlap(left.business_model, right.business_model)),
        (0.15, phrase_overlap(left.specialties, right.specialties)),
    ]
    available = [(weight, score) for weight, score in scores if score is not None]
    if not available:
        return 0.0
    weight_sum = sum(weight for weight, _score in available)
    return sum(weight * score for weight, score in available) / weight_sum


def lexical_similarity(left: CompanyProfile, right: CompanyProfile) -> float:
    left_terms = terms(left.keywords + left.services + left.specialties)
    right_terms = terms(right.keywords + right.services + right.specialties)
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def phrase_overlap(left: list[str], right: list[str]) -> float | None:
    left_terms = terms(left)
    right_terms = terms(right)
    if not left_terms or not right_terms:
        return None
    return len(left_terms & right_terms) / len(left_terms | right_terms)


def terms(values: list[str]) -> set[str]:
    return {word for value in values for word in value.lower().replace("/", " ").replace("-", " ").split() if len(word) > 2}


def company_matches_filters(company: CatalogCompany, filters: LookalikeFilters) -> bool:
    profile = company.profile
    industry_terms = terms([company.category, profile.industry])
    keyword_terms = terms(profile.keywords + profile.services + profile.specialties + [profile.summary])
    technology_terms = {value.lower() for value in profile.technologies}
    tag_terms = terms([company.category, profile.industry, *profile.services, *profile.keywords])

    if filters.industries_any and not industry_terms.intersection(terms(list(filters.industries_any))):
        return False
    if filters.industries_none and industry_terms.intersection(terms(list(filters.industries_none))):
        return False
    if filters.tags_any and not tag_terms.intersection(terms(list(filters.tags_any))):
        return False
    if filters.tags_none and tag_terms.intersection(terms(list(filters.tags_none))):
        return False
    if filters.keywords_any and not keyword_terms.intersection(terms(list(filters.keywords_any))):
        return False
    if filters.keywords_all and not terms(list(filters.keywords_all)).issubset(keyword_terms):
        return False
    if filters.keywords_none and keyword_terms.intersection(terms(list(filters.keywords_none))):
        return False

    any_technologies = {value.lower() for value in filters.technologies_any}
    all_technologies = {value.lower() for value in filters.technologies_all}
    no_technologies = {value.lower() for value in filters.technologies_none}
    if any_technologies and not technology_terms.intersection(any_technologies):
        return False
    if all_technologies and not all_technologies.issubset(technology_terms):
        return False
    if no_technologies and technology_terms.intersection(no_technologies):
        return False
    if filters.require_hiring and not profile.careers_active:
        return False
    if filters.ecommerce_only and not profile.ecommerce:
        return False
    if filters.updated_within_months and not is_fresh(company.updated_at, filters.updated_within_months):
        return False
    return True


def apply_feedback(item: RankedCompany, label: str) -> RankedCompany:
    if label not in {"fit", "not_fit"}:
        return item
    adjustment = 8.0 if label == "fit" else -35.0
    reason = "Previously marked as a fit" if label == "fit" else "Previously marked as not a fit"
    return RankedCompany(
        company=item.company,
        score=round(max(0.0, min(100.0, item.score + adjustment)), 1),
        semantic_score=item.semantic_score,
        profile_score=item.profile_score,
        lexical_score=item.lexical_score,
        negative_penalty=item.negative_penalty,
        reasons=[reason, *item.reasons][:3],
    )


def is_fresh(updated_at: str, months: int) -> bool:
    if not updated_at:
        return False
    try:
        value = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return value >= datetime.now(timezone.utc) - timedelta(days=max(1, months) * 30)


def similarity_reasons(candidate: CompanyProfile, ideal: CompanyProfile) -> list[str]:
    reasons: list[str] = []
    shared_services = sorted(terms(candidate.services) & terms(ideal.services))
    shared_customers = sorted(terms(candidate.customer_types) & terms(ideal.customer_types))
    shared_models = sorted(terms(candidate.business_model) & terms(ideal.business_model))
    if shared_services:
        reasons.append("Shared services: " + ", ".join(shared_services[:5]))
    if shared_customers:
        reasons.append("Similar customers: " + ", ".join(shared_customers[:4]))
    if shared_models:
        reasons.append("Similar model: " + ", ".join(shared_models[:4]))
    return reasons or ["Website meaning is similar to the reference profile"]


def discovery_queries(profile: CompanyProfile) -> list[str]:
    values = list(profile.discovery_queries)
    values.extend(profile.services[:3])
    if profile.industry:
        values.append(profile.industry)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(value.split()).strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
        if len(result) >= 8:
            break
    return result or ["local service business"]


def candidate_ai_enabled() -> bool:
    return os.getenv("LOOKALIKE_CANDIDATE_AI", "false").strip().lower() in {"1", "true", "yes", "on"}


def seed_from_place(place: PlaceLead, city: str, state: str) -> Seed:
    return Seed(
        url=place.website,
        place_id=place.place_id or None,
        business_name=place.business_name or None,
        phone=place.phone or None,
        address=place.address or None,
        city=city or None,
        state=state or None,
        category=place.category or None,
    )


def catalog_company(seed: Seed, profile: CompanyProfile, embedding: list[float], model: str) -> CatalogCompany:
    url = str(seed.url)
    return CatalogCompany(
        domain=domain_of(url), url=url, place_id=seed.place_id or "", business_name=seed.business_name or "",
        phone=seed.phone or "", address=seed.address or "", city=seed.city or "", state=seed.state or "",
        category=seed.category or profile.industry, profile=profile, embedding=embedding, embedding_model=model,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def ranked_seed(item: RankedCompany, query_id: str, reference_domains: list[str]) -> dict[str, object]:
    company = item.company
    profile = company.profile
    return {
        "url": company.url,
        "place_id": company.place_id,
        "business_name": company.business_name,
        "phone": company.phone,
        "address": company.address,
        "city": company.city,
        "state": company.state,
        "category": company.category,
        "lookalike_query_id": query_id,
        "lookalike_score": item.score,
        "semantic_score": item.semantic_score,
        "profile_score": item.profile_score,
        "lexical_score": item.lexical_score,
        "negative_penalty": item.negative_penalty,
        "similarity_reasons": "; ".join(item.reasons),
        "reference_domains": "; ".join(reference_domains),
        "company_summary": profile.summary,
        "technologies": "; ".join(profile.technologies),
        "social_channels": "; ".join(profile.social_channels),
        "careers_active": profile.careers_active,
        "ecommerce": profile.ecommerce,
        "year_founded": profile.year_founded,
        "employee_size": profile.employee_size,
        "headquarters": profile.headquarters,
        "linkedin_url": profile.linkedin_url,
        "industry_tags": "; ".join(unique_tags(company.category, profile)),
    }


def unique_tags(category: str, profile: CompanyProfile) -> list[str]:
    values = [category, profile.industry, *profile.services[:4], *profile.keywords[:5]]
    return list(dict.fromkeys(" ".join(value.split()).strip().lower() for value in values if value.strip()))[:10]

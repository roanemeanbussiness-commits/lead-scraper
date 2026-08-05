from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

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
class LookalikeRun:
    query_id: str
    candidates_discovered: int
    catalog_size: int
    ranked: list[RankedCompany]
    pages_by_domain: dict[str, list[CrawledPage]]
    discovery_queries: list[str]


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
) -> LookalikeRun:
    if not get_openai_api_key():
        raise ValueError("OPENAI_API_KEY is required for like-for-like company embeddings.")
    if not reference_urls:
        raise ValueError("Add at least one ideal company website.")

    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    catalog = CompanyCatalog(catalog_path)
    pages_by_domain: dict[str, list[CrawledPage]] = {}

    positive_profiles, positive_embeddings, positive_domains = build_reference_set(
        reference_urls, max_pages=max_pages, model=model, pages_by_domain=pages_by_domain
    )
    negative_profiles, negative_embeddings, negative_domains = build_reference_set(
        negative_urls, max_pages=max_pages, model=model, pages_by_domain=pages_by_domain
    ) if negative_urls else ([], [], set())

    combined = merge_profiles(positive_profiles)
    queries = discovery_queries(combined)
    places = search_google_places_queries(queries, location, max_results=max_candidates)
    excluded = positive_domains | negative_domains

    existing = {company.domain: company for company in catalog.list(state=state)}
    candidate_seeds: list[Seed] = []
    for place in places:
        domain = domain_of(place.website)
        if not domain or domain in excluded or domain in existing:
            continue
        candidate_seeds.append(seed_from_place(place, city=city, state=state))

    new_companies: list[tuple[Seed, CompanyProfile, list[CrawledPage]]] = []
    worker_count = min(5, len(candidate_seeds))
    if worker_count:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(profile_candidate, seed, max_pages): seed
                for seed in candidate_seeds
            }
            for future in as_completed(futures):
                result = future.result()
                if result is None:
                    continue
                seed, profile, pages = result
                pages_by_domain[domain_of(str(seed.url))] = pages
                new_companies.append((seed, profile, pages))

    if new_companies:
        embeddings = embed_texts([profile.canonical_text() for _seed, profile, _pages in new_companies], model)
        for (seed, profile, _pages), embedding in zip(new_companies, embeddings):
            company = catalog_company(seed, profile, embedding, model)
            catalog.upsert(company)
            existing[company.domain] = company

    candidates = [company for domain, company in existing.items() if domain not in excluded and company.embedding]
    ranked = [
        score_company(company, positive_profiles, positive_embeddings, negative_profiles, negative_embeddings)
        for company in candidates
    ]
    ranked.sort(key=lambda item: (-item.score, item.company.business_name, item.company.domain))
    reranked = rerank_top(ranked[: max(15, max_results * 2)], positive_profiles, negative_profiles)
    rerank_by_domain = {item.company.domain: item for item in reranked}
    ranked = [rerank_by_domain.get(item.company.domain, item) for item in ranked]
    ranked.sort(key=lambda item: (-item.score, item.company.business_name, item.company.domain))
    ranked = [item for item in ranked if item.score >= min_score][:max_results]

    query_id = hashlib.sha256(
        ("|".join(sorted(positive_domains)) + "::" + "|".join(sorted(negative_domains))).encode("utf-8")
    ).hexdigest()[:16]
    return LookalikeRun(
        query_id=query_id,
        candidates_discovered=len(places),
        catalog_size=catalog.count(),
        ranked=ranked,
        pages_by_domain=pages_by_domain,
        discovery_queries=queries,
    )


def build_reference_set(
    urls: list[str], max_pages: int, model: str, pages_by_domain: dict[str, list[CrawledPage]]
) -> tuple[list[CompanyProfile], list[list[float]], set[str]]:
    profiles: list[CompanyProfile] = []
    domains: set[str] = set()
    for url in urls:
        valid = validate_public_url(url)
        domain = domain_of(valid)
        if domain in domains:
            continue
        pages = crawl_site(valid, max_pages=max_pages, timeout=12.0)
        if not pages:
            raise ValueError(f"Could not read the reference website: {domain}")
        domains.add(domain)
        pages_by_domain[domain] = pages
        seed = Seed(url=valid, business_name=domain)
        profiles.append(profile_company(seed, pages))
    return profiles, embed_texts([profile.canonical_text() for profile in profiles], model), domains


def profile_candidate(seed: Seed, max_pages: int) -> tuple[Seed, CompanyProfile, list[CrawledPage]] | None:
    try:
        pages = crawl_site(str(seed.url), max_pages=max_pages, timeout=12.0)
        if not pages:
            return None
        return seed, profile_company(seed, pages), pages
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
    ranked: list[RankedCompany], positives: list[CompanyProfile], negatives: list[CompanyProfile]
) -> list[RankedCompany]:
    if not ranked or not get_openai_api_key():
        return ranked
    payload = {
        "ideal_companies": [profile.model_dump() for profile in positives],
        "not_like_companies": [profile.model_dump() for profile in negatives],
        "candidates": [
            {
                "domain": item.company.domain,
                "base_score": item.score,
                "profile": item.company.profile.model_dump(),
            }
            for item in ranked
        ],
        "instructions": (
            "Judge like-for-like company fit from 0 to 100. Reward matching services, customer type, business model, "
            "and specialties. Penalize contradictions and similarity to not-like examples. Do not reward geography "
            "or shared generic words by themselves. Give 1 to 3 short factual reasons. Return every candidate once."
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
        if len(result) >= 6:
            break
    return result or ["local service business"]


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
    )


def ranked_seed(item: RankedCompany, query_id: str, reference_domains: list[str]) -> dict[str, str | float]:
    company = item.company
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
    }

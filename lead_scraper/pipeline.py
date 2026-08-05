from __future__ import annotations

import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote_plus

from pydantic import ValidationError

from .ai_enrichment import empty_enrichment, extract_with_openai, openai_configured
from .crawler import CrawledPage, UnsafeURL, crawl_site, domain_of, validate_public_url
from .extract import (
    OwnerCandidate,
    extract_emails,
    extract_linkedin_profile_urls,
    extract_owner_candidates,
    is_business_email,
    looks_like_person_name,
    page_text,
)
from .history import LeadHistory
from .models import Lead, Seed
from .scoring import score_lead


@dataclass(frozen=True)
class PageAnalysis:
    page: CrawledPage
    text: str
    emails: set[str]
    owners: list[OwnerCandidate]
    confidence: int
    blue_signals: list[str]
    texas_signals: list[str]


def run_pipeline(
    seeds_path: Path,
    out_path: Path,
    history_path: Path,
    dedupe: str,
    max_pages: int,
    timeout: float,
    pages_by_domain: dict[str, list[CrawledPage]] | None = None,
    contact_sink: list[dict[str, object]] | None = None,
    progress: Callable[[int, str, str], None] | None = None,
    history_months: int | None = None,
) -> int:
    if dedupe not in {"none", "email", "domain", "email_or_domain"}:
        raise ValueError("dedupe must be one of: none, email, domain, email_or_domain")

    seeds = read_seeds(seeds_path)
    history = LeadHistory.load(history_path, months=history_months)
    leads: dict[tuple[str, str], Lead] = {}
    contacts: list[dict[str, object]] = []
    report = progress or (lambda _value, _stage, _message: None)
    worker_count = min(int(os.getenv("CONTACT_ENRICHMENT_WORKERS", "6")), len(seeds))

    if worker_count:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(process_seed, seed, history, dedupe, max_pages, timeout, pages_by_domain): seed
                for seed in seeds
            }
            completed = 0
            for future in as_completed(futures):
                completed += 1
                seed_leads, contact = future.result()
                for candidate in seed_leads:
                    key = (candidate.email, candidate.domain)
                    existing = leads.get(key)
                    if existing is None or candidate.confidence > existing.confidence:
                        leads[key] = candidate
                if contact:
                    contacts.append(contact)
                report(
                    round(100 * completed / max(1, len(seeds))),
                    "Decision makers",
                    f"Enriched {completed} of {len(seeds)} company websites",
                )

    exported = list(leads.values())
    write_leads(out_path, exported)
    history.append(exported)
    if contact_sink is not None:
        contact_sink.extend(
            sorted(
                contacts,
                key=lambda item: (not bool(item["owner_name"]), str(item["business_name"])),
            )
        )
    return len(exported)


def process_seed(
    seed: Seed,
    history: LeadHistory,
    dedupe: str,
    max_pages: int,
    timeout: float,
    pages_by_domain: dict[str, list[CrawledPage]] | None,
) -> tuple[list[Lead], dict[str, object] | None]:
    seed_url = str(seed.url)
    seed_domain = domain_of(seed_url)
    if history.has_seen("", seed_domain, dedupe, seed.place_id or ""):
        cached = history.contact_for_domain(seed_domain)
        cached_owner = cached.get("owner_name", "")
        if not looks_like_person_name(cached_owner):
            cached_owner = ""
        search_terms = " ".join(
            value for value in [
                cached_owner or "owner founder president",
                seed.business_name or cached.get("business_name") or seed_domain,
                seed.city or "",
                seed.state or "",
            ] if value
        )
        return [], {
            "business_name": seed.business_name or cached.get("business_name") or seed_domain,
            "domain": seed_domain,
            "website": seed_url,
            "owner_name": cached_owner,
            "owner_role": "",
            "owner_confidence": 0,
            "verified_email": cached.get("verified_email", ""),
            "phone": seed.phone or "",
            "location": ", ".join(value for value in [seed.city, seed.state] if value),
            "linkedin_url": seed.linkedin_url or "",
            "linkedin_profile_url": "",
            "decision_maker_search_url": (
                "https://www.linkedin.com/search/results/people/?keywords=" + quote_plus(search_terms)
            ),
            "industry_tags": seed.industry_tags or seed.category or "",
            "source_url": cached.get("source_url", seed_url),
            "cached": True,
        }

    try:
        validate_public_url(seed_url)
        cached_pages = (pages_by_domain or {}).get(seed_domain)
        pages = cached_pages if cached_pages is not None else crawl_site(
            seed_url, max_pages=max_pages, timeout=timeout
        )
    except UnsafeURL:
        return [], None
    analyses = [analyze_page(seed, page) for page in pages]
    owners = [owner for analysis in analyses for owner in analysis.owners]
    best_owner = max(owners, key=lambda item: item.confidence, default=None)

    combined_text = build_ai_evidence(analyses)
    ai_data = empty_enrichment()
    if openai_configured() and combined_text and best_owner is None:
        ai_data = extract_with_openai(
            business_name=seed.business_name or "",
            website=seed_url,
            website_text=combined_text,
            industry=seed.category or "",
            location=", ".join(value for value in [seed.city, seed.state] if value),
        )
        if ai_data.get("owner_name") and looks_like_person_name(ai_data["owner_name"]):
            best_owner = OwnerCandidate(
                name=ai_data["owner_name"],
                role=ai_data.get("owner_role") or "Owner/Leader",
                evidence=ai_data.get("owner_evidence") or "OpenAI review of public website text",
                source_url=seed_url,
                confidence=72,
            )

    ai_email = ai_data.get("email", "")
    if ai_email and is_business_email(ai_email) and analyses:
        analyses[0].emails.add(ai_email)

    linkedin_profiles = list(
        dict.fromkeys(
            profile
            for analysis in analyses
            for profile in extract_linkedin_profile_urls(analysis.page.html)
        )
    )
    available_emails = sorted({email for analysis in analyses for email in analysis.emails})
    search_terms = " ".join(
        value for value in [
            best_owner.name if best_owner else "owner founder president",
            seed.business_name or seed_domain,
            seed.city or "",
            seed.state or "",
        ] if value
    )
    linkedin_search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(search_terms)}"
    contact = {
        "business_name": seed.business_name or seed_domain,
        "domain": seed_domain,
        "website": seed_url,
        "owner_name": best_owner.name if best_owner else "",
        "owner_role": best_owner.role if best_owner else "",
        "owner_confidence": best_owner.confidence if best_owner else 0,
        "verified_email": available_emails[0] if available_emails else "",
        "phone": seed.phone or "",
        "location": ", ".join(value for value in [seed.city, seed.state] if value),
        "linkedin_url": seed.linkedin_url or "",
        "linkedin_profile_url": linkedin_profiles[0] if linkedin_profiles else "",
        "decision_maker_search_url": linkedin_search_url,
        "industry_tags": seed.industry_tags or seed.category or "",
        "source_url": best_owner.source_url if best_owner else seed_url,
    }

    seed_leads: list[Lead] = []
    for analysis in analyses:
        for email in analysis.emails:
            domain = seed_domain or domain_of(analysis.page.url)
            if history.has_seen(email, domain, dedupe, seed.place_id or ""):
                continue
            seed_leads.append(
                Lead(
                    email=email,
                    possible_owner=best_owner.name if best_owner else None,
                    owner_role=best_owner.role if best_owner else None,
                    owner_evidence=best_owner.evidence if best_owner else None,
                    owner_source_url=best_owner.source_url if best_owner else None,
                    owner_confidence=best_owner.confidence if best_owner else 0,
                    custom_opener=ai_data.get("custom_opener") or None,
                    place_id=seed.place_id,
                    domain=domain,
                    source_url=analysis.page.url,
                    business_name=seed.business_name,
                    phone=seed.phone,
                    address=seed.address,
                    city=seed.city,
                    state=seed.state,
                    category=seed.category,
                    blue_collar_signals=", ".join(analysis.blue_signals),
                    texas_signals=", ".join(analysis.texas_signals),
                    confidence=analysis.confidence,
                    lookalike_query_id=seed.lookalike_query_id,
                    lookalike_score=seed.lookalike_score,
                    semantic_score=seed.semantic_score,
                    profile_score=seed.profile_score,
                    lexical_score=seed.lexical_score,
                    negative_penalty=seed.negative_penalty,
                    similarity_reasons=seed.similarity_reasons,
                    reference_domains=seed.reference_domains,
                    company_summary=seed.company_summary,
                    technologies=seed.technologies,
                    social_channels=seed.social_channels,
                    careers_active=seed.careers_active,
                    ecommerce=seed.ecommerce,
                    year_founded=seed.year_founded,
                    employee_size=seed.employee_size,
                    headquarters=seed.headquarters,
                    linkedin_url=seed.linkedin_url,
                    linkedin_profile_url=linkedin_profiles[0] if linkedin_profiles else None,
                    decision_maker_search_url=linkedin_search_url,
                    industry_tags=seed.industry_tags,
                )
            )
    return seed_leads, contact


def analyze_page(seed: Seed, page: CrawledPage) -> PageAnalysis:
    text = page_text(page.html)
    confidence, blue_signals, texas_signals = score_lead(seed, text)
    return PageAnalysis(
        page=page,
        text=text,
        emails=extract_emails(page.html),
        owners=extract_owner_candidates(page.html, page.url),
        confidence=confidence,
        blue_signals=blue_signals,
        texas_signals=texas_signals,
    )


def build_ai_evidence(analyses: list[PageAnalysis], limit: int = 8000) -> str:
    sections = []
    for analysis in analyses:
        if not analysis.text:
            continue
        sections.append(f"SOURCE: {analysis.page.url}\n{analysis.text[:2500]}")
        if sum(len(section) for section in sections) >= limit:
            break
    return "\n\n".join(sections)[:limit]


def read_seeds(path: Path) -> list[Seed]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = csv.DictReader(handle)
        seeds = []
        for index, row in enumerate(rows, start=2):
            try:
                seeds.append(
                    Seed(
                        url=row.get("url") or row.get("website") or row.get("domain"),
                        place_id=row.get("place_id") or None,
                        business_name=row.get("business_name") or row.get("name"),
                        phone=row.get("phone") or row.get("phone_number"),
                        address=row.get("address") or row.get("street_address"),
                        city=row.get("city"),
                        state=row.get("state"),
                        category=row.get("category") or row.get("trade"),
                        lookalike_query_id=row.get("lookalike_query_id") or None,
                        lookalike_score=row.get("lookalike_score") or 0,
                        semantic_score=row.get("semantic_score") or 0,
                        profile_score=row.get("profile_score") or 0,
                        lexical_score=row.get("lexical_score") or 0,
                        negative_penalty=row.get("negative_penalty") or 0,
                        similarity_reasons=row.get("similarity_reasons") or None,
                        reference_domains=row.get("reference_domains") or None,
                        company_summary=row.get("company_summary") or None,
                        technologies=row.get("technologies") or None,
                        social_channels=row.get("social_channels") or None,
                        careers_active=parse_bool(row.get("careers_active")),
                        ecommerce=parse_bool(row.get("ecommerce")),
                        year_founded=row.get("year_founded") or None,
                        employee_size=row.get("employee_size") or None,
                        headquarters=row.get("headquarters") or None,
                        linkedin_url=row.get("linkedin_url") or None,
                        industry_tags=row.get("industry_tags") or None,
                    )
                )
            except ValidationError as exc:
                raise ValueError(f"Invalid seed row {index}: {exc}") from exc
    return seeds


def write_leads(path: Path, leads: Iterable[Lead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(Lead.model_fields.keys())
    sorted_leads = sorted(leads, key=lambda lead: (-lead.confidence, lead.domain, lead.email))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for lead in sorted_leads:
            writer.writerow(lead.model_dump())


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}

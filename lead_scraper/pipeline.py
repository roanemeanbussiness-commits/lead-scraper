from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from .ai_enrichment import empty_enrichment, extract_with_openai, openai_configured
from .crawler import CrawledPage, UnsafeURL, crawl_site, domain_of, validate_public_url
from .extract import OwnerCandidate, extract_emails, extract_owner_candidates, is_business_email, page_text
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
) -> int:
    if dedupe not in {"none", "email", "domain", "email_or_domain"}:
        raise ValueError("dedupe must be one of: none, email, domain, email_or_domain")

    seeds = read_seeds(seeds_path)
    history = LeadHistory.load(history_path)
    leads: dict[tuple[str, str], Lead] = {}

    for seed in seeds:
        seed_url = str(seed.url)
        seed_domain = domain_of(seed_url)
        if history.has_seen("", seed_domain, dedupe, seed.place_id or ""):
            continue

        try:
            validate_public_url(seed_url)
            pages = crawl_site(seed_url, max_pages=max_pages, timeout=timeout)
        except UnsafeURL:
            continue
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
            if ai_data.get("owner_name"):
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

        for analysis in analyses:
            for email in analysis.emails:
                domain = seed_domain or domain_of(analysis.page.url)
                if history.has_seen(email, domain, dedupe, seed.place_id or ""):
                    continue

                key = (email, domain)
                candidate = Lead(
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
                )
                existing = leads.get(key)
                if existing is None or candidate.confidence > existing.confidence:
                    leads[key] = candidate

    exported = list(leads.values())
    write_leads(out_path, exported)
    history.append(exported)
    return len(exported)


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

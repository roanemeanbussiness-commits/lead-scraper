from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from .crawler import crawl_site, domain_of
from .extract import extract_emails, extract_possible_owners, page_text
from .history import LeadHistory
from .models import Lead, Seed
from .scoring import score_lead


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
        pages = crawl_site(str(seed.url), max_pages=max_pages, timeout=timeout)
        for page in pages:
            text = page_text(page.html)
            confidence, blue_signals, texas_signals = score_lead(seed, text)
            owners = sorted(extract_possible_owners(page.html))
            for email in extract_emails(page.html):
                domain = domain_of(page.url)
                if history.has_seen(email=email, domain=domain, mode=dedupe):
                    continue

                key = (email, domain)
                existing = leads.get(key)
                candidate = Lead(
                    email=email,
                    possible_owner=", ".join(owners) or None,
                    domain=domain,
                    source_url=page.url,
                    business_name=seed.business_name,
                    phone=seed.phone,
                    address=seed.address,
                    city=seed.city,
                    state=seed.state,
                    category=seed.category,
                    blue_collar_signals=", ".join(blue_signals),
                    texas_signals=", ".join(texas_signals),
                    confidence=confidence,
                )
                if existing is None or candidate.confidence > existing.confidence:
                    leads[key] = candidate

    exported = list(leads.values())
    write_leads(out_path, exported)
    history.append(exported)
    return len(exported)


def read_seeds(path: Path) -> list[Seed]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = csv.DictReader(handle)
        seeds = []
        for index, row in enumerate(rows, start=2):
            try:
                seeds.append(
                    Seed(
                        url=row.get("url") or row.get("website") or row.get("domain"),
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

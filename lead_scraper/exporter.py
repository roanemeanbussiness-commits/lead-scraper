from __future__ import annotations

import csv
from pathlib import Path

from .extract import is_generic_email
from .validation import has_mx_record

LEAD_EXPORT_FIELDNAMES = [
    "business_name",
    "owner_name",
    "owner_role",
    "owner_confidence",
    "owner_evidence",
    "owner_source_url",
    "first_name",
    "verified_email",
    "phone",
    "website",
    "location",
    "industry",
    "custom_opener",
    "source",
    "place_id",
    "lookalike_query_id",
    "lookalike_score",
    "semantic_score",
    "profile_score",
    "lexical_score",
    "negative_penalty",
    "similarity_reasons",
    "reference_domains",
    "company_summary",
    "technologies",
    "social_channels",
    "careers_active",
    "ecommerce",
    "year_founded",
    "employee_size",
    "headquarters",
    "linkedin_url",
    "linkedin_profile_url",
    "decision_maker_search_url",
    "industry_tags",
]


def export_direct_leads(
    input_path: Path,
    output_path: Path,
    drop_generic: bool = True,
    verify_mx: bool = False,
) -> tuple[int, int]:
    leads = read_rows(input_path)
    cleaned_leads, dropped = clean_direct_leads(leads, drop_generic=drop_generic, verify_mx=verify_mx)
    write_email_agent_csv(output_path, cleaned_leads)
    return len(cleaned_leads), dropped


def clean_direct_leads(
    leads: list[dict[str, str]],
    drop_generic: bool = True,
    verify_mx: bool = False,
) -> tuple[list[dict[str, str]], int]:
    seen_emails: set[str] = set()
    cleaned_leads: list[dict[str, str]] = []
    dropped = 0

    for lead in leads:
        email = email_of(lead)
        if not email or email in seen_emails:
            dropped += 1
            continue
        if drop_generic and is_generic_email(email):
            dropped += 1
            continue
        if verify_mx and not has_mx_record(email):
            dropped += 1
            continue

        seen_emails.add(email)
        owner_name = owner_of(lead)
        first_name = owner_name.split()[0] if owner_name else "There"

        cleaned_leads.append(
            {
                "business_name": title_clean(lead.get("business_name") or lead.get("name")),
                "owner_name": owner_name,
                "owner_role": clean(lead.get("owner_role")),
                "owner_confidence": clean(lead.get("owner_confidence")),
                "owner_evidence": clean(lead.get("owner_evidence")),
                "owner_source_url": clean(lead.get("owner_source_url")),
                "first_name": first_name,
                "verified_email": email,
                "phone": clean(lead.get("phone")),
                "website": clean(lead.get("website") or lead.get("source_url")).lower(),
                "location": location_of(lead),
                "industry": title_clean(lead.get("industry") or lead.get("category")),
                "custom_opener": clean(lead.get("custom_opener")),
                "source": clean(lead.get("source")) or "Web Scraper",
                "place_id": clean(lead.get("place_id")),
                "lookalike_query_id": clean(lead.get("lookalike_query_id")),
                "lookalike_score": clean(lead.get("lookalike_score")),
                "semantic_score": clean(lead.get("semantic_score")),
                "profile_score": clean(lead.get("profile_score")),
                "lexical_score": clean(lead.get("lexical_score")),
                "negative_penalty": clean(lead.get("negative_penalty")),
                "similarity_reasons": clean(lead.get("similarity_reasons")),
                "reference_domains": clean(lead.get("reference_domains")),
                "company_summary": clean(lead.get("company_summary")),
                "technologies": clean(lead.get("technologies")),
                "social_channels": clean(lead.get("social_channels")),
                "careers_active": clean(lead.get("careers_active")),
                "ecommerce": clean(lead.get("ecommerce")),
                "year_founded": clean(lead.get("year_founded")),
                "employee_size": clean(lead.get("employee_size")),
                "headquarters": clean(lead.get("headquarters")),
                "linkedin_url": clean(lead.get("linkedin_url")),
                "linkedin_profile_url": clean(lead.get("linkedin_profile_url")),
                "decision_maker_search_url": clean(lead.get("decision_maker_search_url")),
                "industry_tags": clean(lead.get("industry_tags")),
            }
        )

    return cleaned_leads, dropped


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_email_agent_csv(path: Path, leads: list[dict[str, str]]) -> None:
    write_lead_export_csv(path, leads)


def write_lead_export_csv(path: Path, leads: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEAD_EXPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(leads)


def email_of(lead: dict[str, str]) -> str:
    return clean(lead.get("verified_email") or lead.get("email")).lower()


def owner_of(lead: dict[str, str]) -> str:
    value = clean(lead.get("owner_name") or lead.get("possible_owner"))
    if "," in value:
        value = value.split(",", maxsplit=1)[0]
    return value.title()


def location_of(lead: dict[str, str]) -> str:
    location = clean(lead.get("location"))
    if location:
        return location.title()

    city = clean(lead.get("city"))
    state = clean(lead.get("state")).upper()
    return ", ".join(value for value in [city, state] if value)


def clean(value: str | None) -> str:
    return (value or "").strip()


def title_clean(value: str | None) -> str:
    return clean(value).title()

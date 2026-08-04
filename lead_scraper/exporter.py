from __future__ import annotations

import csv
from pathlib import Path

from .extract import is_generic_email

EMAIL_AGENT_FIELDNAMES = [
    "business_name",
    "owner_name",
    "first_name",
    "verified_email",
    "phone",
    "website",
    "location",
    "industry",
    "custom_opener",
    "source",
]


def export_direct_leads(input_path: Path, output_path: Path, drop_generic: bool = True) -> tuple[int, int]:
    leads = read_rows(input_path)
    cleaned_leads, dropped = clean_direct_leads(leads, drop_generic=drop_generic)
    write_email_agent_csv(output_path, cleaned_leads)
    return len(cleaned_leads), dropped


def clean_direct_leads(leads: list[dict[str, str]], drop_generic: bool = True) -> tuple[list[dict[str, str]], int]:
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

        seen_emails.add(email)
        owner_name = owner_of(lead)
        first_name = owner_name.split()[0] if owner_name else "There"

        cleaned_leads.append(
            {
                "business_name": title_clean(lead.get("business_name") or lead.get("name")),
                "owner_name": owner_name,
                "first_name": first_name,
                "verified_email": email,
                "phone": clean(lead.get("phone")),
                "website": clean(lead.get("website") or lead.get("source_url")).lower(),
                "location": location_of(lead),
                "industry": title_clean(lead.get("industry") or lead.get("category")),
                "custom_opener": clean(lead.get("custom_opener")),
                "source": clean(lead.get("source")) or "Web Scraper",
            }
        )

    return cleaned_leads, dropped


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_email_agent_csv(path: Path, leads: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EMAIL_AGENT_FIELDNAMES)
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

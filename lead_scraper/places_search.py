"""Google Places discovery path used when Ocean.io credits are unavailable.

Ocean stays the primary provider. This module rebuilds the pre-Ocean flow --
Places text search, site crawl, email extraction, MX validation -- so the app
can still produce leads without Ocean credits. Emails found here are scraped
from the company's own website and checked for a deliverable MX record; that
is a weaker guarantee than an Ocean reveal, so they carry their own statuses
and are never labelled as Ocean-verified.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from urllib.parse import urlparse

from .crawler import UnsafeURL, crawl_site, domain_of, validate_public_url
from .extract import (
    extract_emails,
    extract_linkedin_profile_urls,
    extract_owner_candidates,
    is_business_email,
    is_generic_email,
    looks_like_person_name,
)
from .google_places import (
    PlaceLead,
    keyword_discovery_queries,
    search_google_places_queries,
)
from .validation import has_mx_record

# Direct addresses (owner@, jane.doe@) beat role inboxes (info@, sales@).
STATUS_PERSONAL_MX = "site_personal_mx"
STATUS_PERSONAL = "site_personal"
STATUS_GENERIC_MX = "site_generic_mx"
STATUS_GENERIC = "site_generic"
DELIVERABLE_STATUSES = {STATUS_PERSONAL_MX, STATUS_GENERIC_MX}


def place_to_row(place: PlaceLead) -> dict[str, object]:
    domain = (urlparse(place.website).hostname or "").lower().removeprefix("www.")
    return {
        "business_name": place.business_name or domain,
        "domain": domain,
        "website": place.website,
        "phone": place.phone,
        "location": place.address,
        "industry": place.category,
        "place_id": place.place_id,
    }


def rank_emails(emails: set[str], domain: str, verify_mx: bool) -> list[tuple[str, str]]:
    """Return (address, status) best-first for a single site."""
    ranked: list[tuple[int, str, str]] = []
    for email in sorted(emails):
        if not is_business_email(email):
            continue
        generic = is_generic_email(email)
        deliverable = has_mx_record(email) if verify_mx else False
        if generic:
            status = STATUS_GENERIC_MX if deliverable else STATUS_GENERIC
            rank = 2 if deliverable else 3
        else:
            status = STATUS_PERSONAL_MX if deliverable else STATUS_PERSONAL
            rank = 0 if deliverable else 1
        on_domain = email.lower().endswith("@" + domain) if domain else False
        ranked.append((rank + (0 if on_domain else 4), email.lower(), status))
    ranked.sort()
    return [(email, status) for _rank, email, status in ranked]


def enrich_place(
    place: PlaceLead,
    max_pages: int,
    timeout: float,
    verify_mx: bool,
) -> dict[str, object]:
    row = place_to_row(place)
    row.update(
        {
            "owner_name": "",
            "owner_role": "",
            "verified_email": "",
            "email_status": "",
            "linkedin_profile_url": "",
            "source": "Google Places + site crawl",
        }
    )
    try:
        validate_public_url(place.website)
        pages = crawl_site(place.website, max_pages=max_pages, timeout=timeout)
    except (UnsafeURL, Exception):  # noqa: BLE001 - a dead site must not kill the run
        return row

    emails: set[str] = set()
    owners = []
    profiles: list[str] = []
    for page in pages:
        emails.update(extract_emails(page.html))
        owners.extend(extract_owner_candidates(page.html, page.url))
        profiles.extend(extract_linkedin_profile_urls(page.html))

    domain = str(row.get("domain") or "") or domain_of(place.website)
    for email, status in rank_emails(emails, domain, verify_mx):
        row["verified_email"] = email
        row["email_status"] = status
        break

    best_owner = max(owners, key=lambda item: item.confidence, default=None)
    if best_owner and looks_like_person_name(best_owner.name):
        row["owner_name"] = best_owner.name
        row["owner_role"] = best_owner.role
    if profiles:
        row["linkedin_profile_url"] = profiles[0]
    return row


def search_places_leads(
    *,
    query: str,
    location: str,
    target_count: int,
    require_email: bool,
    verify_mx: bool,
    max_pages: int = 6,
    timeout: float = 12.0,
    workers: int = 8,
    progress: Callable[[int, str, str], None] | None = None,
    excluded_domains: set[str] | None = None,
) -> list[dict[str, object]]:
    report = progress or (lambda _value, _stage, _message: None)
    excluded = {domain.lower() for domain in (excluded_domains or set())}

    # Crawling drops sites with no reachable email, so start from a wider pool.
    pool = target_count * 3 if require_email else target_count
    report(10, "Google Places", f"Searching Google Places for '{query}' in {location}")
    places = search_google_places_queries(
        keyword_discovery_queries(query, pool),
        location,
        max_results=min(600, pool),
    )
    places = [
        place
        for place in places
        if (urlparse(place.website).hostname or "").lower().removeprefix("www.") not in excluded
    ]
    if not places:
        return []

    report(30, "Crawling sites", f"Checking {len(places)} business websites for contacts")
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(places)))) as executor:
        futures = {
            executor.submit(enrich_place, place, max_pages, timeout, verify_mx): place
            for place in places
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            row = future.result()
            if not require_email or row.get("verified_email"):
                rows.append(row)
            report(
                min(92, 30 + round(60 * done / max(1, len(places)))),
                "Crawling sites",
                f"Checked {done} of {len(places)} sites, {len(rows)} leads kept",
            )
            if len(rows) >= target_count:
                break
        for future in futures:
            future.cancel()
    return rows[:target_count]

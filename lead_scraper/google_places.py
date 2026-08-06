from __future__ import annotations

import os
import math
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import httpx

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.nationalPhoneNumber,"
    "places.websiteUri,"
    "places.primaryTypeDisplayName,"
    "nextPageToken"
)

TRADE_QUERY_EXPANSIONS = {
    # Near-synonyms ("construction company", "local construction") return the
    # same businesses Google already returned. Only genuinely distinct trades
    # and specialities widen the candidate pool, so each list holds sibling
    # business types rather than rewordings of the same one.
    "construct": [
        "general contractor", "home builder", "custom home builder",
        "remodeling contractor", "kitchen remodeler", "bathroom remodeler",
        "commercial construction company", "concrete contractor",
        "framing contractor", "masonry contractor", "excavation contractor",
        "drywall contractor", "foundation repair", "flooring contractor",
        "roofing contractor", "siding contractor", "window installation",
        "demolition contractor", "steel building contractor",
        "civil construction company", "paving contractor", "fence contractor",
        "carpentry contractor", "insulation contractor",
    ],
    "contractor": [
        "general contractor", "home builder", "remodeling contractor",
        "concrete contractor", "roofing contractor", "masonry contractor",
        "excavation contractor", "drywall contractor", "flooring contractor",
        "paving contractor", "fence contractor", "carpentry contractor",
    ],
    "remodel": [
        "remodeling contractor", "kitchen remodeler", "bathroom remodeler",
        "home renovation company", "general contractor", "flooring contractor",
        "cabinet installer", "countertop installer", "tile contractor",
        "custom home builder", "room addition contractor",
    ],
    "insurance": [
        "insurance agency", "auto insurance agency", "home insurance agency",
        "life insurance agency", "health insurance agent",
        "medicare insurance agent", "commercial insurance broker",
        "independent insurance agent", "insurance broker",
    ],
    "law": [
        "personal injury lawyer", "car accident attorney",
        "criminal defense attorney", "family law attorney", "divorce lawyer",
        "immigration lawyer", "estate planning attorney", "bankruptcy attorney",
        "workers compensation lawyer", "business attorney",
    ],
    "attorney": [
        "personal injury lawyer", "car accident attorney",
        "criminal defense attorney", "family law attorney", "divorce lawyer",
        "immigration lawyer", "estate planning attorney", "bankruptcy attorney",
    ],
    "dent": [
        "dentist", "cosmetic dentist", "dental implants clinic", "orthodontist",
        "pediatric dentist", "oral surgeon", "periodontist", "emergency dentist",
    ],
    "spa": [
        "med spa", "medical spa", "botox clinic", "laser hair removal",
        "aesthetics clinic", "skin care clinic", "wellness clinic",
        "body contouring clinic",
    ],
    "real estate": [
        "real estate brokerage", "property management company", "realtor office",
        "commercial real estate broker", "apartment property management",
        "real estate investment company",
    ],
    "auto": [
        "auto repair shop", "auto body shop", "transmission repair",
        "car detailing", "tire shop", "mobile mechanic", "brake repair shop",
        "collision repair center",
    ],
    "clean": [
        "commercial cleaning company", "janitorial services", "maid service",
        "carpet cleaning company", "window cleaning service",
        "pressure washing company", "post construction cleaning",
    ],
    "market": [
        "marketing agency", "digital marketing agency", "SEO company",
        "advertising agency", "web design company", "branding agency",
        "social media marketing agency",
    ],
    "staffing": [
        "staffing agency", "recruiting agency", "temp agency",
        "employment agency", "executive search firm", "nurse staffing agency",
    ],
    "account": [
        "accounting firm", "CPA firm", "bookkeeping service",
        "tax preparation service", "payroll service", "business tax advisor",
    ],
    "it ": [
        "managed IT services", "IT support company", "cybersecurity company",
        "computer repair for business", "network support company",
        "cloud services provider",
    ],
    "solar": [
        "solar installer", "solar panel company", "solar energy contractor",
        "residential solar company", "commercial solar installer",
        "solar battery installer",
    ],
    "restoration": [
        "water damage restoration", "fire damage restoration",
        "mold remediation company", "storm damage restoration",
        "flood cleanup service", "smoke damage restoration",
    ],
    "pest": [
        "pest control company", "exterminator", "termite control",
        "wildlife removal", "rodent control", "mosquito control service",
    ],
    "moving": [
        "moving company", "long distance movers", "junk removal service",
        "packing service", "storage and moving company", "office movers",
    ],
    "senior": [
        "assisted living facility", "home care agency", "senior home care",
        "memory care facility", "nursing home", "hospice care",
    ],
    "fitness": [
        "gym", "fitness studio", "crossfit gym", "martial arts studio",
        "yoga studio", "personal training studio", "pilates studio",
    ],
    "chiro": [
        "chiropractor", "physical therapy clinic", "sports rehab clinic",
        "massage therapy clinic", "pain management clinic",
    ],
    "pool": [
        "pool builder", "swimming pool contractor", "custom pool builder", "pool installation",
        "pool construction company", "inground pool builder", "pool remodeling contractor",
        "pool service company", "pool repair contractor",
    ],
    "roof": [
        "roofing contractor", "residential roofer", "commercial roofing company", "roof repair",
        "metal roofing contractor", "storm damage roofer", "roof replacement company",
    ],
    "plumb": [
        "plumbing contractor", "licensed plumber", "commercial plumber", "residential plumber",
        "drain cleaning company", "water heater contractor", "emergency plumber",
    ],
    "landscap": [
        "landscaping company", "landscape contractor", "commercial landscaper", "lawn care company",
        "hardscape contractor", "irrigation contractor", "tree service company",
    ],
    "hvac": [
        "HVAC contractor", "air conditioning company", "heating contractor", "AC repair company",
        "commercial HVAC company", "residential HVAC contractor",
    ],
    "electric": [
        "electrical contractor", "licensed electrician", "commercial electrician",
        "residential electrician", "electrical service company",
    ],
    "concrete": [
        "concrete contractor", "commercial concrete company", "concrete foundation contractor",
        "decorative concrete company", "concrete repair contractor",
    ],
    "paint": [
        "painting contractor", "commercial painting company", "residential painter",
        "exterior painting contractor", "industrial painting company",
    ],
}


@dataclass(frozen=True)
class PlaceLead:
    place_id: str
    business_name: str
    website: str
    phone: str = ""
    address: str = ""
    category: str = ""


# A bare float timeout left reads able to block indefinitely on a half-open
# TLS socket, which froze whole searches. Bound every phase explicitly.
PLACES_TIMEOUT = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0)

# No single query sweep may outlast this, whatever the network does.
PLACES_SWEEP_DEADLINE_SECONDS = float(os.getenv("PLACES_SWEEP_DEADLINE_SECONDS", "180"))


class GooglePlacesError(RuntimeError):
    pass


def google_places_configured() -> bool:
    return bool(get_google_maps_api_key())


def request_places_page(
    client: httpx.Client,
    headers: dict[str, str],
    payload: dict[str, object],
) -> dict | None:
    """One Places page with retries. Returns None when the page is unavailable.

    Google returns 429/503 under load often enough that a single blip must not
    kill a whole search, so transient failures are retried and then skipped.
    A 4xx other than 429 is a real configuration problem and is raised.
    """
    for attempt in range(4):
        try:
            response = client.post(PLACES_URL, headers=headers, json=payload)
        except httpx.RequestError:
            if attempt == 3:
                return None
            time.sleep(2**attempt)
            continue
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 3:
                return None
            time.sleep(2**attempt)
            continue
        if response.status_code >= 400:
            raise GooglePlacesError(
                f"Google Places returned {response.status_code}: "
                f"{places_error_detail(response)}"
            )
        return response.json()
    return None


def places_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:300] or "Unknown Places error"
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("status") or error)[:300]
    return str(payload)[:300]


def search_google_places(query: str, location: str, max_results: int = 20) -> list[PlaceLead]:
    api_key = get_google_maps_api_key()
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not configured.")

    text_query = query.strip()
    if location.strip():
        text_query = f"{text_query} in {location.strip()}"
    if not text_query or max_results <= 0:
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    leads: list[PlaceLead] = []
    seen_place_ids: set[str] = set()
    seen_page_tokens: set[str] = set()
    page_token = ""

    page_deadline = time.monotonic() + PLACES_SWEEP_DEADLINE_SECONDS
    with httpx.Client(timeout=PLACES_TIMEOUT) as client:
        while len(leads) < max_results and time.monotonic() < page_deadline:
            payload: dict[str, str | int] = {
                "textQuery": text_query,
                "pageSize": min(20, max_results - len(leads)),
                "regionCode": "US",
            }
            if page_token:
                payload["pageToken"] = page_token

            data = request_places_page(client, headers, payload)
            if data is None:
                break

            for place in data.get("places", []):
                website = place.get("websiteUri") or ""
                place_id = place.get("id") or ""
                if not website or (place_id and place_id in seen_place_ids):
                    continue
                display_name = place.get("displayName") or {}
                primary_type = place.get("primaryTypeDisplayName") or {}
                leads.append(
                    PlaceLead(
                        place_id=place_id,
                        business_name=display_name.get("text") or "",
                        website=website,
                        phone=place.get("nationalPhoneNumber") or "",
                        address=place.get("formattedAddress") or "",
                        category=primary_type.get("text") or query,
                    )
                )
                if place_id:
                    seen_place_ids.add(place_id)
                if len(leads) >= max_results:
                    break

            page_token = data.get("nextPageToken") or ""
            if not page_token or page_token in seen_page_tokens:
                break
            seen_page_tokens.add(page_token)

    return leads


def search_google_places_queries(
    queries: list[str],
    location: str,
    max_results: int = 160,
    progress: Callable[[int, int, int], None] | None = None,
) -> list[PlaceLead]:
    """Search several semantic discovery queries and dedupe the shared candidate pool."""
    clean_queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))
    if not clean_queries or max_results <= 0:
        return []

    # Text Search currently permits up to 60 results per query. Spread the pool
    # across semantic phrases so one broad query does not dominate the catalog.
    per_query = min(60, max(10, math.ceil(max_results * 1.35 / len(clean_queries))))
    results: list[PlaceLead] = []
    seen: set[str] = set()
    failures = 0
    deadline = time.monotonic() + PLACES_SWEEP_DEADLINE_SECONDS
    for index, query in enumerate(clean_queries, start=1):
        if time.monotonic() > deadline:
            break
        try:
            found = search_google_places(query, location, max_results=per_query)
        except GooglePlacesError:
            raise
        except Exception:  # noqa: BLE001 - one bad query must not end the sweep
            failures += 1
            found = []
        for place in found:
            domain = (urlparse(place.website).hostname or "").lower().removeprefix("www.")
            key = place.place_id or domain
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(place)
            if len(results) >= max_results:
                if progress:
                    progress(index, len(clean_queries), len(results))
                return results
        if progress:
            progress(index, len(clean_queries), len(results))
    if not results and failures == len(clean_queries):
        raise GooglePlacesError(
            "Google Places is unavailable right now (every query failed). Try again shortly."
        )
    return results


def keyword_discovery_queries(query: str, target_count: int) -> list[str]:
    """Expand a trade keyword into distinct Places searches for larger candidate pools."""
    clean = " ".join(query.split()).strip()
    if not clean:
        return []
    # Text Search returns ~60 results per query, so reaching a few hundred
    # candidates needs many distinct queries, not a handful.
    max_queries = min(30, max(6, math.ceil(max(1, target_count) / 20)))
    candidates = [clean]
    lowered = clean.lower()
    for signal, expansions in TRADE_QUERY_EXPANSIONS.items():
        if signal in lowered:
            candidates.extend(expansions)
    candidates.extend(
        [
            f"{clean} contractor",
            f"{clean} company",
            f"{clean} services",
            f"{clean} specialist",
            f"local {clean}",
            f"commercial {clean}",
            f"residential {clean}",
            f"licensed {clean}",
            f"family owned {clean}",
            f"independent {clean} company",
        ]
    )
    output: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = " ".join(candidate.split()).strip()
        key = normalized.lower()
        if key and key not in seen:
            seen.add(key)
            output.append(normalized)
        if len(output) >= max_queries:
            break
    return output


def get_google_maps_api_key() -> str:
    return (
        os.getenv("GOOGLE_MAPS_API_KEY")
        or os.getenv("GOOGLE_PLACES_API_KEY")
        or os.getenv("GooglePlacesAPI")
        or ""
    )

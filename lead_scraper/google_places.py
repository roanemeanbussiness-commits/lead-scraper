from __future__ import annotations

import os
import math
from dataclasses import dataclass
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


def google_places_configured() -> bool:
    return bool(get_google_maps_api_key())


def search_google_places(query: str, location: str, max_results: int = 20) -> list[PlaceLead]:
    api_key = get_google_maps_api_key()
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not configured.")

    text_query = " ".join(value for value in [query.strip(), "in", location.strip()] if value)
    if not text_query.strip() or max_results <= 0:
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

    with httpx.Client(timeout=20.0) as client:
        while len(leads) < max_results:
            payload: dict[str, str | int] = {
                "textQuery": text_query,
                "pageSize": min(20, max_results - len(leads)),
                "regionCode": "US",
            }
            if page_token:
                payload["pageToken"] = page_token

            response = client.post(PLACES_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

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


def search_google_places_queries(queries: list[str], location: str, max_results: int = 160) -> list[PlaceLead]:
    """Search several semantic discovery queries and dedupe the shared candidate pool."""
    clean_queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))
    if not clean_queries or max_results <= 0:
        return []

    # Text Search currently permits up to 60 results per query. Spread the pool
    # across semantic phrases so one broad query does not dominate the catalog.
    per_query = min(60, max(10, math.ceil(max_results * 1.35 / len(clean_queries))))
    results: list[PlaceLead] = []
    seen: set[str] = set()
    for query in clean_queries:
        for place in search_google_places(query, location, max_results=per_query):
            domain = (urlparse(place.website).hostname or "").lower().removeprefix("www.")
            key = place.place_id or domain
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(place)
            if len(results) >= max_results:
                return results
    return results


def keyword_discovery_queries(query: str, target_count: int) -> list[str]:
    """Expand a trade keyword into distinct Places searches for larger candidate pools."""
    clean = " ".join(query.split()).strip()
    if not clean:
        return []
    max_queries = min(24, max(4, math.ceil(max(1, target_count) / 45)))
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

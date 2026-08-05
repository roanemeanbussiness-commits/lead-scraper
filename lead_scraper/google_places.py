from __future__ import annotations

import os
from dataclasses import dataclass

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


def get_google_maps_api_key() -> str:
    return (
        os.getenv("GOOGLE_MAPS_API_KEY")
        or os.getenv("GOOGLE_PLACES_API_KEY")
        or os.getenv("GooglePlacesAPI")
        or ""
    )

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class PlaceLead:
    business_name: str
    website: str
    phone: str = ""
    address: str = ""
    category: str = ""


def google_places_configured() -> bool:
    return bool(os.getenv("GOOGLE_MAPS_API_KEY"))


def search_google_places(query: str, location: str, max_results: int = 20) -> list[PlaceLead]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not configured.")

    text_query = " ".join(value for value in [query.strip(), "in", location.strip()] if value)
    if not text_query.strip():
        return []

    response = httpx.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.displayName,"
                "places.formattedAddress,"
                "places.nationalPhoneNumber,"
                "places.websiteUri,"
                "places.primaryTypeDisplayName"
            ),
        },
        json={"textQuery": text_query, "maxResultCount": min(max_results, 20)},
        timeout=20.0,
    )
    response.raise_for_status()

    leads: list[PlaceLead] = []
    for place in response.json().get("places", []):
        website = place.get("websiteUri") or ""
        if not website:
            continue
        display_name = place.get("displayName") or {}
        primary_type = place.get("primaryTypeDisplayName") or {}
        leads.append(
            PlaceLead(
                business_name=display_name.get("text") or "",
                website=website,
                phone=place.get("nationalPhoneNumber") or "",
                address=place.get("formattedAddress") or "",
                category=primary_type.get("text") or query,
            )
        )

    return leads


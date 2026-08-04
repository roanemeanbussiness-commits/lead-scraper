from __future__ import annotations

from .config import BLUE_COLLAR_KEYWORDS, TEXAS_SIGNALS
from .models import Seed


def score_lead(seed: Seed, page_text: str) -> tuple[int, list[str], list[str]]:
    haystack = " ".join(
        value
        for value in [
            page_text,
            seed.business_name or "",
            seed.city or "",
            seed.state or "",
            seed.category or "",
        ]
        if value
    ).lower()

    blue = sorted(keyword for keyword in BLUE_COLLAR_KEYWORDS if keyword in haystack)
    texas = sorted(signal for signal in TEXAS_SIGNALS if signal in haystack)

    confidence = 25
    confidence += min(len(blue) * 10, 35)
    confidence += min(len(texas) * 8, 30)
    if seed.city and seed.city.lower() == "san antonio":
        confidence += 10
    if seed.state and seed.state.lower() in {"tx", "texas"}:
        confidence += 10

    return min(confidence, 100), blue, texas


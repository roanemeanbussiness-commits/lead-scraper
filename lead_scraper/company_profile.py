from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter

import httpx
from pydantic import BaseModel, Field

from .ai_enrichment import get_openai_api_key
from .crawler import CrawledPage
from .extract import page_text
from .models import Seed

TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9&+-]{2,}", re.IGNORECASE)
STOPWORDS = {
    "about", "after", "also", "been", "business", "company", "contact", "from", "have",
    "home", "into", "more", "our", "privacy", "service", "services", "that", "their", "them",
    "there", "these", "they", "this", "through", "with", "your",
}


class CompanyProfile(BaseModel):
    summary: str = ""
    industry: str = ""
    services: list[str] = Field(default_factory=list)
    customer_types: list[str] = Field(default_factory=list)
    business_model: list[str] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)
    service_area: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    discovery_queries: list[str] = Field(default_factory=list)

    def canonical_text(self) -> str:
        parts = [
            f"Industry: {self.industry}",
            f"Summary: {self.summary}",
            f"Services: {', '.join(self.services)}",
            f"Customers: {', '.join(self.customer_types)}",
            f"Business model: {', '.join(self.business_model)}",
            f"Specialties: {', '.join(self.specialties)}",
            f"Service area: {', '.join(self.service_area)}",
            f"Keywords: {', '.join(self.keywords)}",
        ]
        return "\n".join(part for part in parts if not part.endswith(": "))


def profile_company(seed: Seed, pages: list[CrawledPage]) -> CompanyProfile:
    evidence = website_evidence(pages)
    if not evidence:
        return fallback_profile(seed, "")
    if not get_openai_api_key():
        return fallback_profile(seed, evidence)

    payload = {
        "company_name": seed.business_name or "",
        "known_category": seed.category or "",
        "location": ", ".join(value for value in [seed.city, seed.state] if value),
        "website": str(seed.url),
        "website_evidence": evidence,
        "instructions": (
            "Build a factual company fingerprint for lookalike search using only the supplied public website evidence. "
            "Describe what the company sells, who buys it, whether it is residential, commercial, B2B, B2C, local, "
            "regional, or national, and meaningful specialties. Use short normalized phrases. Create 3 to 5 Google "
            "Places discovery queries that identify the same kind of company without using this company's name. "
            "Do not infer revenue, employee count, ownership, or unsupported facts."
        ),
    }
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {get_openai_api_key()}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "company_fingerprint",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "summary": {"type": "string"},
                                "industry": {"type": "string"},
                                "services": {"type": "array", "items": {"type": "string"}},
                                "customer_types": {"type": "array", "items": {"type": "string"}},
                                "business_model": {"type": "array", "items": {"type": "string"}},
                                "specialties": {"type": "array", "items": {"type": "string"}},
                                "service_area": {"type": "array", "items": {"type": "string"}},
                                "keywords": {"type": "array", "items": {"type": "string"}},
                                "discovery_queries": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": [
                                "summary", "industry", "services", "customer_types", "business_model",
                                "specialties", "service_area", "keywords", "discovery_queries",
                            ],
                        },
                    },
                },
                "messages": [
                    {"role": "system", "content": "You are a precise company classification engine. Return JSON only."},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                "temperature": 0.1,
            },
            timeout=40.0,
        )
        response.raise_for_status()
        profile = CompanyProfile.model_validate_json(response.json()["choices"][0]["message"]["content"])
        return normalize_profile(profile)
    except Exception:
        return fallback_profile(seed, evidence)


def website_evidence(pages: list[CrawledPage], limit: int = 14_000) -> str:
    sections: list[str] = []
    size = 0
    for page in pages:
        text = page_text(page.html)
        if not text:
            continue
        section = f"SOURCE: {page.url}\n{text[:3500]}"
        sections.append(section)
        size += len(section)
        if size >= limit:
            break
    return "\n\n".join(sections)[:limit]


def fallback_profile(seed: Seed, evidence: str) -> CompanyProfile:
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(evidence)]
    keywords = [token for token, _count in Counter(token for token in tokens if token not in STOPWORDS).most_common(18)]
    category = (seed.category or "").strip()
    query = category or " ".join(keywords[:3]) or (seed.business_name or "local service business")
    summary = " ".join(evidence.split())[:900]
    return CompanyProfile(
        summary=summary,
        industry=category,
        services=[category] if category else [],
        service_area=[value for value in [seed.city, seed.state] if value],
        keywords=keywords,
        discovery_queries=[query],
    )


def normalize_profile(profile: CompanyProfile) -> CompanyProfile:
    data = profile.model_dump()
    for key, value in data.items():
        if isinstance(value, list):
            data[key] = unique_phrases(value, limit=18)
        elif isinstance(value, str):
            data[key] = " ".join(value.split())[:1200]
    data["discovery_queries"] = unique_phrases(data["discovery_queries"], limit=5)
    return CompanyProfile.model_validate(data)


def unique_phrases(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = " ".join(str(value).strip().lower().split())[:100]
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def merge_profiles(profiles: list[CompanyProfile]) -> CompanyProfile:
    if not profiles:
        return CompanyProfile()
    return CompanyProfile(
        summary=" ".join(profile.summary for profile in profiles if profile.summary)[:1800],
        industry=most_common_text(profile.industry for profile in profiles),
        services=merge_lists(profile.services for profile in profiles),
        customer_types=merge_lists(profile.customer_types for profile in profiles),
        business_model=merge_lists(profile.business_model for profile in profiles),
        specialties=merge_lists(profile.specialties for profile in profiles),
        service_area=merge_lists(profile.service_area for profile in profiles),
        keywords=merge_lists(profile.keywords for profile in profiles),
        discovery_queries=merge_lists((profile.discovery_queries for profile in profiles), limit=6),
    )


def merge_lists(groups, limit: int = 18) -> list[str]:
    return [value for value, _count in Counter(value for group in groups for value in group).most_common(limit)]


def most_common_text(values) -> str:
    clean = [value for value in values if value]
    return Counter(clean).most_common(1)[0][0] if clean else ""


def profile_hash(profile: CompanyProfile) -> str:
    return hashlib.sha256(profile.canonical_text().encode("utf-8")).hexdigest()

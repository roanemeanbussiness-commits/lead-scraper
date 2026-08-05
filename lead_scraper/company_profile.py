from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from urllib.parse import urlparse

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
    year_founded: str = ""
    employee_size: str = ""
    headquarters: str = ""
    technologies: list[str] = Field(default_factory=list)
    social_channels: list[str] = Field(default_factory=list)
    linkedin_url: str = ""
    hiring_departments: list[str] = Field(default_factory=list)
    ecommerce: bool = False
    careers_active: bool = False

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
            f"Founded: {self.year_founded}",
            f"Employee size: {self.employee_size}",
            f"Headquarters: {self.headquarters}",
            f"Technologies: {', '.join(self.technologies)}",
            f"Social channels: {', '.join(self.social_channels)}",
            f"Hiring: {', '.join(self.hiring_departments)}",
            f"Ecommerce: {'yes' if self.ecommerce else ''}",
            f"Careers active: {'yes' if self.careers_active else ''}",
        ]
        return "\n".join(part for part in parts if not part.endswith(": "))


def profile_company(seed: Seed, pages: list[CrawledPage], use_ai: bool = True) -> CompanyProfile:
    evidence = website_evidence(pages)
    if not evidence:
        return fallback_profile(seed, "", pages)
    if not use_ai or not get_openai_api_key():
        return fallback_profile(seed, evidence, pages)

    observed = detect_public_signals(pages)
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
        "deterministic_observations": observed,
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
                                "year_founded": {"type": "string"},
                                "employee_size": {"type": "string"},
                                "headquarters": {"type": "string"},
                                "technologies": {"type": "array", "items": {"type": "string"}},
                                "social_channels": {"type": "array", "items": {"type": "string"}},
                                "linkedin_url": {"type": "string"},
                                "hiring_departments": {"type": "array", "items": {"type": "string"}},
                                "ecommerce": {"type": "boolean"},
                                "careers_active": {"type": "boolean"},
                            },
                            "required": [
                                "summary", "industry", "services", "customer_types", "business_model",
                                "specialties", "service_area", "keywords", "discovery_queries",
                                "year_founded", "employee_size", "headquarters", "technologies",
                                "social_channels", "linkedin_url", "hiring_departments", "ecommerce", "careers_active",
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
        profile.technologies = unique_phrases(profile.technologies + observed["technologies"], limit=24)
        profile.social_channels = unique_phrases(profile.social_channels + observed["social_channels"], limit=12)
        profile.linkedin_url = observed["linkedin_url"] or profile.linkedin_url
        profile.ecommerce = profile.ecommerce or observed["ecommerce"]
        profile.careers_active = profile.careers_active or observed["careers_active"]
        return normalize_profile(profile)
    except Exception:
        return fallback_profile(seed, evidence, pages)


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


def fallback_profile(seed: Seed, evidence: str, pages: list[CrawledPage] | None = None) -> CompanyProfile:
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(evidence)]
    keywords = [token for token, _count in Counter(token for token in tokens if token not in STOPWORDS).most_common(18)]
    category = (seed.category or "").strip()
    query = category or " ".join(keywords[:3]) or (seed.business_name or "local service business")
    summary = " ".join(evidence.split())[:900]
    observed = detect_public_signals(pages or [])
    return CompanyProfile(
        summary=summary,
        industry=category,
        services=[category] if category else [],
        service_area=[value for value in [seed.city, seed.state] if value],
        keywords=keywords,
        discovery_queries=[query],
        technologies=observed["technologies"],
        social_channels=observed["social_channels"],
        linkedin_url=observed["linkedin_url"],
        ecommerce=observed["ecommerce"],
        careers_active=observed["careers_active"],
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
        year_founded=most_common_text(profile.year_founded for profile in profiles),
        employee_size=most_common_text(profile.employee_size for profile in profiles),
        headquarters=most_common_text(profile.headquarters for profile in profiles),
        technologies=merge_lists((profile.technologies for profile in profiles), limit=24),
        social_channels=merge_lists((profile.social_channels for profile in profiles), limit=12),
        hiring_departments=merge_lists((profile.hiring_departments for profile in profiles), limit=24),
        ecommerce=any(profile.ecommerce for profile in profiles),
        careers_active=any(profile.careers_active for profile in profiles),
    )


def merge_lists(groups, limit: int = 18) -> list[str]:
    return [value for value, _count in Counter(value for group in groups for value in group).most_common(limit)]


def most_common_text(values) -> str:
    clean = [value for value in values if value]
    return Counter(clean).most_common(1)[0][0] if clean else ""


def profile_hash(profile: CompanyProfile) -> str:
    return hashlib.sha256(profile.canonical_text().encode("utf-8")).hexdigest()


TECHNOLOGY_SIGNATURES = {
    "wordpress": ("wp-content", "wp-includes", "wordpress"),
    "shopify": ("cdn.shopify.com", "shopify.theme", "myshopify.com"),
    "hubspot": ("js.hs-scripts.com", "hubspotutk", "hsforms.net"),
    "google analytics": ("googletagmanager.com", "google-analytics.com", "gtag("),
    "meta pixel": ("connect.facebook.net", "fbq("),
    "wix": ("static.wixstatic.com", "wix.com"),
    "squarespace": ("static1.squarespace.com", "squarespace.com"),
    "webflow": ("webflow.js", "website-files.com"),
    "cloudflare": ("cdnjs.cloudflare.com", "cloudflareinsights.com"),
    "mailchimp": ("chimpstatic.com", "list-manage.com"),
    "stripe": ("js.stripe.com", "stripe.com/v3"),
    "servicetitan": ("servicetitan.com", "schedule.engine"),
}

SOCIAL_HOSTS = {
    "linkedin.com": "linkedin",
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "x.com": "x",
    "twitter.com": "x",
}


def detect_public_signals(pages: list[CrawledPage]) -> dict[str, object]:
    html = "\n".join(page.html for page in pages).lower()
    technologies = [
        name for name, signatures in TECHNOLOGY_SIGNATURES.items()
        if any(signature in html for signature in signatures)
    ]
    social_channels: list[str] = []
    linkedin_urls: list[str] = []
    for match in re.findall(r"https?://[^\s\"'<>]+", html):
        host = (urlparse(match).hostname or "").lower().removeprefix("www.")
        for social_host, label in SOCIAL_HOSTS.items():
            if host == social_host or host.endswith(f".{social_host}"):
                social_channels.append(label)
                if label == "linkedin" and "/company/" in match:
                    linkedin_urls.append(match.rstrip("/.,);"))
    ecommerce = any(signal in html for signal in ("add to cart", "shopping cart", "checkout", "product-price"))
    careers_active = any(
        signal in html
        for signal in ("/careers", "/jobs", "job opening", "join our team", "we are hiring", "now hiring")
    )
    return {
        "technologies": unique_phrases(technologies, limit=24),
        "social_channels": unique_phrases(social_channels, limit=12),
        "linkedin_url": linkedin_urls[0] if linkedin_urls else "",
        "ecommerce": ecommerce,
        "careers_active": careers_active,
    }

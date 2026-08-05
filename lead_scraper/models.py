from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class Seed(BaseModel):
    url: HttpUrl
    place_id: str | None = None
    business_name: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    category: str | None = None
    lookalike_query_id: str | None = None
    lookalike_score: float = 0.0
    semantic_score: float = 0.0
    profile_score: float = 0.0
    lexical_score: float = 0.0
    negative_penalty: float = 0.0
    similarity_reasons: str | None = None
    reference_domains: str | None = None
    company_summary: str | None = None
    technologies: str | None = None
    social_channels: str | None = None
    careers_active: bool = False
    ecommerce: bool = False
    year_founded: str | None = None
    employee_size: str | None = None
    headquarters: str | None = None
    linkedin_url: str | None = None
    industry_tags: str | None = None


class Lead(BaseModel):
    email: str
    possible_owner: str | None = None
    owner_role: str | None = None
    owner_evidence: str | None = None
    owner_source_url: str | None = None
    owner_confidence: int = 0
    custom_opener: str | None = None
    place_id: str | None = None
    domain: str
    source_url: str
    business_name: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    category: str | None = None
    blue_collar_signals: str = ""
    texas_signals: str = ""
    confidence: int = 0
    lookalike_query_id: str | None = None
    lookalike_score: float = 0.0
    semantic_score: float = 0.0
    profile_score: float = 0.0
    lexical_score: float = 0.0
    negative_penalty: float = 0.0
    similarity_reasons: str | None = None
    reference_domains: str | None = None
    company_summary: str | None = None
    technologies: str | None = None
    social_channels: str | None = None
    careers_active: bool = False
    ecommerce: bool = False
    year_founded: str | None = None
    employee_size: str | None = None
    headquarters: str | None = None
    linkedin_url: str | None = None
    linkedin_profile_url: str | None = None
    decision_maker_search_url: str | None = None
    industry_tags: str | None = None

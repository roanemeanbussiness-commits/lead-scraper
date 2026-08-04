from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class Seed(BaseModel):
    url: HttpUrl
    business_name: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    category: str | None = None


class Lead(BaseModel):
    email: str
    possible_owner: str | None = None
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

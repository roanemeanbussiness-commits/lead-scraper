from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .ai_enrichment import openai_configured
from .company_catalog import CompanyCatalog
from .crawler import UnsafeURL, domain_of, validate_public_url
from .dashboard import render_dashboard
from .exporter import export_direct_leads, read_rows
from .google_places import (
    google_places_configured,
    keyword_discovery_queries,
    search_google_places_queries,
)
from .lookalike import LookalikeFilters, find_lookalikes, ranked_seed
from .jobs import JobManager
from .pipeline import run_pipeline

app = FastAPI(title="8-Thon Intelligence Lead Scraper")
LOOKALIKE_RUN_LOCK = Lock()
DEFAULT_JOB_OUTPUT = "/data/jobs" if os.name != "nt" and Path("/data").exists() else "data/jobs"
JOB_MANAGER = JobManager(Path(os.getenv("JOB_OUTPUT_PATH", DEFAULT_JOB_OUTPUT)))


class ScrapeRequest(BaseModel):
    query: str = ""
    location: str = "San Antonio, TX"
    urls: str = Field("", description="Optional website URLs, one per line.")
    city: str = "San Antonio"
    state: str = "TX"
    category: str = ""
    max_results: int = Field(20, ge=1, le=1000)
    target_type: str = "companies"
    target_count: int | None = Field(None, ge=1, le=1000)
    max_pages: int = Field(8, ge=1, le=15)
    dedupe: str = "email"
    verify_mx: bool = False
    dedupe_months: int = Field(12, ge=1, le=120)


class LookalikeRequest(BaseModel):
    reference_urls: str = Field(..., description="Ideal company website URLs, one per line.")
    negative_urls: str = Field("", description="Optional not-like company URLs, one per line.")
    location: str = "San Antonio, TX"
    city: str = "San Antonio"
    state: str = "TX"
    max_candidates: int = Field(160, ge=10, le=3000)
    max_results: int = Field(50, ge=1, le=1000)
    target_type: str = "companies"
    target_count: int | None = Field(None, ge=1, le=1000)
    max_pages: int = Field(6, ge=1, le=12)
    min_score: float = Field(45.0, ge=0, le=100)
    dedupe: str = "email"
    verify_mx: bool = False
    dedupe_months: int = Field(12, ge=1, le=120)
    matching_mode: str = "precise"
    industries_any: str = ""
    industries_none: str = ""
    keywords_any: str = ""
    keywords_all: str = ""
    keywords_none: str = ""
    technologies_any: str = ""
    technologies_all: str = ""
    technologies_none: str = ""
    tags_any: str = ""
    tags_none: str = "software, saas"
    require_hiring: bool = False
    ecommerce_only: bool = False
    require_owner: bool = False
    require_contact_email: bool = False
    decision_maker_roles: str = "owner, founder, president, ceo, principal, general manager"
    updated_within_months: int = Field(12, ge=1, le=120)


class FeedbackRequest(BaseModel):
    query_id: str = Field(..., min_length=8, max_length=64)
    domain: str = Field(..., min_length=3, max_length=255)
    label: str


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return render_dashboard(
        version=__version__,
        maps_configured=google_places_configured(),
        openai_configured=openai_configured(),
    )


@app.post("/api/jobs/lookalikes", status_code=202)
def start_lookalike_job(request: LookalikeRequest) -> dict[str, object]:
    try:
        job = JOB_MANAGER.submit(
            "lookalikes",
            lambda progress: execute_locked_lookalike_search(request, progress),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return job.snapshot()


def execute_locked_lookalike_search(
    request: LookalikeRequest,
    progress: Callable[[int, str, str], None],
) -> dict[str, object]:
    if not LOOKALIKE_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A lookalike search is already running.")
    try:
        return execute_lookalike_search(request, progress=progress)
    finally:
        LOOKALIKE_RUN_LOCK.release()


@app.post("/api/jobs/scrape", status_code=202)
def start_scrape_job(request: ScrapeRequest) -> dict[str, object]:
    try:
        job = JOB_MANAGER.submit("keyword", lambda progress: execute_scrape(request, progress=progress))
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return job.snapshot()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = JOB_MANAGER.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found.")
    return job.snapshot()


@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str):
    job = JOB_MANAGER.get(job_id)
    if not job or not job.download_path or not job.download_path.exists():
        raise HTTPException(status_code=404, detail="The CSV is not ready.")
    filename = "lookalike_leads.csv" if job.kind == "lookalikes" else "scraped_leads.csv"
    return FileResponse(job.download_path, media_type="text/csv", filename=filename)


@app.post("/api/lookalikes")
def lookalikes_from_dashboard(request: LookalikeRequest) -> dict[str, object]:
    if not LOOKALIKE_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A lookalike search is already running. Try again when it finishes.")
    try:
        return execute_lookalike_search(request)
    finally:
        LOOKALIKE_RUN_LOCK.release()


def execute_lookalike_search(
    request: LookalikeRequest,
    progress: Callable[[int, str, str], None] | None = None,
) -> dict[str, object]:
    reference_urls = parse_public_urls(request.reference_urls)
    negative_urls = parse_public_urls(request.negative_urls)
    reference_domains = [domain_of(url) for url in reference_urls]
    catalog_path = Path(os.getenv("COMPANY_CATALOG_PATH", "data/company_catalog.db"))
    target_type = validate_target_type(request.target_type)
    target_count = request.target_count or request.max_results
    result_goal = target_count if target_type == "companies" else min(1000, max(100, target_count * 6))
    candidate_goal = min(3000, max(request.max_candidates, result_goal * 2))

    try:
        filters = LookalikeFilters(
            matching_mode=request.matching_mode,
            industries_any=tuple(parse_filter_values(request.industries_any)),
            industries_none=tuple(parse_filter_values(request.industries_none)),
            keywords_any=tuple(parse_filter_values(request.keywords_any)),
            keywords_all=tuple(parse_filter_values(request.keywords_all)),
            keywords_none=tuple(parse_filter_values(request.keywords_none)),
            technologies_any=tuple(parse_filter_values(request.technologies_any)),
            technologies_all=tuple(parse_filter_values(request.technologies_all)),
            technologies_none=tuple(parse_filter_values(request.technologies_none)),
            tags_any=tuple(parse_filter_values(request.tags_any)),
            tags_none=tuple(parse_filter_values(request.tags_none)),
            require_hiring=request.require_hiring,
            ecommerce_only=request.ecommerce_only,
            updated_within_months=request.updated_within_months,
        )
        search = find_lookalikes(
            reference_urls=reference_urls,
            negative_urls=negative_urls,
            location=request.location,
            city=request.city,
            state=request.state,
            max_candidates=candidate_goal,
            max_results=result_goal,
            max_pages=request.max_pages,
            min_score=request.min_score,
            catalog_path=catalog_path,
            filters=filters,
            progress=progress,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Lookalike discovery failed: {exc}") from exc

    seeds = [ranked_seed(item, search.query_id, reference_domains) for item in search.ranked]
    contacts: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        seeds_path = tmp_path / "lookalike_seeds.csv"
        raw_path = tmp_path / "lookalike_leads_raw.csv"
        direct_path = tmp_path / "lookalike_leads.csv"
        history_path = Path(os.getenv("LEAD_HISTORY_PATH", "data/lead_history.db"))

        if seeds:
            write_seed_rows(seeds_path, seeds)
            raw_count = run_pipeline(
                seeds_path=seeds_path,
                out_path=raw_path,
                history_path=history_path,
                dedupe=request.dedupe,
                max_pages=request.max_pages,
                timeout=12.0,
                pages_by_domain=search.pages_by_domain,
                contact_sink=contacts,
                progress=(
                    (lambda value, stage, message: progress(80 + round(value * 0.18), stage, message))
                    if progress else None
                ),
                history_months=request.dedupe_months,
            )
            direct_count, _dropped = export_direct_leads(
                raw_path, direct_path, verify_mx=request.verify_mx
            )
            csv_text = direct_path.read_text(encoding="utf-8")
            direct_rows = read_rows(direct_path)
        else:
            raw_count = 0
            direct_count = 0
            csv_text = ""
            direct_rows = []

    direct_by_domain = {
        domain_of(row.get("website") or ""): row
        for row in direct_rows
        if domain_of(row.get("website") or "")
    }
    contacts_by_domain = {str(contact.get("domain", "")): contact for contact in contacts}
    for contact in contacts:
        direct = direct_by_domain.get(str(contact.get("domain", "")), {})
        if direct:
            contact["verified_email"] = direct.get("verified_email", contact.get("verified_email", ""))
            contact["owner_name"] = direct.get("owner_name", contact.get("owner_name", ""))
            contact["owner_role"] = direct.get("owner_role", contact.get("owner_role", ""))
            contacts_by_domain[str(contact.get("domain", ""))] = contact
    contacts = filter_contacts(contacts, request)
    matches = [match_payload(item, contacts_by_domain.get(item.company.domain, {})) for item in search.ranked]
    return {
        "query_id": search.query_id,
        "candidates_discovered": search.candidates_discovered,
        "catalog_size": search.catalog_size,
        "match_count": len(search.ranked),
        "raw_count": raw_count,
        "direct_count": direct_count,
        "discovery_queries": search.discovery_queries,
        "filtered_count": search.filtered_count,
        "usage": search.usage,
        "matches": matches,
        "contacts": contacts,
        "target_type": target_type,
        "target_count": target_count,
        "target_achieved": len(search.ranked) if target_type == "companies" else direct_count,
        "target_met": (len(search.ranked) if target_type == "companies" else direct_count) >= target_count,
        "csv": csv_text,
    }


@app.post("/api/lookalike-feedback")
def record_lookalike_feedback(request: FeedbackRequest) -> dict[str, str]:
    if request.label not in {"fit", "not_fit"}:
        raise HTTPException(status_code=400, detail="Feedback must be fit or not_fit.")
    domain = request.domain.strip().lower().removeprefix("www.")
    if not domain or "/" in domain or " " in domain:
        raise HTTPException(status_code=400, detail="Feedback domain is invalid.")
    catalog = CompanyCatalog(Path(os.getenv("COMPANY_CATALOG_PATH", "data/company_catalog.db")))
    catalog.record_feedback(request.query_id, domain, request.label)
    return {"status": "saved", "query_id": request.query_id, "domain": domain, "label": request.label}


@app.post("/api/scrape")
def scrape_from_dashboard(request: ScrapeRequest) -> dict[str, object]:
    return execute_scrape(request)


def execute_scrape(
    request: ScrapeRequest,
    progress: Callable[[int, str, str], None] | None = None,
) -> dict[str, object]:
    seeds: list[dict[str, str]] = []
    notes: list[str] = []
    contacts: list[dict[str, object]] = []
    target_type = validate_target_type(request.target_type)
    target_count = request.target_count or request.max_results
    discovery_goal = target_count if target_type == "companies" else min(1000, max(100, target_count * 6))

    if request.query.strip():
        if google_places_configured():
            try:
                if progress:
                    progress(12, "Discovery", "Searching Google Places")
                queries = keyword_discovery_queries(request.query, discovery_goal)
                places = search_google_places_queries(queries, request.location, discovery_goal)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Google Places search failed: {exc}") from exc
            seeds.extend(
                {
                    "url": normalize_seed_url(place.website),
                    "place_id": place.place_id,
                    "business_name": place.business_name,
                    "phone": place.phone,
                    "address": place.address,
                    "city": request.city,
                    "state": request.state,
                    "category": place.category or request.category or request.query,
                }
                for place in places
            )
        else:
            notes.append("GOOGLE_MAPS_API_KEY is not configured, so only pasted websites were scraped.")

    for url in [line.strip() for line in request.urls.splitlines() if line.strip()]:
        normalized_url = normalize_seed_url(url)
        try:
            validate_public_url(normalized_url)
        except UnsafeURL as exc:
            raise HTTPException(status_code=400, detail=f"Unsafe or invalid website URL: {exc}") from exc
        seeds.append(
            {
                "url": normalized_url,
                "place_id": "",
                "business_name": "",
                "phone": "",
                "address": "",
                "city": request.city,
                "state": request.state,
                "category": request.category or request.query,
            }
        )

    seeds = dedupe_seed_urls(seeds)
    if not seeds:
        return {
            "discovery_count": 0,
            "raw_count": 0,
            "direct_count": 0,
            "matches": [],
            "contacts": [],
            "target_type": target_type,
            "target_count": target_count,
            "target_achieved": 0,
            "target_met": False,
            "csv": "",
            "preview": "No businesses were found. Add GOOGLE_MAPS_API_KEY or paste website URLs.",
        }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        seeds_path = tmp_path / "seeds.csv"
        raw_path = tmp_path / "leads.csv"
        direct_path = tmp_path / "scraped_leads.csv"
        write_seed_rows(seeds_path, seeds)
        try:
            raw_count = run_pipeline(
                seeds_path=seeds_path,
                out_path=raw_path,
                history_path=Path(os.getenv("LEAD_HISTORY_PATH", "data/lead_history.db")),
                dedupe=request.dedupe,
                max_pages=request.max_pages,
                timeout=12.0,
                contact_sink=contacts,
                progress=(
                    (lambda value, stage, message: progress(20 + round(value * 0.78), stage, message))
                    if progress else None
                ),
                history_months=request.dedupe_months,
            )
            direct_count, _dropped = export_direct_leads(
                raw_path, direct_path, verify_mx=request.verify_mx
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        csv_text = direct_path.read_text(encoding="utf-8")
        preview = csv_text if direct_count <= 5 else preview_csv(direct_path, limit=5)

    if notes:
        preview = "\n".join(notes) + "\n\n" + preview
    return {
        "discovery_count": len(seeds),
        "raw_count": raw_count,
        "direct_count": direct_count,
        "csv": csv_text,
        "preview": preview,
        "contacts": contacts,
        "matches": [company_from_contact(contact) for contact in contacts],
        "target_type": target_type,
        "target_count": target_count,
        "target_achieved": len(seeds) if target_type == "companies" else direct_count,
        "target_met": (len(seeds) if target_type == "companies" else direct_count) >= target_count,
    }


@app.get("/api/status")
def status() -> dict[str, str]:
    return {
        "service": "8-Thon Intelligence Lead Scraper",
        "version": __version__,
        "status": "ok",
        "google_maps": "configured" if google_places_configured() else "missing",
        "openai": "configured" if openai_configured() else "missing",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def match_payload(item, contact: dict[str, str]) -> dict[str, object]:
    profile = item.company.profile
    return {
        "business_name": item.company.business_name,
        "domain": item.company.domain,
        "website": item.company.url,
        "score": item.score,
        "semantic_score": item.semantic_score,
        "profile_score": item.profile_score,
        "reasons": "; ".join(item.reasons),
        "grade": score_grade(item.score),
        "industry": profile.industry or item.company.category,
        "summary": profile.summary[:240],
        "technologies": profile.technologies[:5],
        "social_channels": profile.social_channels,
        "linkedin_url": profile.linkedin_url,
        "industry_tags": [
            value.strip() for value in str(contact.get("industry_tags", "")).split(";") if value.strip()
        ] or [profile.industry or item.company.category],
        "careers_active": profile.careers_active,
        "ecommerce": profile.ecommerce,
        "phone": item.company.phone,
        "location": ", ".join(value for value in [item.company.city, item.company.state] if value),
        "owner_name": contact.get("owner_name", ""),
        "verified_email": contact.get("verified_email", ""),
        "linkedin_profile_url": contact.get("linkedin_profile_url", ""),
        "decision_maker_search_url": contact.get("decision_maker_search_url", ""),
    }


def write_seed_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def preview_csv(path: Path, limit: int) -> str:
    rows = read_rows(path)
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows[:limit])
    return output.getvalue()


def dedupe_seed_urls(seeds: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for seed in seeds:
        key = seed["url"].strip().lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            deduped.append(seed)
    return deduped


def normalize_seed_url(url: str) -> str:
    value = url.strip()
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


def parse_public_urls(value: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in value.splitlines():
        if not line.strip():
            continue
        try:
            valid = validate_public_url(normalize_seed_url(line))
        except UnsafeURL as exc:
            raise HTTPException(status_code=400, detail=f"Unsafe or invalid website URL: {exc}") from exc
        key = domain_of(valid)
        if key and key not in seen:
            seen.add(key)
            urls.append(valid)
    return urls


def parse_filter_values(value: str) -> list[str]:
    return list(
        dict.fromkeys(
            item.strip().lower()
            for line in value.splitlines()
            for item in line.split(",")
            if item.strip()
        )
    )


def score_grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    return "C"


def validate_target_type(value: str) -> str:
    clean = value.strip().lower()
    if clean not in {"companies", "emails"}:
        raise HTTPException(status_code=400, detail="Target type must be companies or emails.")
    return clean


def filter_contacts(contacts: list[dict[str, object]], request: LookalikeRequest) -> list[dict[str, object]]:
    roles = parse_filter_values(request.decision_maker_roles)
    output: list[dict[str, object]] = []
    for contact in contacts:
        owner_name = str(contact.get("owner_name", ""))
        owner_role = str(contact.get("owner_role", "")).lower()
        if request.require_owner and not owner_name:
            continue
        if request.require_contact_email and not contact.get("verified_email"):
            continue
        if roles and owner_role and not any(role in owner_role for role in roles):
            continue
        output.append(contact)
    return output


def company_from_contact(contact: dict[str, object]) -> dict[str, object]:
    tags = [value.strip() for value in str(contact.get("industry_tags", "")).split(";") if value.strip()]
    return {
        **contact,
        "score": 0,
        "industry_tags": tags,
        "technologies": [],
        "careers_active": False,
        "ecommerce": False,
    }

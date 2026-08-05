from __future__ import annotations

import csv
import io
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Callable
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from . import __version__
from .dashboard import render_dashboard
from .jobs import JobManager
from .ocean import (
    OceanAPIError,
    OceanClient,
    OceanLeadStore,
    ocean_configured,
    ocean_webhook_base_url,
)


app = FastAPI(title="8-Thon Intelligence Ocean Lead Scraper")
SEARCH_LOCK = Lock()
DEFAULT_DATA_PATH = Path("/data") if os.name != "nt" and Path("/data").exists() else Path("data")
JOB_MANAGER = JobManager(Path(os.getenv("JOB_OUTPUT_PATH", str(DEFAULT_DATA_PATH / "jobs"))))
OCEAN_STORE = OceanLeadStore(
    Path(os.getenv("OCEAN_STORE_PATH", str(DEFAULT_DATA_PATH / "ocean_leads.db")))
)


class OceanSearchRequest(BaseModel):
    mode: str = "lookalike"
    reference_domains: str = ""
    negative_domains: str = ""
    query: str = ""
    keywords_any: str = ""
    keywords_all: str = ""
    keywords_none: str = "software, saas"
    industries_any: str = ""
    industries_none: str = ""
    technologies_any: str = ""
    company_sizes: str = ""
    revenues: str = ""
    country: str = "us"
    city: str = "San Antonio"
    state: str = "TX"
    ecommerce: str = "any"
    year_founded_from: int | None = Field(None, ge=0, le=2100)
    year_founded_to: int | None = Field(None, ge=0, le=2100)
    target_type: str = "companies"
    target_count: int = Field(100, ge=1, le=1000)
    find_contacts: bool = True
    reveal_emails: bool = True
    people_per_company: int = Field(1, ge=1, le=10)
    seniorities: str = "Owner, Founder, C-Level, Partner, VP, Head, Director"
    departments: str = ""
    job_titles: str = ""
    dedupe_months: int = Field(12, ge=1, le=120)


class LookalikeRequest(OceanSearchRequest):
    reference_urls: str = ""
    negative_urls: str = ""
    location: str = "San Antonio, TX"
    max_candidates: int = Field(160, ge=10, le=3000)
    max_results: int = Field(50, ge=1, le=1000)
    max_pages: int = Field(6, ge=1, le=15)
    min_score: float = Field(45.0, ge=0, le=100)
    dedupe: str = "email"
    verify_mx: bool = False
    matching_mode: str = "precise"
    technologies_all: str = ""
    technologies_none: str = ""
    tags_any: str = ""
    tags_none: str = "software, saas"
    require_hiring: bool = False
    ecommerce_only: bool = False
    require_owner: bool = False
    require_contact_email: bool = False
    decision_maker_roles: str = ""
    updated_within_months: int = Field(12, ge=1, le=120)


class ScrapeRequest(OceanSearchRequest):
    location: str = "San Antonio, TX"
    urls: str = ""
    category: str = ""
    max_results: int = Field(20, ge=1, le=1000)
    max_pages: int = Field(8, ge=1, le=15)
    dedupe: str = "email"
    verify_mx: bool = False


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(
        render_dashboard(version=__version__, ocean_configured=ocean_configured()),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.post("/api/jobs/ocean", status_code=202)
def start_ocean_job(request: OceanSearchRequest) -> dict[str, object]:
    return submit_search(request)


@app.post("/api/jobs/lookalikes", status_code=202)
def start_lookalike_job(request: LookalikeRequest) -> dict[str, object]:
    return submit_search(lookalike_compatibility_request(request))


@app.post("/api/jobs/scrape", status_code=202)
def start_scrape_job(request: ScrapeRequest) -> dict[str, object]:
    return submit_search(scrape_compatibility_request(request))


def submit_search(request: OceanSearchRequest) -> dict[str, object]:
    try:
        job = JOB_MANAGER.submit(
            "ocean",
            lambda progress: execute_locked_ocean_search(request, progress),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return job.snapshot()


def execute_locked_ocean_search(
    request: OceanSearchRequest,
    progress: Callable[[int, str, str], None],
) -> dict[str, object]:
    if not SEARCH_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="An Ocean.io search is already running.")
    try:
        return execute_ocean_search(request, progress)
    finally:
        SEARCH_LOCK.release()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    job = JOB_MANAGER.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found.")
    return JSONResponse(job.snapshot(), headers={"Cache-Control": "no-store"})


@app.get("/api/jobs/{job_id}/download")
def download_job(job_id: str):
    job = JOB_MANAGER.get(job_id)
    if not job or not job.download_path or not job.download_path.exists():
        raise HTTPException(status_code=404, detail="The CSV is not ready.")
    return FileResponse(job.download_path, media_type="text/csv", filename="ocean_leads.csv")


@app.post("/api/ocean/search")
def ocean_search(request: OceanSearchRequest) -> dict[str, object]:
    if not SEARCH_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="An Ocean.io search is already running.")
    try:
        return execute_ocean_search(request)
    finally:
        SEARCH_LOCK.release()


@app.post("/api/lookalikes")
def lookalikes_from_dashboard(request: LookalikeRequest) -> dict[str, object]:
    return ocean_search(lookalike_compatibility_request(request))


@app.post("/api/scrape")
def scrape_from_dashboard(request: ScrapeRequest) -> dict[str, object]:
    return ocean_search(scrape_compatibility_request(request))


@app.post("/api/webhooks/ocean/emails/{callback_token}")
def receive_ocean_emails(callback_token: str, payload: dict[str, object]) -> dict[str, object]:
    saved = OCEAN_STORE.save_reveal(callback_token, payload)
    if not saved:
        raise HTTPException(status_code=404, detail="Unknown or empty Ocean reveal callback.")
    return {"status": "accepted", "results": saved}


@app.get("/api/ocean/credits")
def ocean_credits() -> dict[str, object]:
    try:
        return OceanClient().credit_balance()
    except OceanAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def execute_ocean_search(
    request: OceanSearchRequest,
    progress: Callable[[int, str, str], None] | None = None,
    *,
    client: OceanClient | None = None,
    store: OceanLeadStore | None = None,
) -> dict[str, object]:
    report = progress or (lambda _value, _stage, _message: None)
    if request.mode not in {"lookalike", "filters"}:
        raise HTTPException(status_code=400, detail="Search mode must be lookalike or filters.")
    if request.target_type not in {"companies", "emails"}:
        raise HTTPException(status_code=400, detail="Target type must be companies or emails.")

    ocean = client or OceanClient()
    history = store or OCEAN_STORE
    references = parse_domains(request.reference_domains)
    negatives = parse_domains(request.negative_domains)
    if request.mode == "lookalike" and not references:
        raise HTTPException(status_code=400, detail="Add at least one reference company domain.")

    company_goal = request.target_count
    if request.target_type == "emails":
        company_goal = min(3000, max(request.target_count, math.ceil(request.target_count / 0.65)))

    try:
        companies_filters = build_company_filters(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    excluded_domains = sorted(
        set(negatives).union(history.recent_domains(request.dedupe_months))
    )
    report(8, "Ocean companies", f"Searching for {company_goal} matching companies")
    try:
        company_page = ocean.search_companies(
            size=company_goal,
            companies_filters=companies_filters,
            lookalike_domains=references if request.mode == "lookalike" else None,
            exclude_domains=excluded_domains,
        )
    except OceanAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    companies = dedupe_companies(company_page.records)[:company_goal]
    company_payloads = [company_payload(company) for company in companies]
    contacts: list[dict[str, object]] = []
    reveal_complete = True

    if request.find_contacts and companies:
        domains = [str(company.get("domain") or "") for company in company_payloads]
        people_goal = min(3000, max(request.target_count, len(domains) * request.people_per_company))
        people_filters = build_people_filters(request)
        recent_people = sorted(history.recent_people(request.dedupe_months))
        if recent_people:
            people_filters["excludePeopleIds"] = recent_people
        report(38, "Ocean people", "Finding owners and senior decision-makers")
        try:
            people_page = ocean.search_people(
                size=people_goal,
                people_filters=people_filters,
                companies_filters={"includeDomains": domains},
                people_per_company=request.people_per_company,
            )
        except OceanAPIError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        contacts = [person_payload(person) for person in dedupe_people(people_page.records)]

        if request.reveal_emails and contacts:
            report(60, "Ocean email reveal", "Requesting verified contact emails")
            reveal_complete = attach_revealed_emails(ocean, history, contacts, report)

    contact_by_domain: dict[str, dict[str, object]] = {}
    for contact in contacts:
        domain = str(contact.get("domain") or "").lower()
        current = contact_by_domain.get(domain)
        if current is None or (contact.get("verified_email") and not current.get("verified_email")):
            contact_by_domain[domain] = contact

    matches: list[dict[str, object]] = []
    for company in company_payloads:
        contact = contact_by_domain.get(str(company.get("domain") or "").lower(), {})
        merged = dict(company)
        merged.update(
            {
                "owner_name": contact.get("owner_name", ""),
                "owner_role": contact.get("owner_role", ""),
                "verified_email": contact.get("verified_email", ""),
                "email_status": contact.get("email_status", ""),
                "linkedin_profile_url": contact.get("linkedin_profile_url", ""),
            }
        )
        matches.append(merged)

    export_rows = build_export_rows(matches, contacts, request.target_type)
    history.record_exports(export_rows)
    csv_text = render_csv(export_rows)
    direct_count = sum(1 for contact in contacts if contact.get("verified_email"))
    achieved = len(matches) if request.target_type == "companies" else direct_count
    report(96, "Preparing export", f"Building CSV for {len(export_rows)} leads")
    return {
        "provider": "Ocean.io",
        "mode": request.mode,
        "match_count": len(matches),
        "discovery_count": len(matches),
        "contacts_count": len(contacts),
        "direct_count": direct_count,
        "ocean_total": company_page.total,
        "matches": matches,
        "contacts": contacts,
        "target_type": request.target_type,
        "target_count": request.target_count,
        "target_achieved": achieved,
        "target_met": achieved >= request.target_count,
        "reveal_complete": reveal_complete,
        "estimated_standard_credits": round((len(matches) + len(contacts)) * 0.2, 1),
        "estimated_email_credits": direct_count,
        "csv": csv_text,
    }


def execute_lookalike_search(
    request: LookalikeRequest,
    progress: Callable[[int, str, str], None] | None = None,
) -> dict[str, object]:
    return execute_ocean_search(lookalike_compatibility_request(request), progress)


def execute_scrape(
    request: ScrapeRequest,
    progress: Callable[[int, str, str], None] | None = None,
) -> dict[str, object]:
    return execute_ocean_search(scrape_compatibility_request(request), progress)


def attach_revealed_emails(
    client: OceanClient,
    store: OceanLeadStore,
    contacts: list[dict[str, object]],
    progress: Callable[[int, str, str], None],
) -> bool:
    people = [str(contact.get("person_id") or "") for contact in contacts]
    people = [person_id for person_id in people if person_id]
    if not people:
        return True
    batches: list[tuple[str, list[str]]] = []
    for offset in range(0, len(people), 500):
        person_ids = people[offset : offset + 500]
        token = store.new_reveal(person_ids)
        callback_url = f"{ocean_webhook_base_url()}/api/webhooks/ocean/emails/{token}"
        try:
            client.reveal_emails(person_ids, callback_url)
        except OceanAPIError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        batches.append((token, person_ids))

    timeout = max(1.0, float(os.getenv("OCEAN_REVEAL_WAIT_SECONDS", "120")))
    email_results: dict[str, dict[str, str]] = {}
    complete = True
    with ThreadPoolExecutor(max_workers=min(6, len(batches))) as executor:
        futures = {
            executor.submit(
                store.wait_for_reveal,
                token,
                timeout,
                lambda received, expected: progress(
                    min(92, 65 + round(27 * received / max(1, expected))),
                    "Ocean email reveal",
                    f"Received {received} of {expected} email checks",
                ),
            ): person_ids
            for token, person_ids in batches
        }
        for future in as_completed(futures):
            results = future.result()
            email_results.update(results)
            complete = complete and len(results) >= len(set(futures[future]))

    for contact in contacts:
        result = email_results.get(str(contact.get("person_id") or ""), {})
        contact["verified_email"] = result.get("address", "")
        contact["email_status"] = result.get("status", "")
    return complete


def build_company_filters(request: OceanSearchRequest) -> dict[str, object]:
    filters: dict[str, object] = {}
    sizes = parse_values(request.company_sizes)
    if sizes:
        filters["companySizes"] = sizes
    revenues = normalize_revenues(request.revenues)
    if revenues:
        filters["revenues"] = revenues
    industries = parse_values(request.industries_any)
    excluded_industries = parse_values(request.industries_none)
    if industries:
        filters["industries"] = {
            "industries": industries,
            "mode": "anyOf",
        }
    if excluded_industries:
        filters["excludeIndustries"] = excluded_industries
    keywords_any = parse_values(request.keywords_any or request.query)
    keywords_all = parse_values(request.keywords_all)
    keywords_none = parse_values(request.keywords_none)
    if keywords_any or keywords_all or keywords_none:
        filters["keywords"] = compact_filter(
            {"anyOf": keywords_any, "allOf": keywords_all, "noneOf": keywords_none}
        )
    technologies = parse_values(request.technologies_any)
    if technologies:
        filters["technologies"] = {"apps": {"anyOf": technologies}}
    locations: dict[str, object] = {}
    country = request.country.strip().lower()
    state = request.state.strip().upper()
    city = request.city.strip()
    if country:
        locations["includeCountries"] = [country]
    if state:
        locations["includeRegions"] = [{"country": country or "us", "abbreviation": state}]
    if city:
        city_filter: dict[str, object] = {"city": city, "country": country or "us"}
        if state:
            city_filter["region"] = {"country": country or "us", "abbreviation": state}
        locations["includeCities"] = [city_filter]
    if locations:
        filters["primaryLocations"] = locations
    if request.ecommerce in {"include", "exclude"}:
        filters["ecommerce"] = request.ecommerce == "include"
    founded = compact_filter({"from": request.year_founded_from, "to": request.year_founded_to})
    if founded:
        filters["yearFounded"] = founded
    return filters


def build_people_filters(request: OceanSearchRequest) -> dict[str, object]:
    filters: dict[str, object] = {}
    seniorities = parse_values(request.seniorities)
    departments = parse_values(request.departments)
    job_titles = parse_values(request.job_titles)
    if seniorities:
        filters["seniorities"] = seniorities
    if departments:
        filters["departments"] = departments
    if job_titles:
        filters["jobTitleKeywords"] = {"anyOf": job_titles}
    return filters


def company_payload(company: dict[str, object]) -> dict[str, object]:
    domain = clean_domain(company.get("domain") or company.get("website") or "")
    industries = string_list(company.get("industries") or company.get("industryCategories"))
    technologies = string_list(company.get("technologies"))
    location = location_text(
        company.get("primaryLocation") or company.get("headquarters") or company.get("location")
    )
    traffic = company.get("webTraffic")
    visits = traffic.get("visits") if isinstance(traffic, dict) else ""
    score = company.get("score") or company.get("lookalikeScore") or company.get("similarity") or 0
    try:
        numeric_score = float(score)
        if 0 < numeric_score <= 1:
            numeric_score *= 100
    except (TypeError, ValueError):
        numeric_score = 0.0
    return {
        "business_name": str(company.get("name") or company.get("companyName") or domain),
        "domain": domain,
        "website": f"https://{domain}" if domain else "",
        "score": round(numeric_score, 1),
        "grade": "Ocean match",
        "industry": industries[0] if industries else "",
        "industry_tags": industries,
        "technologies": technologies,
        "location": location,
        "company_size": str(company.get("companySize") or company.get("employeeRange") or ""),
        "people_count": company.get("employeeCountOcean") or company.get("employeeCountLinkedin") or "",
        "website_traffic": visits or "",
        "year_founded": company.get("yearFounded") or "",
        "linkedin_url": str(company.get("linkedinUrl") or company.get("linkedin") or ""),
        "phone": str(company.get("phone") or ""),
        "ocean_company_id": str(company.get("id") or company.get("oceanId") or ""),
        "summary": str(company.get("description") or company.get("shortDescription") or ""),
    }


def person_payload(person: dict[str, object]) -> dict[str, object]:
    domain = clean_domain(person.get("domain") or person.get("companyDomain") or "")
    company = person.get("company")
    company_name = ""
    if isinstance(company, dict):
        domain = domain or clean_domain(company.get("domain") or "")
        company_name = str(company.get("name") or "")
    return {
        "person_id": str(person.get("id") or person.get("oceanId") or ""),
        "owner_name": str(person.get("name") or person.get("fullName") or ""),
        "owner_role": str(person.get("jobTitle") or person.get("title") or ""),
        "seniorities": string_list(person.get("seniorities")),
        "departments": string_list(person.get("departments")),
        "domain": domain,
        "business_name": str(person.get("companyName") or company_name or domain),
        "linkedin_profile_url": str(person.get("linkedinUrl") or person.get("linkedin") or ""),
        "location": location_text(person.get("location") or person.get("country")),
        "phone": str(person.get("phone") or ""),
        "verified_email": "",
        "email_status": "",
        "source": "Ocean.io API",
    }


def build_export_rows(
    matches: list[dict[str, object]],
    contacts: list[dict[str, object]],
    target_type: str,
) -> list[dict[str, object]]:
    company_by_domain = {str(company.get("domain") or ""): company for company in matches}
    rows: list[dict[str, object]] = []
    for contact in contacts:
        if target_type == "emails" and not contact.get("verified_email"):
            continue
        company = company_by_domain.get(str(contact.get("domain") or ""), {})
        name = str(contact.get("owner_name") or "").strip()
        rows.append(
            {
                "business_name": company.get("business_name") or contact.get("business_name") or "",
                "owner_name": name,
                "first_name": name.split()[0] if name else "There",
                "owner_role": contact.get("owner_role") or "",
                "verified_email": contact.get("verified_email") or "",
                "email_status": contact.get("email_status") or "",
                "phone": contact.get("phone") or company.get("phone") or "",
                "website": company.get("website") or "",
                "domain": contact.get("domain") or company.get("domain") or "",
                "location": company.get("location") or contact.get("location") or "",
                "industry": company.get("industry") or "",
                "company_size": company.get("company_size") or "",
                "technologies": "; ".join(string_list(company.get("technologies"))),
                "linkedin_url": company.get("linkedin_url") or "",
                "linkedin_profile_url": contact.get("linkedin_profile_url") or "",
                "website_traffic": company.get("website_traffic") or "",
                "ocean_company_id": company.get("ocean_company_id") or "",
                "ocean_person_id": contact.get("person_id") or "",
                "person_id": contact.get("person_id") or "",
                "source": "Ocean.io API",
            }
        )
    if target_type == "companies":
        represented = {str(row.get("domain") or "") for row in rows}
        for company in matches:
            if str(company.get("domain") or "") in represented:
                continue
            rows.append(
                {
                    "business_name": company.get("business_name") or "",
                    "owner_name": "",
                    "first_name": "There",
                    "owner_role": "",
                    "verified_email": "",
                    "email_status": "",
                    "phone": company.get("phone") or "",
                    "website": company.get("website") or "",
                    "domain": company.get("domain") or "",
                    "location": company.get("location") or "",
                    "industry": company.get("industry") or "",
                    "company_size": company.get("company_size") or "",
                    "technologies": "; ".join(string_list(company.get("technologies"))),
                    "linkedin_url": company.get("linkedin_url") or "",
                    "linkedin_profile_url": "",
                    "website_traffic": company.get("website_traffic") or "",
                    "ocean_company_id": company.get("ocean_company_id") or "",
                    "ocean_person_id": "",
                    "person_id": "",
                    "source": "Ocean.io API",
                }
            )
    return rows


def render_csv(rows: list[dict[str, object]]) -> str:
    fieldnames = [
        "business_name",
        "owner_name",
        "first_name",
        "owner_role",
        "verified_email",
        "email_status",
        "phone",
        "website",
        "domain",
        "location",
        "industry",
        "company_size",
        "technologies",
        "linkedin_url",
        "linkedin_profile_url",
        "website_traffic",
        "ocean_company_id",
        "ocean_person_id",
        "source",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def lookalike_compatibility_request(request: LookalikeRequest) -> OceanSearchRequest:
    values = request.model_dump()
    values["mode"] = "lookalike"
    values["reference_domains"] = request.reference_domains or request.reference_urls
    values["negative_domains"] = request.negative_domains or request.negative_urls
    values["target_count"] = request.target_count or request.max_results
    values["keywords_none"] = request.keywords_none or request.tags_none
    values["ecommerce"] = "include" if request.ecommerce_only else request.ecommerce
    if request.decision_maker_roles:
        values["job_titles"] = request.decision_maker_roles
    return OceanSearchRequest.model_validate(values)


def scrape_compatibility_request(request: ScrapeRequest) -> OceanSearchRequest:
    values = request.model_dump()
    values["mode"] = "filters"
    values["reference_domains"] = request.reference_domains or request.urls
    values["keywords_any"] = request.keywords_any or request.query or request.category
    values["target_count"] = request.target_count or request.max_results
    return OceanSearchRequest.model_validate(values)


def parse_values(value: str) -> list[str]:
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


OCEAN_REVENUE_RANGES = (
    "0-1M",
    "1-10M",
    "10-50M",
    "50-100M",
    "100-500M",
    "500-1000M",
    ">1000M",
)


def normalize_revenues(value: str) -> list[str]:
    aliases = {
        "<1M": "0-1M",
        "UNDER1M": "0-1M",
        "0M-1M": "0-1M",
        "1M": "1-10M",
        "1M-10M": "1-10M",
        "10M": "10-50M",
        "10M-50M": "10-50M",
        "50M": "50-100M",
        "50M-100M": "50-100M",
        "100M": "100-500M",
        "100M-500M": "100-500M",
        "500M": "500-1000M",
        "500M-1000M": "500-1000M",
        "1000M": ">1000M",
        "1000M+": ">1000M",
        ">1B": ">1000M",
    }
    normalized: list[str] = []
    invalid: list[str] = []
    for raw in parse_values(value):
        item = (
            raw.upper()
            .replace("$", "")
            .replace(" ", "")
            .replace("–", "-")
            .replace("—", "-")
            .replace("MILLION", "M")
            .replace("BILLION", "B")
        )
        canonical = aliases.get(item, item)
        if canonical not in OCEAN_REVENUE_RANGES:
            invalid.append(raw)
        elif canonical not in normalized:
            normalized.append(canonical)
    if invalid:
        choices = ", ".join(OCEAN_REVENUE_RANGES)
        raise ValueError(
            f"Revenue range '{invalid[0]}' is invalid. Use one or more of: {choices}."
        )
    return normalized


def parse_domains(value: str) -> list[str]:
    domains: list[str] = []
    for item in parse_values(value):
        domain = clean_domain(item)
        if domain and domain not in domains:
            domains.append(domain)
    return domains


def clean_domain(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    return (parsed.hostname or "").removeprefix("www.")


def compact_filter(values: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value not in (None, "", [], {})}


def string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def location_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    region = value.get("region")
    region_name = ""
    if isinstance(region, dict):
        region_name = str(region.get("name") or region.get("abbreviation") or "")
    elif region:
        region_name = str(region)
    parts = [
        str(value.get("city") or ""),
        region_name,
        str(value.get("countryName") or value.get("country") or ""),
    ]
    return ", ".join(part for part in parts if part)


def dedupe_companies(companies: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for company in companies:
        domain = clean_domain(company.get("domain") or company.get("website") or "")
        if not domain or domain in seen:
            continue
        seen.add(domain)
        result.append(company)
    return result


def dedupe_people(people: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for person in people:
        identity = str(person.get("id") or person.get("oceanId") or person.get("linkedinUrl") or "")
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(person)
    return result


@app.get("/api/status")
def status() -> dict[str, str]:
    return {
        "service": "8-Thon Intelligence Ocean Lead Scraper",
        "version": __version__,
        "status": "ok",
        "provider": "Ocean.io",
        "ocean": "configured" if ocean_configured() else "missing",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

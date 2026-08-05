from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

import httpx


OCEAN_API_BASE = "https://api.ocean.io"
TOKEN_ENV_NAMES = (
    "OCEAN_API_TOKEN",
    "OCEANIO",
    "Oceanio",
    "OCEAN_IO_API_KEY",
    "OCEAN_API_KEY",
)


class OceanAPIError(RuntimeError):
    pass


def ocean_api_token() -> str:
    for name in TOKEN_ENV_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def ocean_configured() -> bool:
    return bool(ocean_api_token())


def ocean_webhook_base_url() -> str:
    return (
        os.getenv("OCEAN_WEBHOOK_BASE_URL")
        or os.getenv("APP_BASE_URL")
        or "https://lead-scraper-rrhtda.fly.dev"
    ).rstrip("/")


@dataclass(frozen=True)
class OceanSearchPage:
    records: list[dict[str, object]]
    total: int
    search_after: object | None


class OceanClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = OCEAN_API_BASE,
        timeout: float = 45.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token = (token or ocean_api_token()).strip()
        if not self.token:
            raise OceanAPIError(
                "Ocean.io is not configured. Add an OCEAN_API_TOKEN or Oceanio Fly secret."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def credit_balance(self) -> dict[str, object]:
        return self._request("GET", "/v2/credits/balance")

    def search_companies(
        self,
        *,
        size: int,
        companies_filters: dict[str, object] | None = None,
        lookalike_domains: list[str] | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> OceanSearchPage:
        payload: dict[str, object] = {"size": max(1, min(10_000, size))}
        filters = dict(companies_filters or {})
        if lookalike_domains:
            filters["lookalikeDomains"] = lookalike_domains
        if include_domains:
            filters["includeDomains"] = include_domains
        if exclude_domains:
            filters["excludeDomains"] = exclude_domains
        if filters:
            payload["companiesFilters"] = filters
        data = self._request("POST", "/v3/search/companies", payload)
        return OceanSearchPage(
            records=normalize_records(data.get("companies"), "company"),
            total=int(data.get("total") or 0),
            search_after=data.get("searchAfter"),
        )

    def search_people(
        self,
        *,
        size: int,
        people_filters: dict[str, object],
        companies_filters: dict[str, object],
        people_per_company: int = 1,
    ) -> OceanSearchPage:
        payload = {
            "size": max(1, min(10_000, size)),
            "peoplePerCompany": max(1, people_per_company),
            "peopleFilters": people_filters,
            "companiesFilters": companies_filters,
        }
        data = self._request("POST", "/v3/search/people", payload)
        return OceanSearchPage(
            records=normalize_records(data.get("people"), "person"),
            total=int(data.get("total") or 0),
            search_after=data.get("searchAfter"),
        )

    def reveal_emails(self, person_ids: list[str], webhook_url: str) -> dict[str, object]:
        if not person_ids:
            return {"status": "skipped"}
        if len(person_ids) > 500:
            raise ValueError("Ocean email reveal accepts at most 500 person IDs per request.")
        return self._request(
            "POST",
            "/v2/reveal/emails",
            {"personIds": person_ids, "webhookUrl": webhook_url},
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        headers = {"x-api-token": self.token, "accept": "application/json"}
        if payload is not None:
            headers["content-type"] = "application/json"
        with httpx.Client(
            timeout=self.timeout,
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            for attempt in range(4):
                response = client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("retry-after", "")
                    try:
                        delay = max(1.0, min(20.0, float(retry_after)))
                    except ValueError:
                        delay = 2**attempt
                    time.sleep(delay)
                    continue
                if response.status_code >= 500 and attempt < 3:
                    time.sleep(2**attempt)
                    continue
                if response.is_error:
                    detail = ocean_error_detail(response)
                    raise OceanAPIError(f"Ocean.io returned {response.status_code}: {detail}")
                data = response.json()
                return data if isinstance(data, dict) else {"data": data}
        raise OceanAPIError("Ocean.io did not respond after multiple attempts.")


class OceanLeadStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    def new_reveal(self, person_ids: list[str]) -> str:
        token = secrets.token_urlsafe(24)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO ocean_reveal_batches (token, expected_count) VALUES (?, ?)",
                (token, len(set(person_ids))),
            )
        return token

    def save_reveal(self, token: str, payload: dict[str, object]) -> int:
        results = payload.get("results") or payload.get("data") or []
        if not isinstance(results, list):
            return 0
        rows: list[tuple[str, str, str, str]] = []
        for raw in results:
            if not isinstance(raw, dict):
                continue
            person_id = str(raw.get("personId") or raw.get("person_id") or "").strip()
            email_value = raw.get("email")
            if isinstance(email_value, dict):
                address = str(email_value.get("address") or "").strip().lower()
                status = str(email_value.get("status") or "notFound").strip()
            else:
                address = str(email_value or raw.get("emailAddress") or "").strip().lower()
                status = str(raw.get("status") or ("verified" if address else "notFound")).strip()
            if person_id:
                rows.append((token, person_id, address, status))
        with self._connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM ocean_reveal_batches WHERE token = ?", (token,)
            ).fetchone()
            if not exists:
                return 0
            connection.executemany(
                """
                INSERT INTO ocean_email_results (token, person_id, address, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(token, person_id) DO UPDATE SET
                    address = excluded.address,
                    status = excluded.status
                """,
                rows,
            )
        return len(rows)

    def reveal_results(self, token: str) -> tuple[int, dict[str, dict[str, str]]]:
        with self._connection() as connection:
            batch = connection.execute(
                "SELECT expected_count FROM ocean_reveal_batches WHERE token = ?", (token,)
            ).fetchone()
            if not batch:
                return 0, {}
            rows = connection.execute(
                "SELECT person_id, address, status FROM ocean_email_results WHERE token = ?",
                (token,),
            ).fetchall()
        return int(batch[0]), {
            str(person_id): {"address": str(address or ""), "status": str(status or "")}
            for person_id, address, status in rows
        }

    def wait_for_reveal(
        self,
        token: str,
        timeout: float,
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, dict[str, str]]:
        deadline = time.monotonic() + timeout
        latest: dict[str, dict[str, str]] = {}
        while time.monotonic() < deadline:
            expected, latest = self.reveal_results(token)
            if progress:
                progress(len(latest), expected)
            if expected and len(latest) >= expected:
                return latest
            time.sleep(0.75)
        return latest

    def recent_domains(self, months: int) -> set[str]:
        return self._recent_values("domain", months)

    def recent_people(self, months: int) -> set[str]:
        return self._recent_values("person_id", months)

    def record_exports(self, rows: list[dict[str, object]]) -> None:
        values: list[tuple[str, str, str, str]] = []
        for row in rows:
            domain = str(row.get("domain") or "").strip().lower()
            person_id = str(row.get("person_id") or "").strip()
            email = str(row.get("verified_email") or "").strip().lower()
            identity = person_id or email or domain
            if identity:
                values.append((identity, domain, person_id, email))
        with self._connection() as connection:
            connection.executemany(
                """
                INSERT INTO ocean_export_history (identity, domain, person_id, email, exported_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(identity) DO UPDATE SET exported_at = CURRENT_TIMESTAMP
                """,
                values,
            )

    def _recent_values(self, column: str, months: int) -> set[str]:
        if column not in {"domain", "person_id"}:
            raise ValueError("Unsupported Ocean history column.")
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT {column} FROM ocean_export_history
                WHERE {column} != '' AND exported_at >= datetime('now', ?)
                """,
                (f"-{max(1, months) * 30} days",),
            ).fetchall()
        if column == "domain":
            return {str(row[0]).lower() for row in rows if row[0]}
        return {str(row[0]) for row in rows if row[0]}

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ocean_reveal_batches (
                    token TEXT PRIMARY KEY,
                    expected_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ocean_email_results (
                    token TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (token, person_id)
                );
                CREATE TABLE IF NOT EXISTS ocean_export_history (
                    identity TEXT PRIMARY KEY,
                    domain TEXT NOT NULL DEFAULT '',
                    person_id TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    exported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_ocean_exports_domain
                    ON ocean_export_history(domain);
                CREATE INDEX IF NOT EXISTS idx_ocean_exports_person
                    ON ocean_export_history(person_id);
                """
            )


def normalize_records(value: object, nested_key: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        nested = item.get(nested_key)
        record = dict(nested) if isinstance(nested, dict) else dict(item)
        for key, nested_value in item.items():
            if key != nested_key and key not in record:
                record[key] = nested_value
        normalized.append(record)
    return normalized


def ocean_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return response.text.strip()[:300] or "Unknown API error"
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
        if detail:
            return str(detail)[:300]
    return str(payload)[:300]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

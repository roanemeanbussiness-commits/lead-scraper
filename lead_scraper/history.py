from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .crawler import domain_of
from .models import Lead


@dataclass
class LeadHistory:
    path: Path
    emails: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)
    place_ids: set[str] = field(default_factory=set)
    contacts_by_domain: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "LeadHistory":
        history = cls(path=path)
        if history.uses_sqlite:
            history._initialize_database()
            history._load_database()
        elif path.exists():
            history._load_csv()
        return history

    @property
    def uses_sqlite(self) -> bool:
        return self.path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}

    def has_seen(self, email: str, domain: str, mode: str, place_id: str = "") -> bool:
        if mode == "none":
            return False
        place_seen = bool(place_id and place_id in self.place_ids)
        if mode == "email":
            return email.lower() in self.emails or place_seen
        if mode == "domain":
            return domain.lower() in self.domains or place_seen
        return email.lower() in self.emails or domain.lower() in self.domains or place_seen

    def append(self, leads: list[Lead]) -> None:
        if not leads:
            return
        if self.uses_sqlite:
            self._append_database(leads)
        else:
            self._append_csv(leads)
        for lead in leads:
            self.emails.add(lead.email.lower())
            self.domains.add(lead.domain.lower())
            if lead.place_id:
                self.place_ids.add(lead.place_id)
            self.contacts_by_domain[lead.domain.lower()] = {
                "verified_email": lead.email,
                "owner_name": lead.possible_owner or "",
                "business_name": lead.business_name or "",
                "source_url": lead.source_url,
            }

    def contact_for_domain(self, domain: str) -> dict[str, str]:
        return dict(self.contacts_by_domain.get(domain.lower(), {}))

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_history (
                    email TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    place_id TEXT NOT NULL DEFAULT '',
                    business_name TEXT NOT NULL DEFAULT '',
                    possible_owner TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_lead_history_domain ON lead_history(domain)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_lead_history_place_id ON lead_history(place_id)"
            )

    def _load_database(self) -> None:
        with self._connection() as connection:
            for email, domain, place_id, business_name, possible_owner, source_url in connection.execute(
                "SELECT email, domain, place_id, business_name, possible_owner, source_url FROM lead_history"
            ):
                if email:
                    self.emails.add(email.lower())
                if domain:
                    self.domains.add(domain.lower())
                if place_id:
                    self.place_ids.add(place_id)
                if domain:
                    self.contacts_by_domain.setdefault(
                        domain.lower(),
                        {
                            "verified_email": email or "",
                            "owner_name": possible_owner or "",
                            "business_name": business_name or "",
                            "source_url": source_url or "",
                        },
                    )

    def _append_database(self, leads: list[Lead]) -> None:
        rows = [
            (
                lead.email.lower(),
                lead.domain.lower(),
                lead.place_id or "",
                lead.business_name or "",
                lead.possible_owner or "",
                lead.source_url,
            )
            for lead in leads
        ]
        with self._connection() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO lead_history
                    (email, domain, place_id, business_name, possible_owner, source_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def _load_csv(self) -> None:
        with self.path.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                email = (row.get("email") or "").strip().lower()
                domain = (row.get("domain") or "").strip().lower()
                place_id = (row.get("place_id") or "").strip()
                website = (row.get("website") or row.get("url") or row.get("source_url") or "").strip()
                if email:
                    self.emails.add(email)
                if domain:
                    self.domains.add(domain)
                elif website:
                    self.domains.add(domain_of(website))
                if place_id:
                    self.place_ids.add(place_id)
                if domain:
                    self.contacts_by_domain.setdefault(
                        domain.lower(),
                        {
                            "verified_email": email,
                            "owner_name": (row.get("possible_owner") or row.get("owner_name") or "").strip(),
                            "business_name": (row.get("business_name") or "").strip(),
                            "source_url": (row.get("source_url") or website).strip(),
                        },
                    )

    def _append_csv(self, leads: list[Lead]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        exists = self.path.exists()
        fieldnames = [
            "email",
            "domain",
            "place_id",
            "business_name",
            "possible_owner",
            "custom_opener",
            "source_url",
        ]
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            for lead in leads:
                writer.writerow({field: getattr(lead, field) for field in fieldnames})

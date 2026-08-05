from __future__ import annotations

import json
import sqlite3
from array import array
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .company_profile import CompanyProfile


@dataclass(frozen=True)
class CatalogCompany:
    domain: str
    url: str
    place_id: str
    business_name: str
    phone: str
    address: str
    city: str
    state: str
    category: str
    profile: CompanyProfile
    embedding: list[float]
    embedding_model: str


class CompanyCatalog:
    def __init__(self, path: Path):
        self.path = path
        self._initialize()

    def get(self, domain: str) -> CatalogCompany | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT domain, url, place_id, business_name, phone, address, city, state, category, "
                "profile_json, embedding_blob, embedding_model FROM company_profiles WHERE domain = ?",
                (domain.lower(),),
            ).fetchone()
        return self._from_row(row) if row else None

    def list(self, state: str = "") -> list[CatalogCompany]:
        query = (
            "SELECT domain, url, place_id, business_name, phone, address, city, state, category, "
            "profile_json, embedding_blob, embedding_model FROM company_profiles"
        )
        params: tuple[str, ...] = ()
        if state.strip():
            query += " WHERE state = '' OR lower(state) = ?"
            params = (state.strip().lower(),)
        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def upsert(self, company: CatalogCompany) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO company_profiles (
                    domain, url, place_id, business_name, phone, address, city, state, category,
                    profile_json, embedding_blob, embedding_model, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(domain) DO UPDATE SET
                    url = excluded.url,
                    place_id = CASE WHEN excluded.place_id != '' THEN excluded.place_id ELSE company_profiles.place_id END,
                    business_name = CASE WHEN excluded.business_name != '' THEN excluded.business_name ELSE company_profiles.business_name END,
                    phone = CASE WHEN excluded.phone != '' THEN excluded.phone ELSE company_profiles.phone END,
                    address = CASE WHEN excluded.address != '' THEN excluded.address ELSE company_profiles.address END,
                    city = CASE WHEN excluded.city != '' THEN excluded.city ELSE company_profiles.city END,
                    state = CASE WHEN excluded.state != '' THEN excluded.state ELSE company_profiles.state END,
                    category = CASE WHEN excluded.category != '' THEN excluded.category ELSE company_profiles.category END,
                    profile_json = excluded.profile_json,
                    embedding_blob = excluded.embedding_blob,
                    embedding_model = excluded.embedding_model,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    company.domain.lower(), company.url, company.place_id, company.business_name, company.phone,
                    company.address, company.city, company.state, company.category,
                    company.profile.model_dump_json(), array("f", company.embedding).tobytes(), company.embedding_model,
                ),
            )

    def count(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM company_profiles").fetchone()[0])

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS company_profiles (
                    domain TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    place_id TEXT NOT NULL DEFAULT '',
                    business_name TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    profile_json TEXT NOT NULL,
                    embedding_blob BLOB NOT NULL,
                    embedding_model TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_company_profiles_state ON company_profiles(state)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_company_profiles_place ON company_profiles(place_id)")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=20000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _from_row(row) -> CatalogCompany:
        return CatalogCompany(
            domain=row[0], url=row[1], place_id=row[2], business_name=row[3], phone=row[4], address=row[5],
            city=row[6], state=row[7], category=row[8], profile=CompanyProfile.model_validate_json(row[9]),
            embedding=decode_embedding(row[10]), embedding_model=row[11],
        )


def decode_embedding(value: bytes | str) -> list[float]:
    if isinstance(value, bytes):
        numbers = array("f")
        numbers.frombytes(value)
        return [float(number) for number in numbers]
    return [float(number) for number in json.loads(value)]

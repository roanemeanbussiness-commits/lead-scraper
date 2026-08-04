from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .crawler import domain_of
from .models import Lead


@dataclass
class LeadHistory:
    path: Path
    emails: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> "LeadHistory":
        history = cls(path=path)
        if not path.exists():
            return history

        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                email = (row.get("email") or "").strip().lower()
                domain = (row.get("domain") or "").strip().lower()
                website = (row.get("website") or row.get("url") or row.get("source_url") or "").strip()
                if email:
                    history.emails.add(email)
                if domain:
                    history.domains.add(domain)
                elif website:
                    history.domains.add(domain_of(website))
        return history

    def has_seen(self, email: str, domain: str, mode: str) -> bool:
        if mode == "none":
            return False
        if mode == "email":
            return email.lower() in self.emails
        if mode == "domain":
            return domain.lower() in self.domains
        return email.lower() in self.emails or domain.lower() in self.domains

    def append(self, leads: list[Lead]) -> None:
        if not leads:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        exists = self.path.exists()
        fieldnames = ["email", "domain", "business_name", "possible_owner", "custom_opener", "source_url"]
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            for lead in leads:
                writer.writerow({field: getattr(lead, field) for field in fieldnames})
                self.emails.add(lead.email.lower())
                self.domains.add(lead.domain.lower())

from __future__ import annotations

import json
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .config import GENERIC_EMAIL_PREFIXES, SKIP_EMAIL_PREFIXES

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
NAME_RE = r"([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,2})"
OWNER_PATTERNS = [
    re.compile(
        rf"(?:owner|founder|co-founder|ceo|president|principal|operator|general manager)"
        rf"\s*(?:[:\-]|is|,)?\s*{NAME_RE}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:owned and operated by|owned by|founded by|led by|started by|meet the owner)\s+{NAME_RE}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"{NAME_RE}\s*(?:,|\-|\|)\s*(?:owner|founder|co-founder|ceo|president|principal|operator|general manager)",
        re.IGNORECASE,
    ),
]
BAD_NAME_PREFIXES = {"the", "our", "your", "a", "an"}
BAD_NAME_WORDS = {
    "business",
    "by",
    "clients",
    "company",
    "customers",
    "founded",
    "service",
    "services",
    "since",
    "team",
}


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def extract_emails(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: set[str] = set()

    for link in soup.select("a[href^='mailto:']"):
        href = unquote(link.get("href", ""))
        address = href.removeprefix("mailto:").split("?")[0].strip()
        candidates.update(EMAIL_RE.findall(address))

    candidates.update(EMAIL_RE.findall(unquote(html)))
    return {email.lower() for email in candidates if is_business_email(email)}


def extract_possible_owners(html: str) -> set[str]:
    text = page_text(html)
    owners = set()
    for pattern in OWNER_PATTERNS:
        owners.update(clean_owner_name(match) for match in pattern.findall(text))
    owners.update(extract_schema_people(html))
    return {owner for owner in owners if looks_like_person_name(owner)}


def extract_schema_people(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    names: set[str] = set()
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        names.update(names_from_schema_node(data))
    return names


def names_from_schema_node(node: object) -> set[str]:
    names: set[str] = set()
    if isinstance(node, list):
        for item in node:
            names.update(names_from_schema_node(item))
        return names

    if not isinstance(node, dict):
        return names

    node_type = node.get("@type")
    if isinstance(node_type, list):
        node_types = {str(value).lower() for value in node_type}
    else:
        node_types = {str(node_type).lower()}

    name = node.get("name")
    if "person" in node_types and isinstance(name, str):
        names.add(name)

    for key in ["founder", "owner", "employee", "founders", "alumni"]:
        value = node.get(key)
        names.update(names_from_schema_person_field(value))

    graph = node.get("@graph")
    if graph:
        names.update(names_from_schema_node(graph))

    return names


def names_from_schema_person_field(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        names = set()
        for item in value:
            names.update(names_from_schema_person_field(item))
        return names
    if isinstance(value, dict):
        name = value.get("name")
        return {name} if isinstance(name, str) else set()
    return set()


def clean_owner_name(name: str) -> str:
    parts = name.strip(" .,:;!?()[]{}").split()
    cleaned = []
    for part in parts:
        normalized = part.lower().strip(".,")
        if normalized in BAD_NAME_WORDS:
            break
        cleaned.append(part.strip(".,"))
    return " ".join(cleaned)


def looks_like_person_name(name: str) -> bool:
    parts = name.strip().split()
    if len(parts) < 2 or len(parts) > 3:
        return False
    lowered = {part.lower().strip(".,") for part in parts}
    if parts[0].lower() in BAD_NAME_PREFIXES:
        return False
    if lowered & BAD_NAME_WORDS:
        return False
    return all(re.match(r"^[A-Za-z][A-Za-z.'-]+$", part) for part in parts)


def is_business_email(email: str) -> bool:
    local, _, domain = email.lower().partition("@")
    if not local or not domain:
        return False
    if local in SKIP_EMAIL_PREFIXES:
        return False
    if any(local.startswith(prefix + ".") for prefix in SKIP_EMAIL_PREFIXES):
        return False
    if domain.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return False
    if "example." in domain or domain.endswith(".test"):
        return False
    return True


def is_generic_email(email: str) -> bool:
    if not email or "@" not in email:
        return True

    local_part = email.split("@", maxsplit=1)[0].lower().strip()
    clean_prefix = local_part.split(".")[0].split("-")[0].split("_")[0]
    return clean_prefix in GENERIC_EMAIL_PREFIXES

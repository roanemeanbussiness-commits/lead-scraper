from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .config import GENERIC_EMAIL_PREFIXES, SKIP_EMAIL_PREFIXES

try:
    import extruct
except ImportError:  # Optional during lightweight local development.
    extruct = None

try:
    import trafilatura
except ImportError:  # BeautifulSoup remains a reliable fallback.
    trafilatura = None

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
NAME_RE = r"([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,2})"
OWNER_PATTERNS = [
    ("Owner", 88, re.compile(
        rf"(?:owner|founder|co-founder|ceo|president|principal|operator|general manager)"
        rf"\s*(?:[:\-]|is|,)?\s*{NAME_RE}",
        re.IGNORECASE,
    )),
    ("Owner", 94, re.compile(
        rf"(?:owned and operated by|owned by|founded by|led by|started by|meet the owner)\s+{NAME_RE}",
        re.IGNORECASE,
    )),
    ("Owner", 90, re.compile(
        rf"{NAME_RE}\s*(?:,|\-|\|)\s*(?:owner|founder|co-founder|ceo|president|principal|operator|general manager)",
        re.IGNORECASE,
    )),
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


@dataclass(frozen=True)
class OwnerCandidate:
    name: str
    role: str
    evidence: str
    source_url: str = ""
    confidence: int = 0


def page_text(html: str) -> str:
    if trafilatura is not None:
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if extracted:
                return " ".join(extracted.split())
        except Exception:
            pass

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

    for element in soup.select("[data-cfemail]"):
        decoded = decode_cloudflare_email(element.get("data-cfemail", ""))
        if decoded:
            candidates.add(decoded)

    decoded_html = unquote(html)
    decoded_html = re.sub(r"\s*(?:\[|\()\s*at\s*(?:\]|\))\s*", "@", decoded_html, flags=re.IGNORECASE)
    decoded_html = re.sub(r"\s*(?:\[|\()\s*dot\s*(?:\]|\))\s*", ".", decoded_html, flags=re.IGNORECASE)
    candidates.update(EMAIL_RE.findall(decoded_html))
    return {email.lower() for email in candidates if is_business_email(email)}


def extract_possible_owners(html: str) -> set[str]:
    return {candidate.name for candidate in extract_owner_candidates(html)}


def extract_owner_candidates(html: str, source_url: str = "") -> list[OwnerCandidate]:
    text = page_text(html)
    candidates: dict[str, OwnerCandidate] = {}

    for role, confidence, pattern in OWNER_PATTERNS:
        for match in pattern.finditer(text):
            name = clean_owner_name(match.group(1))
            if not looks_like_person_name(name):
                continue
            evidence = " ".join(match.group(0).split())[:240]
            add_owner_candidate(
                candidates,
                OwnerCandidate(name, role, evidence, source_url, confidence),
            )

    for candidate in extract_schema_owner_candidates(html, source_url):
        add_owner_candidate(candidates, candidate)

    return sorted(candidates.values(), key=lambda item: (-item.confidence, item.name.lower()))


def extract_schema_people(html: str) -> set[str]:
    return {candidate.name for candidate in extract_schema_owner_candidates(html)}


def extract_schema_owner_candidates(html: str, source_url: str = "") -> list[OwnerCandidate]:
    candidates: dict[str, OwnerCandidate] = {}

    if extruct is not None:
        try:
            data = extruct.extract(
                html,
                base_url=source_url or None,
                syntaxes=["json-ld", "microdata"],
                uniform=True,
            )
            for syntax in ("json-ld", "microdata"):
                for node in data.get(syntax, []):
                    for candidate in owner_candidates_from_schema_node(node, source_url):
                        add_owner_candidate(candidates, candidate)
        except Exception:
            pass

    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for candidate in owner_candidates_from_schema_node(data, source_url):
            add_owner_candidate(candidates, candidate)
    return list(candidates.values())


def names_from_schema_node(node: object) -> set[str]:
    return {candidate.name for candidate in owner_candidates_from_schema_node(node)}


def owner_candidates_from_schema_node(node: object, source_url: str = "") -> list[OwnerCandidate]:
    candidates: list[OwnerCandidate] = []
    if isinstance(node, list):
        for item in node:
            candidates.extend(owner_candidates_from_schema_node(item, source_url))
        return candidates
    if not isinstance(node, dict):
        return candidates

    for key, role, confidence in (("founder", "Founder", 98), ("founders", "Founder", 98), ("owner", "Owner", 98)):
        for name in names_from_schema_person_field(node.get(key)):
            cleaned = clean_owner_name(name)
            if looks_like_person_name(cleaned):
                candidates.append(
                    OwnerCandidate(cleaned, role, f"schema.org {key}", source_url, confidence)
                )

    graph = node.get("@graph")
    if graph:
        candidates.extend(owner_candidates_from_schema_node(graph, source_url))
    return candidates


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


def add_owner_candidate(candidates: dict[str, OwnerCandidate], candidate: OwnerCandidate) -> None:
    key = candidate.name.lower()
    current = candidates.get(key)
    if current is None or candidate.confidence > current.confidence:
        candidates[key] = candidate


def decode_cloudflare_email(value: str) -> str:
    try:
        key = int(value[:2], 16)
        return "".join(chr(int(value[index : index + 2], 16) ^ key) for index in range(2, len(value), 2))
    except (ValueError, TypeError):
        return ""


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

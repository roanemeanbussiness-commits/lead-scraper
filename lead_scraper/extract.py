from __future__ import annotations

import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .config import SKIP_EMAIL_PREFIXES

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


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


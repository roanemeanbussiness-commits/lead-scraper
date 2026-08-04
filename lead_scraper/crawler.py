from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import CONTACT_PATH_HINTS


@dataclass(frozen=True)
class CrawledPage:
    url: str
    html: str


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def normalize_url(url: str) -> str:
    clean, _fragment = urldefrag(url)
    return clean.rstrip("/")


def crawl_site(seed_url: str, max_pages: int, timeout: float) -> list[CrawledPage]:
    start = normalize_url(seed_url)
    root_domain = domain_of(start)
    queue: deque[str] = deque([start])
    seen: set[str] = set()
    pages: list[CrawledPage] = []

    headers = {"User-Agent": "8-Thon-Lead-Scraper/0.1 public-contact-discovery"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
        while queue and len(pages) < max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)

            try:
                response = client.get(url)
                content_type = response.headers.get("content-type", "")
                if response.status_code >= 400 or "text/html" not in content_type:
                    continue
            except httpx.HTTPError:
                continue

            html = response.text
            pages.append(CrawledPage(url=str(response.url), html=html))

            for link in prioritized_links(html, str(response.url), root_domain):
                if link not in seen and link not in queue:
                    queue.append(link)

    return pages


def prioritized_links(html: str, base_url: str, root_domain: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    scored: list[tuple[int, str]] = []

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        url = normalize_url(urljoin(base_url, href))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or domain_of(url) != root_domain:
            continue

        path = parsed.path.lower()
        text = anchor.get_text(" ", strip=True).lower()
        haystack = f"{path} {text}"
        score = 10 if any(hint in haystack for hint in CONTACT_PATH_HINTS) else 1
        scored.append((score, url))

    ordered = sorted(scored, key=lambda item: item[0], reverse=True)
    deduped = list(dict.fromkeys(url for _score, url in ordered))
    return deduped[:20]


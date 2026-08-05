from __future__ import annotations

import ipaddress
import socket
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .config import CONTACT_PATH_HINTS

USER_AGENT = "8-Thon-Lead-Scraper"
MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 5
PRIORITY_PATHS = (
    "/about",
    "/about-us",
    "/our-team",
    "/team",
    "/leadership",
    "/contact",
    "/contact-us",
)


class UnsafeURL(ValueError):
    pass


@dataclass(frozen=True)
class CrawledPage:
    url: str
    html: str


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.")


def normalize_url(url: str) -> str:
    clean, _fragment = urldefrag(url)
    parsed = urlparse(clean)
    if parsed.path in {"", "/"} and not parsed.query:
        return clean.rstrip("/")
    return clean.rstrip("/")


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeURL("Only public http:// or https:// website URLs are allowed.")
    if parsed.username or parsed.password:
        raise UnsafeURL("Website URLs cannot contain credentials.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeURL("Website URL contains an invalid port.") from exc
    if port not in {None, 80, 443}:
        raise UnsafeURL("Only standard website ports 80 and 443 are allowed.")

    host = parsed.hostname.strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise UnsafeURL("Local and private network addresses are not allowed.")

    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80))
            }
        except socket.gaierror as exc:
            raise UnsafeURL(f"Website hostname could not be resolved: {host}") from exc

    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeURL("Local, private, reserved, and link-local addresses are not allowed.")
    return normalize_url(url)


def crawl_site(seed_url: str, max_pages: int, timeout: float) -> list[CrawledPage]:
    start = validate_public_url(normalize_url(seed_url))
    root_domain = domain_of(start)
    parsed_start = urlparse(start)
    origin = f"{parsed_start.scheme}://{parsed_start.netloc}"
    queue: deque[str] = deque([start, *(urljoin(origin, path) for path in PRIORITY_PATHS)])
    seen: set[str] = set()
    pages: list[CrawledPage] = []
    robots_cache: dict[str, RobotFileParser | None] = {}

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    limits = httpx.Limits(max_connections=5, max_keepalive_connections=2)
    with httpx.Client(headers=headers, follow_redirects=False, timeout=timeout, limits=limits) as client:
        while queue and len(pages) < max_pages:
            url = normalize_url(queue.popleft())
            if url in seen:
                continue
            seen.add(url)

            try:
                validate_public_url(url)
                if not robots_allowed(client, url, robots_cache):
                    continue
                final_url, html = fetch_html(client, url)
            except (httpx.HTTPError, UnsafeURL):
                continue

            if domain_of(final_url) != root_domain:
                continue
            pages.append(CrawledPage(url=final_url, html=html))

            for link in prioritized_links(html, final_url, root_domain):
                if link not in seen and link not in queue:
                    queue.append(link)

    return pages


def fetch_html(client: httpx.Client, url: str, attempts: int = 2) -> tuple[str, str]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fetch_html_once(client, url)
        except (httpx.HTTPError, UnsafeURL) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.35 * (2**attempt))
    if last_error:
        raise last_error
    raise httpx.RequestError("Unable to fetch website")


def fetch_html_once(client: httpx.Client, url: str) -> tuple[str, str]:
    current = validate_public_url(url)
    for _redirect in range(MAX_REDIRECTS + 1):
        with client.stream("GET", current) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise httpx.HTTPStatusError("Redirect is missing Location", request=response.request, response=response)
                current = validate_public_url(urljoin(current, location))
                continue

            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise httpx.HTTPError("Response is not HTML")

            declared_size = response.headers.get("content-length")
            if declared_size and declared_size.isdigit() and int(declared_size) > MAX_RESPONSE_BYTES:
                raise httpx.HTTPError("HTML response is too large")

            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise httpx.HTTPError("HTML response is too large")
            encoding = response.encoding or "utf-8"
            return str(response.url), bytes(body).decode(encoding, errors="replace")
    raise httpx.TooManyRedirects("Too many redirects")


def robots_allowed(
    client: httpx.Client,
    url: str,
    cache: dict[str, RobotFileParser | None],
) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            final_url, text = fetch_text(client, robots_url, max_bytes=512_000)
            parser.set_url(final_url)
            parser.parse(text.splitlines())
            cache[origin] = parser
        except (httpx.HTTPError, UnsafeURL):
            cache[origin] = None
    parser = cache[origin]
    return parser.can_fetch(USER_AGENT, url) if parser else True


def fetch_text(client: httpx.Client, url: str, max_bytes: int) -> tuple[str, str]:
    current = validate_public_url(url)
    for _redirect in range(MAX_REDIRECTS + 1):
        with client.stream("GET", current) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise httpx.HTTPStatusError("Redirect is missing Location", request=response.request, response=response)
                current = validate_public_url(urljoin(current, location))
                continue
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise httpx.HTTPError("Response is too large")
            encoding = response.encoding or "utf-8"
            return str(response.url), bytes(body).decode(encoding, errors="replace")
    raise httpx.TooManyRedirects("Too many redirects")


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
    return list(dict.fromkeys(url for _score, url in ordered))[:20]

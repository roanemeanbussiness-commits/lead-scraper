from __future__ import annotations

import json
import os

import httpx

from .crawler import crawl_site
from .extract import is_business_email, is_generic_email, page_text


def openai_configured() -> bool:
    return bool(get_openai_api_key())


def enrich_direct_rows_with_openai(rows: list[dict[str, str]], max_pages: int = 2) -> list[dict[str, str]]:
    if not openai_configured() or not rows:
        return rows

    enriched = []
    for row in rows:
        enriched.append(enrich_direct_row(row, max_pages=max_pages))
    return enriched


def enrich_direct_row(row: dict[str, str], max_pages: int) -> dict[str, str]:
    website = row.get("website") or ""
    text = ""
    if website:
        pages = crawl_site(website, max_pages=max_pages, timeout=10.0)
        text = " ".join(page_text(page.html) for page in pages)[:5000]

    ai_data = extract_with_openai(
        business_name=row.get("business_name") or "",
        website=website,
        website_text=text,
        industry=row.get("industry") or "",
        location=row.get("location") or "",
    )
    updated = dict(row)
    if ai_data.get("owner_name") and not updated.get("owner_name"):
        updated["owner_name"] = ai_data["owner_name"]
        updated["first_name"] = ai_data["owner_name"].split()[0]
    if ai_data.get("email") and not updated.get("verified_email"):
        updated["verified_email"] = ai_data["email"]
    if ai_data.get("custom_opener") and not updated.get("custom_opener"):
        updated["custom_opener"] = ai_data["custom_opener"]
    return updated


def extract_with_openai(
    business_name: str,
    website: str,
    website_text: str,
    industry: str,
    location: str,
) -> dict[str, str]:
    api_key = get_openai_api_key()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        return {"owner_name": "", "email": "", "custom_opener": ""}

    prompt = {
        "business_name": business_name,
        "website": website,
        "industry": industry,
        "location": location,
        "website_text": website_text,
        "task": (
            "Return JSON with owner_name, email, and custom_opener. Use owner_name only when the text clearly "
            "names an owner, founder, CEO, president, or principal. For email, prefer direct personal addresses "
            "and avoid generic inboxes such as info@, support@, sales@, contact@, admin@, hello@, office@, and team@. "
            "The custom_opener should be one short sentence based on the business services or location. Do not invent facts."
        ),
    }

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "lead_enrichment",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "owner_name": {"type": "string"},
                                "email": {"type": "string"},
                                "custom_opener": {"type": "string"},
                            },
                            "required": ["owner_name", "email", "custom_opener"],
                        },
                    },
                },
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a careful B2B lead research assistant. Return strict JSON only.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                "temperature": 0.2,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
    except Exception:
        return {"owner_name": "", "email": "", "custom_opener": ""}

    email = str(data.get("email") or "").strip().lower()
    if email and (not is_business_email(email) or is_generic_email(email)):
        email = ""

    return {
        "owner_name": str(data.get("owner_name") or "").strip(),
        "email": email,
        "custom_opener": str(data.get("custom_opener") or "").strip(),
    }


def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or os.getenv("OpenAI_api") or os.getenv("OPENAI_API") or ""

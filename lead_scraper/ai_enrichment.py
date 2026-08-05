from __future__ import annotations

import json
import os

import httpx

from .extract import is_business_email, is_generic_email, looks_like_person_name


def openai_configured() -> bool:
    return bool(get_openai_api_key())


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
        return empty_enrichment()

    prompt = {
        "business_name": business_name,
        "website": website,
        "industry": industry,
        "location": location,
        "website_text": website_text,
        "task": (
            "Return JSON with owner_name, owner_role, owner_evidence, email, and custom_opener. Use owner_name only "
            "when the text clearly names an owner, founder, CEO, president, or principal. Copy a short supporting "
            "phrase into owner_evidence; otherwise leave all owner fields blank. For email, prefer direct personal addresses "
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
                                "owner_role": {"type": "string"},
                                "owner_evidence": {"type": "string"},
                                "email": {"type": "string"},
                                "custom_opener": {"type": "string"},
                            },
                            "required": ["owner_name", "owner_role", "owner_evidence", "email", "custom_opener"],
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
        return empty_enrichment()

    email = str(data.get("email") or "").strip().lower()
    if email and (not is_business_email(email) or is_generic_email(email)):
        email = ""

    owner_name = str(data.get("owner_name") or "").strip()
    if owner_name and not looks_like_person_name(owner_name):
        owner_name = ""

    return {
        "owner_name": owner_name,
        "owner_role": str(data.get("owner_role") or "").strip() if owner_name else "",
        "owner_evidence": str(data.get("owner_evidence") or "").strip()[:240] if owner_name else "",
        "email": email,
        "custom_opener": str(data.get("custom_opener") or "").strip(),
    }


def empty_enrichment() -> dict[str, str]:
    return {
        "owner_name": "",
        "owner_role": "",
        "owner_evidence": "",
        "email": "",
        "custom_opener": "",
    }


def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or os.getenv("OpenAI_api") or os.getenv("OPENAI_API") or ""

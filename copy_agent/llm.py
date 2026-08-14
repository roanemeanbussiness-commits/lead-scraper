"""OpenAI chat client for the Copy Studio agent.

Raw httpx rather than the OpenAI SDK: the app needs exactly one endpoint
(chat completions, streamed and unstreamed), and a thin client keeps retry
and error behavior explicit and testable.
"""

from __future__ import annotations

import json
import os
import time
from typing import Iterator

import httpx

OPENAI_API_BASE = "https://api.openai.com"
DEFAULT_MODEL = "gpt-4.1"
KEY_ENV_NAMES = ("OPENAI_API_KEY", "OpenAI_api", "OPENAI_API")


class OpenAIError(RuntimeError):
    pass


def openai_api_key() -> str:
    for name in KEY_ENV_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def openai_configured() -> bool:
    return bool(openai_api_key())


def chat_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


class ChatClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = OPENAI_API_BASE,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = (api_key or openai_api_key()).strip()
        if not self.api_key:
            raise OpenAIError(
                "OpenAI is not configured. Add an OPENAI_API_KEY (or OpenAI_api) Fly secret."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _payload(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        stream: bool,
    ) -> dict[str, object]:
        chosen = (model or chat_model()).strip()
        payload: dict[str, object] = {
            "model": chosen,
            "messages": messages,
            "max_completion_tokens": int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", "2048")),
        }
        if stream:
            payload["stream"] = True
        return payload

    def complete(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        with self._client() as client:
            response = self._post_with_retries(
                client, self._payload(messages, model, stream=False)
            )
            data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAIError(f"Unexpected OpenAI response shape: {str(data)[:200]}") from exc

    def stream(
        self, messages: list[dict[str, str]], model: str | None = None
    ) -> Iterator[str]:
        """Yield content deltas as they arrive."""
        with self._client() as client:
            payload = self._payload(messages, model, stream=True)
            for attempt in range(3):
                try:
                    with client.stream(
                        "POST",
                        f"{self.base_url}/v1/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    ) as response:
                        if response.status_code in (429,) or response.status_code >= 500:
                            response.read()
                            if attempt < 2:
                                # 429s here are usually per-minute token limits;
                                # short backoffs never recover, so wait longer.
                                time.sleep(12 * (attempt + 1) if response.status_code == 429 else 2**attempt)
                                continue
                        if response.is_error:
                            response.read()
                            raise OpenAIError(openai_error_detail(response))
                        yield from self._parse_sse(response)
                        return
                except httpx.RequestError as exc:
                    if attempt < 2:
                        time.sleep(2**attempt)
                        continue
                    raise OpenAIError(f"OpenAI request failed: {exc}") from exc
        raise OpenAIError("OpenAI did not respond after multiple attempts.")

    @staticmethod
    def _parse_sse(response: httpx.Response) -> Iterator[str]:
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line.removeprefix("data: ").strip()
            if data == "[DONE]":
                return
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = (choices[0].get("delta") or {}).get("content")
            if delta:
                yield delta

    def _post_with_retries(
        self, client: httpx.Client, payload: dict[str, object]
    ) -> httpx.Response:
        for attempt in range(3):
            try:
                response = client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
            except httpx.RequestError as exc:
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise OpenAIError(f"OpenAI request failed: {exc}") from exc
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    time.sleep(12 * (attempt + 1) if response.status_code == 429 else 2**attempt)
                    continue
            if response.is_error:
                raise OpenAIError(openai_error_detail(response))
            return response
        raise OpenAIError("OpenAI did not respond after multiple attempts.")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout, transport=self.transport)


def openai_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        return f"OpenAI returned {response.status_code}: {response.text.strip()[:200]}"
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = str(error.get("message") or error.get("code") or error)[:300]
        return f"OpenAI returned {response.status_code}: {message}"
    return f"OpenAI returned {response.status_code}: {str(payload)[:200]}"

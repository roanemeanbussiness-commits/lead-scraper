"""8-Thon Intelligence Copy Studio - FastAPI app."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .dashboard import render_dashboard
from .knowledge_loader import build_compact_prompt, build_system_prompt
from .llm import ChatClient, OpenAIError, chat_model, openai_configured
from .store import ChatStore
from .youtube import (
    TranscriptError,
    extract_video_id,
    fetch_transcript,
    summarize_transcript,
)

app = FastAPI(title="8-Thon Intelligence Copy Studio")
DEFAULT_DATA_PATH = Path("/data") if os.name != "nt" and Path("/data").exists() else Path("data")
STORE = ChatStore(Path(os.getenv("CHAT_STORE_PATH", str(DEFAULT_DATA_PATH / "copy_studio.db"))))
HISTORY_LIMIT = 24
HISTORY_CHAR_BUDGET = 24_000


def trim_history(history: list[dict[str, str]], budget: int = HISTORY_CHAR_BUDGET) -> list[dict[str, str]]:
    """Keep the newest messages that fit the character budget - Tier-1 OpenAI
    accounts have tight tokens-per-minute limits, so history must stay small."""
    kept: list[dict[str, str]] = []
    used = 0
    for message in reversed(history):
        used += len(message["content"])
        if kept and used > budget:
            break
        kept.append(message)
    return list(reversed(kept))


def search_model() -> str:
    return os.getenv("OPENAI_SEARCH_MODEL", "gpt-4o-search-preview")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_000)
    conversation_id: str = ""
    research: bool = False


class LearningRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)


class YouTubeRequest(BaseModel):
    url: str = Field(min_length=5, max_length=500)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(
        render_dashboard(version=__version__, openai_ok=openai_configured()),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    if not openai_configured():
        raise HTTPException(
            status_code=400,
            detail="OpenAI is not configured. Add an OpenAI_api or OPENAI_API_KEY Fly secret.",
        )
    conversation_id = request.conversation_id.strip()
    if conversation_id and not STORE.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if not conversation_id:
        conversation_id = STORE.create_conversation()

    STORE.add_message(conversation_id, "user", request.message)
    STORE.set_title_if_empty(conversation_id, request.message.splitlines()[0][:80])

    # The search model runs under a much tighter tokens-per-minute limit
    # than the writing model, so research mode gets a compact prompt and a
    # short history window instead of the full knowledge base.
    if request.research:
        system_prompt = build_compact_prompt()
        history = trim_history(STORE.messages(conversation_id, limit=6), budget=8_000)
        model = search_model()
    else:
        system_prompt = build_system_prompt(STORE)
        history = trim_history(STORE.messages(conversation_id, limit=HISTORY_LIMIT))
        model = None
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in history)

    def event_stream() -> Iterator[str]:
        yield sse({"type": "start", "conversation_id": conversation_id})
        parts: list[str] = []
        try:
            client = ChatClient()
            for delta in client.stream(messages, model=model):
                cleaned = scrub_dashes(delta)
                parts.append(cleaned)
                yield sse({"type": "delta", "text": cleaned})
        except OpenAIError as exc:
            yield sse({"type": "error", "message": str(exc)})
            return
        answer = "".join(parts)
        if answer:
            STORE.add_message(conversation_id, "assistant", answer)
        yield sse({"type": "done", "conversation_id": conversation_id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def scrub_dashes(text: str) -> str:
    """Hard voice rule: no em or en dashes ever reach the reader.

    The humanize skill instructs the model, and this backstop guarantees it
    even when the model slips one through."""
    return (
        text.replace("\u2014", ", ")
        .replace("\u2013", "-")
        .replace(" , ", ", ")
        .replace(",  ", ", ")
    )


def sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/api/conversations")
def conversations() -> JSONResponse:
    return JSONResponse(STORE.list_conversations(), headers={"Cache-Control": "no-store"})


@app.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str) -> JSONResponse:
    if not STORE.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return JSONResponse(
        {"id": conversation_id, "messages": STORE.messages(conversation_id)},
        headers={"Cache-Control": "no-store"},
    )


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, str]:
    STORE.delete_conversation(conversation_id)
    return {"status": "deleted"}


@app.get("/api/learnings")
def learnings() -> JSONResponse:
    return JSONResponse(STORE.list_learnings(), headers={"Cache-Control": "no-store"})


@app.post("/api/learnings", status_code=201)
def add_learning(request: LearningRequest) -> dict[str, object]:
    learning_id = STORE.add_learning("note", "", request.title, request.content)
    return {"id": learning_id, "status": "saved"}


@app.delete("/api/learnings/{learning_id}")
def delete_learning(learning_id: int) -> dict[str, str]:
    if not STORE.delete_learning(learning_id):
        raise HTTPException(status_code=404, detail="Learning not found.")
    return {"status": "deleted"}


@app.post("/api/youtube/ingest", status_code=201)
def ingest_youtube(request: YouTubeRequest) -> dict[str, object]:
    if not openai_configured():
        raise HTTPException(status_code=400, detail="OpenAI is not configured.")
    try:
        video_id = extract_video_id(request.url)
        transcript = fetch_transcript(video_id)
        summary = summarize_transcript(ChatClient(), transcript, request.url)
    except TranscriptError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    title_line = next(
        (line.strip("# ").strip() for line in summary.splitlines() if line.strip()),
        f"YouTube video {video_id}",
    )
    learning_id = STORE.add_learning(
        "youtube", request.url, f"Video study: {title_line[:150]}", summary
    )
    return {"id": learning_id, "status": "learned", "summary": summary}


@app.get("/api/status")
def status() -> dict[str, str]:
    return {
        "service": "8-Thon Intelligence Copy Studio",
        "version": __version__,
        "status": "ok",
        "openai": "configured" if openai_configured() else "missing",
        "model": chat_model(),
        "search_model": search_model(),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

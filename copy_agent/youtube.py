"""YouTube transcript ingestion - the agent learns from videos it is given."""

from __future__ import annotations

import re

from .llm import ChatClient

VIDEO_ID_PATTERNS = (
    re.compile(r"(?:v=|/shorts/|/live/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})"),
    re.compile(r"^([A-Za-z0-9_-]{11})$"),
)

SUMMARIZE_PROMPT = """\
You are a marketing analyst. Below is the transcript of a YouTube video.
Extract the transferable lessons a copywriter should learn from it.

Return markdown with exactly these sections:
## What this video is about
(1-2 sentences)
## Hook analysis
(How the first 30 seconds work - quote the actual opening lines)
## Structure & retention tactics
(The skeleton: how it sequences ideas, open loops, payoffs, CTAs)
## Copy techniques worth stealing
(Specific phrasings, framings, persuasion moves - quote examples)
## How 8-Thon could apply this
(2-3 concrete applications for AI-implementation content)

Be specific and quote the transcript. Do not pad.

TRANSCRIPT:
{transcript}
"""


class TranscriptError(RuntimeError):
    pass


def extract_video_id(url: str) -> str:
    text = url.strip()
    for pattern in VIDEO_ID_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    raise TranscriptError(
        "Could not find a YouTube video ID in that link. "
        "Paste a normal video URL like https://www.youtube.com/watch?v=..."
    )


def fetch_transcript(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise TranscriptError("youtube-transcript-api is not installed.") from exc
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=("en", "en-US", "en-GB"))
        snippets = getattr(fetched, "snippets", fetched)
        text = " ".join(
            getattr(snippet, "text", "") or "" for snippet in snippets
        )
    except TranscriptError:
        raise
    except Exception as exc:
        raise TranscriptError(
            f"Could not fetch a transcript for video {video_id}: {exc}. "
            "The video may have captions disabled."
        ) from exc
    cleaned = " ".join(text.split())
    if len(cleaned) < 200:
        raise TranscriptError(
            f"The transcript for {video_id} is too short to learn from."
        )
    return cleaned


def summarize_transcript(client: ChatClient, transcript: str, url: str) -> str:
    # Very long transcripts get trimmed from the middle; hooks (start) and
    # CTAs (end) carry most of the copywriting signal.
    limit = 60_000
    if len(transcript) > limit:
        head = transcript[: limit // 2]
        tail = transcript[-limit // 2 :]
        transcript = f"{head}\n[... middle trimmed ...]\n{tail}"
    prompt = SUMMARIZE_PROMPT.format(transcript=transcript)
    return client.complete(
        [
            {"role": "system", "content": "You extract copywriting lessons from video transcripts."},
            {"role": "user", "content": f"Video: {url}\n\n{prompt}"},
        ]
    )

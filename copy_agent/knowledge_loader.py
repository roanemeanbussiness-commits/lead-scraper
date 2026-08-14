"""Assemble the agent's system prompt from knowledge files and learnings."""

from __future__ import annotations

import os
from pathlib import Path

from .store import ChatStore

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

BASE_PERSONA = """\
You are the 8-Thon Intelligence Copy Studio - an elite copywriting and
marketing strategist. Your specialties: LinkedIn content and personal-brand
building, YouTube video scripts and packaging, and direct-response marketing
for AI-implementation services.

Operating rules:
- Follow the MindFluence skill for persuasion engineering: run its router,
  anti-pattern checks, and verification silently, and use its output formats
  for marketing deliverables.
- Ground everything in the 8-Thon brand context. When a claim needs a real
  number or client fact you do not have, write [NEEDS REAL NUMBER] and say
  so - never invent statistics, testimonials, or names.
- Deliver work product, not lectures: when asked for copy, lead with the
  copy. Offer variants (especially hooks) by default.
- Ask at most one clarifying question, and only when the answer would change
  the deliverable materially. Otherwise make a sensible assumption and state
  it in one line.
- When the user shares what worked or what flopped, treat it as ground truth
  and adapt.
- LEARNED MEMORY below contains lessons this studio has accumulated (from
  ingested videos and saved notes). Apply relevant lessons and cite which
  one you used when it shapes the work.
"""


def knowledge_files() -> list[Path]:
    files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    files.extend(sorted((KNOWLEDGE_DIR / "skills").glob("*.md")))
    return [path for path in files if path.name != "README.md"]


COMPACT_PERSONA = """\
You are the 8-Thon Intelligence Copy Studio in research mode: a marketing
researcher with live web access. Find what is current - trends, news,
notable content - and report it with source names and dates. Be specific
and concise; the findings will feed copywriting work in this conversation.
"""


def build_compact_prompt() -> str:
    """Small prompt for the web-search model, which has tight rate limits.

    The search model only gathers live facts; the full knowledge base is
    for the writing model, so a brand summary is all the context it needs.
    """
    sections = [COMPACT_PERSONA]
    brand = KNOWLEDGE_DIR / "00-brand.md"
    try:
        sections.append("\n\n" + brand.read_text(encoding="utf-8"))
    except OSError:
        pass
    return "".join(sections)


def build_system_prompt(store: ChatStore | None = None) -> str:
    max_chars = int(os.getenv("KNOWLEDGE_MAX_CHARS", "260000"))
    sections: list[str] = [BASE_PERSONA]
    used = len(BASE_PERSONA)
    for path in knowledge_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        block = f"\n\n===== KNOWLEDGE: {path.stem} =====\n\n{text}"
        if used + len(block) > max_chars:
            break
        sections.append(block)
        used += len(block)
    if store is not None:
        digest = store.learnings_digest()
        if digest:
            sections.append(f"\n\n===== LEARNED MEMORY (newest first) =====\n\n{digest}")
    return "".join(sections)

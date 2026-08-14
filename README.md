# 8-Thon Intelligence Copy Studio

A copywriting and marketing expert agent with a chat dashboard. Specialties:
LinkedIn content, YouTube scripts and packaging, and direct-response copy for
AI-implementation services.

## What it does

- **Chat** (`/`): streaming chatbot backed by OpenAI (`OPENAI_MODEL`, default
  `gpt-4.1`), loaded with a curated knowledge base on every message.
- **Research mode**: toggles to `gpt-4o-search-preview`, which browses the
  live web - "write a YouTube script based on what's trending" works.
- **Self-learning**: paste a YouTube link and the studio fetches the
  transcript, extracts the copywriting lessons, and stores them in SQLite
  memory that feeds every future chat. Manual notes can be saved the same
  way (`POST /api/learnings`).

## Knowledge base (`copy_agent/knowledge/`)

| File | Purpose |
|---|---|
| `00-brand.md` | 8-Thon identity, audience, voice, standing positions - edit this |
| `10-copywriting.md` | Core craft doctrine (adapted from marketing-os-starter, MIT) |
| `20-linkedin.md` | LinkedIn playbook (from agency-agents, MIT) |
| `30-youtube.md` | YouTube packaging + script doctrine (extends agency-agents, MIT) |
| `skills/mindfluence.md` | MindFluence v2.2 cognitive-bias persuasion engine (MIT) |
| `skills/*.md` | Drop any additional skill file here; it loads automatically |

## Config (Fly secrets / env)

- `OpenAI_api` / `OPENAI_API_KEY` - OpenAI key (required)
- `OPENAI_MODEL` - chat model (default `gpt-4.1`)
- `OPENAI_SEARCH_MODEL` - research-mode model (default `gpt-4o-search-preview`)
- `CHAT_STORE_PATH` - SQLite path (default `/data/copy_studio.db`)
- `KNOWLEDGE_MAX_CHARS` - system-prompt budget (default 260000)

## Deploy

Push to `master` → GitHub Actions → `flyctl deploy` (app `lead-scraper-rrhtda`).

The previous life of this repo (Ocean.io/Google Places lead scraper) lives in
git history before the "Copy Studio" rewrite commit.

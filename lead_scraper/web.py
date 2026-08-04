from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .ai_enrichment import enrich_direct_rows_with_openai, openai_configured
from .exporter import export_direct_leads, read_rows, write_lead_export_csv
from .google_places import google_places_configured, search_google_places
from .pipeline import run_pipeline

app = FastAPI(title="8-Thon Intelligence Lead Scraper")


class ScrapeRequest(BaseModel):
    query: str = ""
    location: str = "San Antonio, TX"
    urls: str = Field("", description="Optional website URLs, one per line.")
    city: str = "San Antonio"
    state: str = "TX"
    category: str = ""
    max_results: int = 20
    max_pages: int = 8
    dedupe: str = "email"
    verify_mx: bool = False


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>8-Thon Lead Scraper</title>
    <style>
      :root {{
        color-scheme: dark;
        --bg: #101216;
        --panel: #181c22;
        --panel-soft: #202630;
        --text: #f4f7fb;
        --muted: #aab4c2;
        --line: #303846;
        --accent: #29c7ac;
        --accent-2: #f2b84b;
        --danger: #ff6b6b;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 44px; }}
      header {{ display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; margin-bottom: 28px; }}
      h1 {{ margin: 0 0 8px; font-size: 34px; line-height: 1.1; letter-spacing: 0; }}
      h2 {{ margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }}
      p {{ margin: 0; color: var(--muted); line-height: 1.55; }}
      label {{ display: block; margin-bottom: 7px; color: var(--muted); font-size: 13px; }}
      input, textarea, select {{
        width: 100%;
        border: 1px solid var(--line);
        background: #0d1014;
        color: var(--text);
        border-radius: 8px;
        padding: 11px 12px;
        font: inherit;
      }}
      textarea {{ min-height: 142px; resize: vertical; }}
      button {{
        border: 0;
        border-radius: 8px;
        background: var(--accent);
        color: #03110e;
        cursor: pointer;
        font-weight: 800;
        padding: 12px 15px;
      }}
      button:disabled {{ cursor: wait; opacity: .7; }}
      code {{ color: #d7fff6; }}
      .badge {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--muted); font-size: 14px; white-space: nowrap; }}
      .dot {{ width: 9px; height: 9px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 16px var(--accent); }}
      .grid {{ display: grid; gap: 16px; }}
      .stats {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 18px; }}
      .two {{ grid-template-columns: 1.05fr .95fr; align-items: start; }}
      .form-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 14px 0; }}
      .card {{ border: 1px solid var(--line); background: var(--panel); border-radius: 8px; padding: 18px; }}
      .metric {{ font-size: 28px; font-weight: 750; margin-bottom: 4px; }}
      .label {{ color: var(--muted); font-size: 13px; }}
      .steps {{ display: grid; gap: 12px; }}
      .step {{ display: grid; grid-template-columns: 34px 1fr; gap: 12px; align-items: start; }}
      .num {{ width: 30px; height: 30px; display: grid; place-items: center; border-radius: 50%; background: var(--panel-soft); color: var(--accent); font-weight: 750; }}
      pre {{ margin: 0; padding: 14px; overflow-x: auto; border-radius: 8px; background: #0b0d10; border: 1px solid var(--line); color: #e8edf5; line-height: 1.5; }}
      table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
      th, td {{ padding: 10px 8px; text-align: left; border-bottom: 1px solid var(--line); }}
      th {{ color: var(--muted); font-weight: 600; }}
      .ok {{ color: var(--accent); }}
      .warn {{ color: var(--accent-2); }}
      .danger {{ color: var(--danger); }}
      .actions {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
      .result {{ margin-top: 14px; }}
      footer {{ margin-top: 22px; color: var(--muted); font-size: 13px; }}
      @media (max-width: 820px) {{
        header {{ display: block; }}
        .badge {{ margin-top: 16px; }}
        .stats, .two, .form-grid {{ grid-template-columns: 1fr; }}
        h1 {{ font-size: 28px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>8-Thon Intelligence Lead Scraper</h1>
          <p>Texas-focused lead scraping for blue-collar businesses, owner names, public emails, CSV export, and duplicate memory.</p>
        </div>
        <div class="badge"><span class="dot"></span> Live on Fly.io - v{__version__}</div>
      </header>

      <section class="grid stats" aria-label="System status">
        <div class="card"><div class="metric ok">Online</div><div class="label">Dashboard</div></div>
        <div class="card"><div class="metric">{"Maps" if google_places_configured() else "No Maps"}</div><div class="label">Google API</div></div>
        <div class="card"><div class="metric">{"AI" if openai_configured() else "No AI"}</div><div class="label">OpenAI enrichment</div></div>
        <div class="card"><div class="metric">Memory</div><div class="label">Skips scraped leads</div></div>
      </section>

      <section class="grid two">
        <div class="card">
          <h2>Start Scraping</h2>
          <p>Search Google Maps by business type and location, or paste known business websites. The agent will find websites, crawl public pages, identify possible owners and public emails, and generate a downloadable CSV.</p>
          <form id="scrape-form">
            <div class="form-grid">
              <div><label for="query">Business type</label><input id="query" placeholder="Roofing, HVAC, plumbing"></div>
              <div><label for="location">Search location</label><input id="location" value="San Antonio, TX"></div>
              <div><label for="max_results">Maps results</label><input id="max_results" type="number" min="1" max="20" value="20"></div>
            </div>
            <label for="urls">Optional website URLs</label>
            <textarea id="urls" name="urls" placeholder="https://example-roofing.com&#10;https://example-plumbing.com"></textarea>
            <div class="form-grid">
              <div><label for="city">City</label><input id="city" value="San Antonio"></div>
              <div><label for="state">State</label><input id="state" value="TX"></div>
              <div><label for="category">Industry</label><input id="category" placeholder="Roofing"></div>
            </div>
            <div class="form-grid">
              <div><label for="max_pages">Max pages/site</label><input id="max_pages" type="number" min="1" max="20" value="8"></div>
              <div><label for="dedupe">Dedupe</label><select id="dedupe"><option>email</option><option>domain</option><option>email_or_domain</option><option>none</option></select></div>
              <div><label for="verify_mx">Email domain check</label><select id="verify_mx"><option value="false">Off</option><option value="true">Require MX</option></select></div>
            </div>
            <div class="actions"><button id="run" type="submit">Start Scrape</button></div>
          </form>
          <div id="result" class="result"></div>
        </div>

        <div class="card">
          <h2>Agent Workflow</h2>
          <div class="steps">
            <div class="step"><div class="num">1</div><p><strong>Discovery</strong><br>Use Google Places/API output or Maps scraper exports to collect websites.</p></div>
            <div class="step"><div class="num">2</div><p><strong>Website Enrichment</strong><br>Crawl homepage, contact, about, team, service, and location pages.</p></div>
            <div class="step"><div class="num">3</div><p><strong>AI Review</strong><br>When <code>OPENAI_API_KEY</code> is set, improve owner names and custom opener notes from website text.</p></div>
            <div class="step"><div class="num">4</div><p><strong>CSV Download</strong><br>Drop generic inboxes, dedupe leads, and download the lead list.</p></div>
          </div>
        </div>
      </section>

      <section class="card" style="margin-top: 16px;">
        <h2>Lead CSV Columns</h2>
        <table>
          <thead><tr><th>Column</th><th>Purpose</th></tr></thead>
          <tbody>
            <tr><td>business_name</td><td>Company name from Maps or website seed data.</td></tr>
            <tr><td>owner_name</td><td>Likely owner, founder, CEO, president, or principal when found.</td></tr>
            <tr><td>first_name</td><td>First-name field for downstream tools.</td></tr>
            <tr><td>verified_email</td><td>Direct non-generic email after filtering.</td></tr>
            <tr><td>phone, website, location, industry</td><td>Lead context and segmentation fields.</td></tr>
            <tr><td>custom_opener, source</td><td>Optional AI note and provenance for QA.</td></tr>
          </tbody>
        </table>
      </section>

      <footer>Health check: <code>/health</code> - API status: <code>/api/status</code></footer>
    </main>
    <script>
      const form = document.querySelector("#scrape-form");
      const result = document.querySelector("#result");
      const run = document.querySelector("#run");

      function showSuccess(data, downloadUrl) {{
        result.textContent = "";
        const summary = document.createElement("p");
        summary.className = "ok";
        summary.textContent = `Scrape complete: ${{data.discovery_count}} discovered businesses, ${{data.raw_count}} raw lead rows, ${{data.direct_count}} downloadable leads.`;

        const downloadLine = document.createElement("p");
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = "scraped_leads.csv";
        link.textContent = "Download scraped_leads.csv";
        downloadLine.appendChild(link);

        const pre = document.createElement("pre");
        const code = document.createElement("code");
        code.textContent = data.preview;
        pre.appendChild(code);

        result.append(summary, downloadLine, pre);
      }}

      form.addEventListener("submit", async (event) => {{
        event.preventDefault();
        result.innerHTML = "<p class='warn'>Scraping in progress. This can take a minute for multiple sites.</p>";
        run.disabled = true;

        const payload = {{
          query: document.querySelector("#query").value,
          location: document.querySelector("#location").value,
          urls: document.querySelector("#urls").value,
          city: document.querySelector("#city").value,
          state: document.querySelector("#state").value,
          category: document.querySelector("#category").value,
          max_results: Number(document.querySelector("#max_results").value),
          max_pages: Number(document.querySelector("#max_pages").value),
          dedupe: document.querySelector("#dedupe").value,
          verify_mx: document.querySelector("#verify_mx").value === "true"
        }};

        try {{
          const response = await fetch("/api/scrape", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify(payload)
          }});
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "Scrape failed");
          const blob = new Blob([data.csv], {{ type: "text/csv" }});
          const url = URL.createObjectURL(blob);
          showSuccess(data, url);
        }} catch (error) {{
          result.innerHTML = `<p class="danger">${{error.message}}</p>`;
        }} finally {{
          run.disabled = false;
        }}
      }});
    </script>
  </body>
</html>"""


@app.post("/api/scrape")
def scrape_from_dashboard(request: ScrapeRequest) -> dict[str, str | int]:
    seeds = []
    notes = []

    if request.query.strip():
        if google_places_configured():
            try:
                places = search_google_places(
                    query=request.query,
                    location=request.location,
                    max_results=request.max_results,
                )
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Google Places search failed: {exc}") from exc
            for place in places:
                seeds.append(
                    {
                        "url": normalize_seed_url(place.website),
                        "business_name": place.business_name,
                        "phone": place.phone,
                        "address": place.address,
                        "city": request.city,
                        "state": request.state,
                        "category": place.category or request.category or request.query,
                    }
                )
        else:
            notes.append("GOOGLE_MAPS_API_KEY is not configured, so only pasted websites were scraped.")

    for url in [line.strip() for line in request.urls.splitlines() if line.strip()]:
        seeds.append(
            {
                "url": normalize_seed_url(url),
                "business_name": "",
                "phone": "",
                "address": "",
                "city": request.city,
                "state": request.state,
                "category": request.category or request.query,
            }
        )

    seeds = dedupe_seed_urls(seeds)
    if not seeds:
        return {
            "discovery_count": 0,
            "raw_count": 0,
            "direct_count": 0,
            "csv": "",
            "preview": "No businesses were found. Add GOOGLE_MAPS_API_KEY or paste website URLs.",
        }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        seeds_path = tmp_path / "seeds.csv"
        raw_path = tmp_path / "leads.csv"
        direct_path = tmp_path / "scraped_leads.csv"
        history_path = Path(os.getenv("LEAD_HISTORY_PATH", "data/lead_history.csv"))

        with seeds_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["url", "business_name", "phone", "address", "city", "state", "category"],
            )
            writer.writeheader()
            writer.writerows(seeds)

        try:
            raw_count = run_pipeline(
                seeds_path=seeds_path,
                out_path=raw_path,
                history_path=history_path,
                dedupe=request.dedupe,
                max_pages=request.max_pages,
                timeout=12.0,
            )
            direct_count, _dropped = export_direct_leads(raw_path, direct_path, verify_mx=request.verify_mx)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        direct_rows = read_rows(direct_path)
        if openai_configured() and direct_rows:
            direct_rows = enrich_direct_rows_with_openai(direct_rows)
            write_lead_export_csv(direct_path, direct_rows)
            direct_count = len(direct_rows)

        csv_text = direct_path.read_text(encoding="utf-8")
        preview = csv_text if direct_count <= 5 else preview_csv(direct_path, limit=5)
        if notes:
            preview = "\n".join(notes) + "\n\n" + preview

    return {
        "discovery_count": len(seeds),
        "raw_count": raw_count,
        "direct_count": direct_count,
        "csv": csv_text,
        "preview": preview,
    }


@app.get("/api/status")
def status() -> dict[str, str]:
    return {
        "service": "8-Thon Intelligence Lead Scraper",
        "version": __version__,
        "status": "ok",
        "google_maps": "configured" if google_places_configured() else "missing",
        "openai": "configured" if openai_configured() else "missing",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def preview_csv(path: Path, limit: int) -> str:
    rows = read_rows(path)
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())
    lines = [",".join(fieldnames)]
    for row in rows[:limit]:
        lines.append(",".join(row.get(field, "") for field in fieldnames))
    return "\n".join(lines)


def dedupe_seed_urls(seeds: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    deduped = []
    for seed in seeds:
        key = seed["url"].strip().lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(seed)
    return deduped


def normalize_seed_url(url: str) -> str:
    value = url.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value

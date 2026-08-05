from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .ai_enrichment import openai_configured
from .crawler import UnsafeURL, domain_of, validate_public_url
from .exporter import export_direct_leads, read_rows
from .google_places import google_places_configured, search_google_places
from .lookalike import find_lookalikes, ranked_seed
from .pipeline import run_pipeline

app = FastAPI(title="8-Thon Intelligence Lead Scraper")
LOOKALIKE_RUN_LOCK = Lock()


class ScrapeRequest(BaseModel):
    query: str = ""
    location: str = "San Antonio, TX"
    urls: str = Field("", description="Optional website URLs, one per line.")
    city: str = "San Antonio"
    state: str = "TX"
    category: str = ""
    max_results: int = Field(20, ge=1, le=60)
    max_pages: int = Field(8, ge=1, le=15)
    dedupe: str = "email"
    verify_mx: bool = False


class LookalikeRequest(BaseModel):
    reference_urls: str = Field(..., description="Ideal company website URLs, one per line.")
    negative_urls: str = Field("", description="Optional not-like company URLs, one per line.")
    location: str = "San Antonio, TX"
    city: str = "San Antonio"
    state: str = "TX"
    max_candidates: int = Field(24, ge=4, le=60)
    max_results: int = Field(10, ge=1, le=30)
    max_pages: int = Field(6, ge=1, le=12)
    min_score: float = Field(45.0, ge=0, le=100)
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
      .mode-tabs {{ display: inline-flex; gap: 3px; padding: 3px; margin: 2px 0 16px; border: 1px solid var(--line); border-radius: 8px; background: #0d1014; }}
      .mode-tab {{ background: transparent; color: var(--muted); padding: 9px 13px; }}
      .mode-tab.active {{ background: var(--panel-soft); color: var(--text); }}
      .mode-panel.hidden {{ display: none; }}
      .field-note {{ margin: -2px 0 10px; font-size: 12px; }}
      .matches {{ display: grid; gap: 8px; margin-top: 14px; }}
      .match {{ display: grid; grid-template-columns: 62px 1fr; gap: 10px; padding: 10px 0; border-top: 1px solid var(--line); }}
      .score {{ color: var(--accent); font-weight: 800; }}
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
          <div class="mode-tabs" aria-label="Scrape mode">
            <button class="mode-tab active" type="button" data-mode="lookalike">Lookalike</button>
            <button class="mode-tab" type="button" data-mode="keyword">Keyword</button>
          </div>
          <form id="lookalike-form" class="mode-panel">
            <label for="reference_urls">Ideal company websites</label>
            <textarea id="reference_urls" placeholder="https://ideal-roofing-company.com&#10;https://another-great-fit.com" required></textarea>
            <p class="field-note">Use 2 to 4 strong examples when possible. The agent learns their shared company profile.</p>
            <label for="negative_urls">Not-like websites (optional)</label>
            <textarea id="negative_urls" style="min-height: 86px" placeholder="https://large-national-chain.com"></textarea>
            <div class="form-grid">
              <div><label for="lookalike_location">Target market</label><input id="lookalike_location" value="San Antonio, TX"></div>
              <div><label for="lookalike_candidates">Candidate pool</label><input id="lookalike_candidates" type="number" min="4" max="60" value="24"></div>
              <div><label for="lookalike_results">Results</label><input id="lookalike_results" type="number" min="1" max="30" value="10"></div>
            </div>
            <div class="form-grid">
              <div><label for="lookalike_city">City</label><input id="lookalike_city" value="San Antonio"></div>
              <div><label for="lookalike_state">State</label><input id="lookalike_state" value="TX"></div>
              <div><label for="min_score">Minimum fit score</label><input id="min_score" type="number" min="0" max="100" value="45"></div>
            </div>
            <div class="form-grid">
              <div><label for="lookalike_pages">Max pages/site</label><input id="lookalike_pages" type="number" min="1" max="12" value="6"></div>
              <div><label for="lookalike_dedupe">Dedupe</label><select id="lookalike_dedupe"><option>email</option><option>domain</option><option>email_or_domain</option><option>none</option></select></div>
              <div><label for="lookalike_mx">Email domain check</label><select id="lookalike_mx"><option value="false">Off</option><option value="true">Require MX</option></select></div>
            </div>
            <div class="actions"><button id="lookalike-run" type="submit">Find Similar Companies</button></div>
          </form>
          <form id="scrape-form" class="mode-panel hidden">
            <p>Search Google Maps by business type and location, or paste known business websites.</p>
            <div class="form-grid">
              <div><label for="query">Business type</label><input id="query" placeholder="Roofing, HVAC, plumbing"></div>
              <div><label for="location">Search location</label><input id="location" value="San Antonio, TX"></div>
              <div><label for="max_results">Maps results</label><input id="max_results" type="number" min="1" max="60" value="20"></div>
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
            <div class="step"><div class="num">1</div><p><strong>Profile</strong><br>Read several ideal-company websites and identify their shared services, customers, and business model.</p></div>
            <div class="step"><div class="num">2</div><p><strong>Discover and Rank</strong><br>Search company memory and fresh Maps candidates, then calculate inspectable fit scores.</p></div>
            <div class="step"><div class="num">3</div><p><strong>Enrich</strong><br>Review public business pages for owner evidence, direct emails, phones, and location details.</p></div>
            <div class="step"><div class="num">4</div><p><strong>Export</strong><br>Skip previously scraped leads and produce a clean CSV for the separate outreach agent.</p></div>
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
            <tr><td>owner_role, owner_confidence</td><td>Role and evidence quality for owner-name review.</td></tr>
            <tr><td>first_name</td><td>First-name field for downstream tools.</td></tr>
            <tr><td>verified_email</td><td>Direct non-generic email after filtering.</td></tr>
            <tr><td>phone, website, location, industry</td><td>Lead context and segmentation fields.</td></tr>
            <tr><td>custom_opener, source</td><td>Optional AI note and provenance for QA.</td></tr>
            <tr><td>lookalike_score, similarity_reasons</td><td>Overall company fit and the strongest supporting factors.</td></tr>
          </tbody>
        </table>
      </section>

      <footer>Health check: <code>/health</code> - API status: <code>/api/status</code></footer>
    </main>
    <script>
      const form = document.querySelector("#scrape-form");
      const lookalikeForm = document.querySelector("#lookalike-form");
      const result = document.querySelector("#result");
      const run = document.querySelector("#run");
      const lookalikeRun = document.querySelector("#lookalike-run");

      document.querySelectorAll(".mode-tab").forEach((tab) => {{
        tab.addEventListener("click", () => {{
          document.querySelectorAll(".mode-tab").forEach((item) => item.classList.toggle("active", item === tab));
          lookalikeForm.classList.toggle("hidden", tab.dataset.mode !== "lookalike");
          form.classList.toggle("hidden", tab.dataset.mode !== "keyword");
          result.textContent = "";
        }});
      }});

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

      function showLookalikeSuccess(data, downloadUrl) {{
        result.textContent = "";
        const summary = document.createElement("p");
        summary.className = "ok";
        summary.textContent = `Found ${{data.match_count}} similar companies from ${{data.candidates_discovered}} fresh candidates and a ${{data.catalog_size}}-company memory. ${{data.direct_count}} direct-email leads are ready.`;
        result.appendChild(summary);

        if (data.csv) {{
          const line = document.createElement("p");
          const link = document.createElement("a");
          link.href = downloadUrl;
          link.download = "lookalike_leads.csv";
          link.textContent = "Download lookalike_leads.csv";
          line.appendChild(link);
          result.appendChild(line);
        }}

        const matches = document.createElement("div");
        matches.className = "matches";
        data.matches.forEach((match) => {{
          const row = document.createElement("div");
          row.className = "match";
          const score = document.createElement("div");
          score.className = "score";
          score.textContent = `${{match.score}}%`;
          const detail = document.createElement("div");
          const name = document.createElement("strong");
          name.textContent = match.business_name || match.domain;
          const reason = document.createElement("p");
          reason.textContent = match.reasons;
          detail.append(name, reason);
          row.append(score, detail);
          matches.appendChild(row);
        }});
        result.appendChild(matches);
      }}

      lookalikeForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        result.innerHTML = "<p class='warn'>Building the ideal-company profile and ranking candidates. The first run can take several minutes.</p>";
        lookalikeRun.disabled = true;
        const payload = {{
          reference_urls: document.querySelector("#reference_urls").value,
          negative_urls: document.querySelector("#negative_urls").value,
          location: document.querySelector("#lookalike_location").value,
          city: document.querySelector("#lookalike_city").value,
          state: document.querySelector("#lookalike_state").value,
          max_candidates: Number(document.querySelector("#lookalike_candidates").value),
          max_results: Number(document.querySelector("#lookalike_results").value),
          max_pages: Number(document.querySelector("#lookalike_pages").value),
          min_score: Number(document.querySelector("#min_score").value),
          dedupe: document.querySelector("#lookalike_dedupe").value,
          verify_mx: document.querySelector("#lookalike_mx").value === "true"
        }};
        try {{
          const response = await fetch("/api/lookalikes", {{
            method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify(payload)
          }});
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "Lookalike search failed");
          const blob = new Blob([data.csv], {{ type: "text/csv" }});
          showLookalikeSuccess(data, URL.createObjectURL(blob));
        }} catch (error) {{
          result.innerHTML = `<p class="danger">${{error.message}}</p>`;
        }} finally {{
          lookalikeRun.disabled = false;
        }}
      }});

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


@app.post("/api/lookalikes")
def lookalikes_from_dashboard(request: LookalikeRequest) -> dict[str, object]:
    if not LOOKALIKE_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A lookalike search is already running. Try again when it finishes.")
    try:
        return execute_lookalike_search(request)
    finally:
        LOOKALIKE_RUN_LOCK.release()


def execute_lookalike_search(request: LookalikeRequest) -> dict[str, object]:
    reference_urls = parse_public_urls(request.reference_urls)
    negative_urls = parse_public_urls(request.negative_urls)
    reference_domains = [domain_of(url) for url in reference_urls]
    catalog_path = Path(os.getenv("COMPANY_CATALOG_PATH", "data/company_catalog.db"))

    try:
        search = find_lookalikes(
            reference_urls=reference_urls,
            negative_urls=negative_urls,
            location=request.location,
            city=request.city,
            state=request.state,
            max_candidates=request.max_candidates,
            max_results=request.max_results,
            max_pages=request.max_pages,
            min_score=request.min_score,
            catalog_path=catalog_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Lookalike discovery failed: {exc}") from exc

    seeds = [ranked_seed(item, search.query_id, reference_domains) for item in search.ranked]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        seeds_path = tmp_path / "lookalike_seeds.csv"
        raw_path = tmp_path / "lookalike_leads_raw.csv"
        direct_path = tmp_path / "lookalike_leads.csv"
        history_path = Path(os.getenv("LEAD_HISTORY_PATH", "data/lead_history.db"))

        if seeds:
            with seeds_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(seeds[0].keys()))
                writer.writeheader()
                writer.writerows(seeds)
            raw_count = run_pipeline(
                seeds_path=seeds_path,
                out_path=raw_path,
                history_path=history_path,
                dedupe=request.dedupe,
                max_pages=request.max_pages,
                timeout=12.0,
                pages_by_domain=search.pages_by_domain,
            )
            direct_count, _dropped = export_direct_leads(
                raw_path, direct_path, verify_mx=request.verify_mx
            )
            csv_text = direct_path.read_text(encoding="utf-8")
        else:
            raw_count = 0
            direct_count = 0
            csv_text = ""

    matches = [
        {
            "business_name": item.company.business_name,
            "domain": item.company.domain,
            "website": item.company.url,
            "score": item.score,
            "semantic_score": item.semantic_score,
            "profile_score": item.profile_score,
            "reasons": "; ".join(item.reasons),
        }
        for item in search.ranked
    ]
    return {
        "query_id": search.query_id,
        "candidates_discovered": search.candidates_discovered,
        "catalog_size": search.catalog_size,
        "match_count": len(search.ranked),
        "raw_count": raw_count,
        "direct_count": direct_count,
        "discovery_queries": search.discovery_queries,
        "matches": matches,
        "csv": csv_text,
    }


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
                        "place_id": place.place_id,
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
        normalized_url = normalize_seed_url(url)
        try:
            validate_public_url(normalized_url)
        except UnsafeURL as exc:
            raise HTTPException(status_code=400, detail=f"Unsafe or invalid website URL: {exc}") from exc
        seeds.append(
            {
                "url": normalized_url,
                "place_id": "",
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
        history_path = Path(os.getenv("LEAD_HISTORY_PATH", "data/lead_history.db"))

        with seeds_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["url", "place_id", "business_name", "phone", "address", "city", "state", "category"],
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
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows[:limit])
    return output.getvalue()


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


def parse_public_urls(value: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for line in value.splitlines():
        if not line.strip():
            continue
        url = normalize_seed_url(line)
        try:
            valid = validate_public_url(url)
        except UnsafeURL as exc:
            raise HTTPException(status_code=400, detail=f"Unsafe or invalid website URL: {exc}") from exc
        key = domain_of(valid)
        if key and key not in seen:
            seen.add(key)
            urls.append(valid)
    return urls

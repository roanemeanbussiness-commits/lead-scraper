from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import __version__

app = FastAPI(title="8-Thon Intelligence Lead Scraper")


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
      code {{ color: #d7fff6; }}
      .badge {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 11px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--muted); font-size: 14px; white-space: nowrap; }}
      .dot {{ width: 9px; height: 9px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 16px var(--accent); }}
      .grid {{ display: grid; gap: 16px; }}
      .stats {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 18px; }}
      .two {{ grid-template-columns: 1.2fr .8fr; align-items: start; }}
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
      footer {{ margin-top: 22px; color: var(--muted); font-size: 13px; }}
      @media (max-width: 820px) {{
        header {{ display: block; }}
        .badge {{ margin-top: 16px; }}
        .stats, .two {{ grid-template-columns: 1fr; }}
        h1 {{ font-size: 28px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>8-Thon Intelligence Lead Scraper</h1>
          <p>Texas-focused lead discovery pipeline for blue-collar businesses, owner names, direct emails, CSV export, and duplicate memory.</p>
        </div>
        <div class="badge"><span class="dot"></span> Live on Fly.io · v{__version__}</div>
      </header>

      <section class="grid stats" aria-label="System status">
        <div class="card"><div class="metric ok">Online</div><div class="label">Web dashboard</div></div>
        <div class="card"><div class="metric">CSV</div><div class="label">Email-agent export</div></div>
        <div class="card"><div class="metric">Memory</div><div class="label">Skips scraped leads</div></div>
        <div class="card"><div class="metric warn">CLI</div><div class="label">Scraper runs as a job</div></div>
      </section>

      <section class="grid two">
        <div class="card">
          <h2>Agent Workflow</h2>
          <div class="steps">
            <div class="step"><div class="num">1</div><p><strong>Discovery</strong><br>Feed the agent Google Maps/search exports with business name, website, phone, location, and trade.</p></div>
            <div class="step"><div class="num">2</div><p><strong>Website Enrichment</strong><br>Crawl homepage, contact, about, team, service, and location pages for public emails and owner signals.</p></div>
            <div class="step"><div class="num">3</div><p><strong>Memory Filter</strong><br>Skip previously exported emails or domains using <code>data/lead_history.csv</code>.</p></div>
            <div class="step"><div class="num">4</div><p><strong>Email Agent Export</strong><br>Drop generic inboxes and write direct-lead CSVs with <code>first_name</code> ready for campaign templates.</p></div>
          </div>
        </div>

        <div class="card">
          <h2>Run Commands</h2>
          <pre><code>python -m lead_scraper scrape ^
  --seeds data/sample_seeds.csv ^
  --out output/leads.csv

python -m lead_scraper export-direct ^
  --input output/leads.csv ^
  --out output/direct_leads.csv</code></pre>
        </div>
      </section>

      <section class="card" style="margin-top: 16px;">
        <h2>Campaign CSV Columns</h2>
        <table>
          <thead><tr><th>Column</th><th>Purpose</th></tr></thead>
          <tbody>
            <tr><td>business_name</td><td>Company name from Maps or website seed data.</td></tr>
            <tr><td>owner_name</td><td>Likely owner, founder, CEO, president, or principal when found.</td></tr>
            <tr><td>first_name</td><td>Template tag for the outbound email agent.</td></tr>
            <tr><td>verified_email</td><td>Direct non-generic email after filtering.</td></tr>
            <tr><td>phone, website, location, industry</td><td>Sales context and campaign segmentation fields.</td></tr>
            <tr><td>custom_opener, source</td><td>Personalization and provenance for outreach QA.</td></tr>
          </tbody>
        </table>
      </section>

      <footer>Health check: <code>/health</code> · API status: <code>/api/status</code></footer>
    </main>
  </body>
</html>"""


@app.get("/api/status")
def status() -> dict[str, str]:
    return {
        "service": "8-Thon Intelligence Lead Scraper",
        "version": __version__,
        "status": "ok",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

from __future__ import annotations


def render_dashboard(version: str, maps_configured: bool, openai_configured: bool) -> str:
    maps_status = "Connected" if maps_configured else "Missing"
    ai_status = "Connected" if openai_configured else "Missing"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>8-Thon Intelligence</title>
    <style>
      :root {{
        color-scheme: dark;
        --canvas: #0d0f13;
        --surface: #14171d;
        --surface-raised: #1a1e26;
        --surface-soft: #202531;
        --line: #2a303b;
        --line-strong: #3b4452;
        --text: #f5f7fa;
        --muted: #99a3b2;
        --subtle: #697586;
        --blue: #579dff;
        --blue-soft: #172945;
        --mint: #63ddb1;
        --mint-soft: #13352d;
        --amber: #f1be63;
        --amber-soft: #3a2c15;
        --red: #ff7b7b;
      }}
      * {{ box-sizing: border-box; }}
      html, body {{ min-height: 100%; }}
      body {{
        margin: 0;
        background: var(--canvas);
        color: var(--text);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 14px;
      }}
      button, input, textarea, select {{ font: inherit; letter-spacing: 0; }}
      button {{ cursor: pointer; }}
      .app-shell {{ min-height: 100vh; display: grid; grid-template-columns: 74px minmax(0, 1fr); }}
      .rail {{
        position: sticky; top: 0; height: 100vh; border-right: 1px solid var(--line);
        background: #101217; display: flex; flex-direction: column; align-items: center; padding: 16px 10px;
      }}
      .brand {{
        width: 40px; height: 40px; display: grid; place-items: center; border: 1px solid #376da9;
        border-radius: 8px; background: var(--blue-soft); color: #d8e9ff; font-weight: 850; margin-bottom: 22px;
      }}
      .rail-nav {{ display: grid; gap: 8px; width: 100%; }}
      .rail-button {{
        width: 52px; min-height: 48px; margin: auto; display: grid; place-items: center; gap: 2px;
        border: 0; border-radius: 8px; background: transparent; color: var(--subtle); padding: 6px;
      }}
      .rail-button.active {{ background: var(--surface-soft); color: var(--blue); }}
      .rail-button span {{ font-size: 10px; }}
      .rail-bottom {{ margin-top: auto; display: grid; gap: 8px; }}
      .status-dot {{ width: 9px; height: 9px; border-radius: 50%; background: var(--mint); }}
      .app {{ min-width: 0; }}
      .topbar {{
        min-height: 64px; border-bottom: 1px solid var(--line); display: flex; align-items: center;
        justify-content: space-between; gap: 18px; padding: 0 22px; background: rgba(20, 23, 29, .96);
      }}
      .title-line {{ display: flex; align-items: baseline; gap: 10px; min-width: 0; }}
      h1 {{ margin: 0; font-size: 17px; line-height: 1.2; letter-spacing: 0; }}
      .version {{ color: var(--subtle); font-size: 12px; }}
      .connection-row {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }}
      .connection {{
        display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--line); border-radius: 7px;
        padding: 7px 9px; color: var(--muted); background: var(--surface); font-size: 12px;
      }}
      .connection.good .status-dot {{ background: var(--mint); }}
      .connection.bad .status-dot {{ background: var(--red); }}
      .modebar {{
        min-height: 52px; display: flex; align-items: end; gap: 24px; border-bottom: 1px solid var(--line);
        padding: 0 22px; background: var(--surface);
      }}
      .mode-tab {{
        height: 52px; border: 0; border-bottom: 2px solid transparent; background: transparent;
        color: var(--muted); padding: 0 2px; font-weight: 650;
      }}
      .mode-tab.active {{ border-bottom-color: var(--blue); color: var(--text); }}
      .workbench {{ display: grid; grid-template-columns: 330px minmax(0, 1fr); min-height: calc(100vh - 116px); }}
      .filter-rail {{ border-right: 1px solid var(--line); background: var(--surface); min-width: 0; }}
      .filter-head {{ padding: 17px 18px 13px; border-bottom: 1px solid var(--line); }}
      .filter-head h2, .results-title h2 {{ margin: 0; font-size: 14px; letter-spacing: 0; }}
      .filter-head p {{ margin: 5px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }}
      .filter-form {{ padding-bottom: 20px; }}
      .filter-section {{ padding: 15px 18px; border-bottom: 1px solid var(--line); }}
      .filter-label {{
        display: flex; align-items: center; gap: 8px; margin-bottom: 9px; color: #cbd2dc; font-size: 12px; font-weight: 650;
      }}
      .filter-label svg {{ width: 15px; height: 15px; color: var(--muted); }}
      input, textarea, select {{
        width: 100%; border: 1px solid var(--line-strong); border-radius: 7px; background: #0f1217;
        color: var(--text); padding: 9px 10px; outline: 0;
      }}
      input:focus, textarea:focus, select:focus {{ border-color: var(--blue); box-shadow: 0 0 0 2px rgba(87, 157, 255, .15); }}
      textarea {{ resize: vertical; min-height: 94px; line-height: 1.45; }}
      textarea.compact {{ min-height: 66px; }}
      .help {{ color: var(--subtle); font-size: 11px; line-height: 1.45; margin: 7px 0 0; }}
      .segmented {{ display: grid; grid-template-columns: 1fr 1fr; gap: 3px; padding: 3px; border: 1px solid var(--line); border-radius: 7px; background: #0f1217; }}
      .segmented input {{ position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }}
      .segmented label {{ border-radius: 5px; color: var(--muted); text-align: center; padding: 8px 6px; cursor: pointer; font-weight: 650; }}
      .segmented input:checked + label {{ background: var(--surface-soft); color: var(--text); }}
      .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }}
      .mini-label {{ display: block; color: var(--subtle); font-size: 11px; margin: 0 0 6px; }}
      details {{ border-bottom: 1px solid var(--line); }}
      details summary {{
        list-style: none; padding: 14px 18px; display: flex; align-items: center; justify-content: space-between;
        color: #cbd2dc; cursor: pointer; font-size: 12px; font-weight: 650;
      }}
      details summary::-webkit-details-marker {{ display: none; }}
      details[open] summary {{ border-bottom: 1px solid var(--line); }}
      .details-body {{ padding: 14px 18px 17px; display: grid; gap: 12px; }}
      .toggle-row {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; color: var(--muted); }}
      .toggle-row input {{ width: 17px; height: 17px; accent-color: var(--blue); }}
      .range-row {{ display: grid; grid-template-columns: 1fr 42px; gap: 10px; align-items: center; }}
      input[type="range"] {{ padding: 0; border: 0; accent-color: var(--blue); box-shadow: none; }}
      output {{ color: var(--blue); font-weight: 750; text-align: right; }}
      .run-zone {{ padding: 16px 18px; }}
      .primary {{
        width: 100%; min-height: 42px; border: 1px solid #6ca9ff; border-radius: 7px; background: var(--blue);
        color: #07101f; font-weight: 800; display: inline-flex; justify-content: center; align-items: center; gap: 8px;
      }}
      .primary:disabled {{ cursor: wait; opacity: .65; }}
      .usage-preview {{ margin-top: 10px; display: flex; justify-content: space-between; color: var(--subtle); font-size: 11px; }}
      .hidden {{ display: none !important; }}
      .results-pane {{ min-width: 0; background: var(--canvas); }}
      .results-toolbar {{
        min-height: 64px; display: flex; justify-content: space-between; align-items: center; gap: 16px;
        padding: 12px 18px; border-bottom: 1px solid var(--line); background: var(--surface);
      }}
      .results-title {{ display: flex; align-items: baseline; gap: 10px; min-width: 0; }}
      .result-count {{ color: var(--muted); font-size: 12px; }}
      .toolbar-actions {{ display: flex; gap: 8px; align-items: center; }}
      .secondary, .icon-button {{
        min-height: 34px; border: 1px solid var(--line-strong); border-radius: 7px; background: var(--surface-raised);
        color: #dce2ea; padding: 7px 10px; display: inline-flex; gap: 7px; align-items: center; justify-content: center;
      }}
      .secondary:disabled {{ opacity: .45; cursor: default; }}
      .secondary svg, .icon-button svg, .primary svg {{ width: 15px; height: 15px; }}
      .metrics {{
        display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--line);
        background: var(--surface);
      }}
      .metric {{ padding: 12px 18px; border-right: 1px solid var(--line); }}
      .metric:last-child {{ border-right: 0; }}
      .metric-value {{ font-size: 16px; font-weight: 780; }}
      .metric-label {{ color: var(--subtle); font-size: 11px; margin-top: 3px; }}
      .table-wrap {{ width: 100%; overflow: auto; }}
      table {{ width: 100%; min-width: 960px; border-collapse: collapse; table-layout: fixed; }}
      th {{
        position: sticky; top: 0; z-index: 1; background: #11141a; color: var(--subtle); font-size: 11px;
        font-weight: 650; text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line);
      }}
      td {{ padding: 12px; border-bottom: 1px solid var(--line); vertical-align: middle; color: #d9dee6; }}
      tbody tr:hover {{ background: #12161d; }}
      .col-score {{ width: 86px; }}
      .col-company {{ width: 230px; }}
      .col-fit {{ width: 215px; }}
      .col-signals {{ width: 190px; }}
      .col-contact {{ width: 220px; }}
      .col-actions {{ width: 92px; }}
      .grade {{
        display: inline-flex; align-items: center; justify-content: space-between; gap: 6px; min-width: 58px;
        border-radius: 7px; padding: 7px 9px; font-weight: 850;
      }}
      .grade-a {{ color: var(--mint); background: var(--mint-soft); }}
      .grade-b {{ color: var(--blue); background: var(--blue-soft); }}
      .grade-c {{ color: var(--amber); background: var(--amber-soft); }}
      .company-name {{ color: var(--text); font-weight: 720; margin-bottom: 4px; }}
      .domain, .cell-note {{ color: var(--subtle); font-size: 11px; overflow-wrap: anywhere; }}
      .reason {{ line-height: 1.45; color: #c5ccd6; font-size: 12px; }}
      .badges {{ display: flex; flex-wrap: wrap; gap: 5px; }}
      .signal {{ padding: 4px 6px; border: 1px solid var(--line); border-radius: 5px; color: var(--muted); font-size: 10px; white-space: nowrap; }}
      .contact-name {{ color: #dce2ea; font-size: 12px; margin-bottom: 3px; }}
      .contact-email {{ color: var(--blue); font-size: 11px; overflow-wrap: anywhere; }}
      .action-pair {{ display: flex; gap: 5px; }}
      .icon-button {{ width: 34px; padding: 0; color: var(--muted); }}
      .icon-button.fit.active {{ color: var(--mint); border-color: #34735f; background: var(--mint-soft); }}
      .icon-button.not-fit.active {{ color: var(--red); border-color: #7e3e43; background: #35191d; }}
      .empty {{ min-height: 470px; display: grid; place-items: center; text-align: center; padding: 40px; }}
      .empty-inner {{ max-width: 390px; }}
      .empty-icon {{ width: 48px; height: 48px; display: grid; place-items: center; margin: 0 auto 14px; border: 1px solid var(--line); border-radius: 8px; color: var(--blue); background: var(--surface); }}
      .empty h3 {{ margin: 0 0 7px; font-size: 15px; }}
      .empty p {{ margin: 0; color: var(--muted); line-height: 1.55; font-size: 12px; }}
      .notice {{ margin: 16px 18px; padding: 11px 12px; border: 1px solid var(--line); border-radius: 7px; color: var(--muted); background: var(--surface); }}
      .notice.error {{ border-color: #70373d; color: #ffb2b2; }}
      pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; color: var(--muted); }}
      @media (max-width: 980px) {{
        .app-shell {{ grid-template-columns: 1fr; }}
        .rail {{ position: static; width: 100%; height: 54px; flex-direction: row; justify-content: space-between; border-right: 0; border-bottom: 1px solid var(--line); padding: 7px 12px; }}
        .brand {{ width: 38px; height: 38px; margin: 0; }}
        .rail-nav {{ display: flex; width: auto; }}
        .rail-button {{ width: 44px; min-height: 38px; }}
        .rail-button span, .rail-bottom {{ display: none; }}
        .workbench {{ grid-template-columns: 1fr; }}
        .filter-rail {{ border-right: 0; border-bottom: 1px solid var(--line); }}
        .filter-form {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .filter-head, .run-zone, details {{ grid-column: 1 / -1; }}
        .filter-section {{ min-width: 0; }}
      }}
      @media (max-width: 640px) {{
        .topbar {{ align-items: flex-start; padding: 13px 14px; }}
        .title-line {{ display: grid; gap: 3px; }}
        .connection span:last-child {{ display: none; }}
        .modebar {{ padding: 0 14px; gap: 18px; overflow-x: auto; }}
        .filter-form {{ display: block; }}
        .results-toolbar {{ align-items: flex-start; }}
        .results-title {{ display: grid; gap: 3px; }}
        .secondary span {{ display: none; }}
        .metrics {{ grid-template-columns: 1fr 1fr; }}
        .metric:nth-child(2) {{ border-right: 0; }}
        .metric:nth-child(-n+2) {{ border-bottom: 1px solid var(--line); }}
      }}
    </style>
  </head>
  <body>
    <div class="app-shell">
      <aside class="rail" aria-label="Main navigation">
        <div class="brand" title="8-Thon Intelligence">8T</div>
        <nav class="rail-nav">
          <button class="rail-button active" type="button" title="Discover"><i data-lucide="search"></i><span>Discover</span></button>
        </nav>
        <div class="rail-bottom"><div class="status-dot" title="Service online"></div></div>
      </aside>

      <main class="app">
        <header class="topbar">
          <div class="title-line"><h1>Company discovery</h1><span class="version">8-Thon Intelligence v{version}</span></div>
          <div class="connection-row">
            <div class="connection {'good' if maps_configured else 'bad'}"><span class="status-dot"></span><span>Maps {maps_status}</span></div>
            <div class="connection {'good' if openai_configured else 'bad'}"><span class="status-dot"></span><span>AI {ai_status}</span></div>
          </div>
        </header>

        <div class="modebar" role="tablist">
          <button class="mode-tab active" type="button" data-mode="lookalike" role="tab">Company lookalikes</button>
          <button class="mode-tab" type="button" data-mode="keyword" role="tab">Keyword discovery</button>
        </div>

        <div class="workbench">
          <aside class="filter-rail">
            <div class="filter-head"><h2>Search filters</h2><p>Build an ICP from companies you already know, then narrow the matching pool.</p></div>

            <form id="lookalike-form" class="filter-form">
              <div class="filter-section">
                <label class="filter-label" for="reference_urls"><i data-lucide="building-2"></i>Company lookalikes</label>
                <textarea id="reference_urls" placeholder="acme-roofing.com&#10;besthvac.com" required></textarea>
                <p class="help">Enter 2 to 4 ideal company domains, one per line.</p>
              </div>
              <div class="filter-section">
                <span class="filter-label"><i data-lucide="scan-search"></i>Matching mode</span>
                <div class="segmented">
                  <input id="mode-precise" type="radio" name="matching_mode" value="precise" checked><label for="mode-precise">Precise</label>
                  <input id="mode-broad" type="radio" name="matching_mode" value="broad"><label for="mode-broad">Broad</label>
                </div>
              </div>
              <div class="filter-section">
                <label class="filter-label" for="negative_urls"><i data-lucide="circle-slash-2"></i>Exclude lookalikes</label>
                <textarea class="compact" id="negative_urls" placeholder="national-chain.com"></textarea>
              </div>
              <div class="filter-section">
                <label class="filter-label" for="lookalike_location"><i data-lucide="map-pin"></i>Headquarter location</label>
                <input id="lookalike_location" value="San Antonio, TX">
                <div class="split" style="margin-top:9px">
                  <div><label class="mini-label" for="lookalike_city">City</label><input id="lookalike_city" value="San Antonio"></div>
                  <div><label class="mini-label" for="lookalike_state">State</label><input id="lookalike_state" value="TX"></div>
                </div>
              </div>

              <details>
                <summary><span>Firmographic filters</span><i data-lucide="chevron-down"></i></summary>
                <div class="details-body">
                  <div><label class="mini-label" for="industries_any">Industry includes</label><input id="industries_any" placeholder="roofing, construction"></div>
                  <div><label class="mini-label" for="industries_none">Industry excludes</label><input id="industries_none" placeholder="software, wholesale"></div>
                  <label class="toggle-row" for="require_hiring"><span>Actively hiring</span><input id="require_hiring" type="checkbox"></label>
                  <label class="toggle-row" for="ecommerce_only"><span>E-commerce detected</span><input id="ecommerce_only" type="checkbox"></label>
                </div>
              </details>

              <details>
                <summary><span>Keywords and technologies</span><i data-lucide="chevron-down"></i></summary>
                <div class="details-body">
                  <div><label class="mini-label" for="keywords_any">Any keyword</label><input id="keywords_any" placeholder="commercial, emergency"></div>
                  <div><label class="mini-label" for="keywords_all">All keywords</label><input id="keywords_all" placeholder="licensed, insured"></div>
                  <div><label class="mini-label" for="keywords_none">Exclude keywords</label><input id="keywords_none" placeholder="franchise"></div>
                  <div><label class="mini-label" for="technologies_any">Any technology</label><input id="technologies_any" placeholder="wordpress, hubspot"></div>
                  <div><label class="mini-label" for="technologies_none">Exclude technologies</label><input id="technologies_none" placeholder="shopify"></div>
                </div>
              </details>

              <details>
                <summary><span>Search controls</span><i data-lucide="chevron-down"></i></summary>
                <div class="details-body">
                  <div class="split">
                    <div><label class="mini-label" for="lookalike_candidates">Candidate pool</label><input id="lookalike_candidates" type="number" min="4" max="60" value="24"></div>
                    <div><label class="mini-label" for="lookalike_results">Results</label><input id="lookalike_results" type="number" min="1" max="30" value="10"></div>
                  </div>
                  <div><label class="mini-label" for="min_score">Minimum fit score</label><div class="range-row"><input id="min_score" type="range" min="0" max="95" value="45"><output id="min_score_value">45</output></div></div>
                  <div class="split">
                    <div><label class="mini-label" for="lookalike_pages">Pages/site</label><input id="lookalike_pages" type="number" min="1" max="12" value="6"></div>
                    <div><label class="mini-label" for="freshness">Fresh within</label><select id="freshness"><option value="3">3 months</option><option value="6">6 months</option><option value="12" selected>12 months</option><option value="24">24 months</option></select></div>
                  </div>
                  <div class="split">
                    <div><label class="mini-label" for="lookalike_dedupe">Dedupe</label><select id="lookalike_dedupe"><option>email</option><option>domain</option><option>email_or_domain</option><option>none</option></select></div>
                    <div><label class="mini-label" for="lookalike_mx">Require MX</label><select id="lookalike_mx"><option value="false">No</option><option value="true">Yes</option></select></div>
                  </div>
                </div>
              </details>

              <div class="run-zone">
                <button id="lookalike-run" class="primary" type="submit"><i data-lucide="sparkles"></i>Preview matches</button>
                <div class="usage-preview"><span>Max fresh profiles</span><span id="candidate-estimate">24</span></div>
              </div>
            </form>

            <form id="keyword-form" class="filter-form hidden">
              <div class="filter-section"><label class="filter-label" for="query"><i data-lucide="briefcase-business"></i>Business type</label><input id="query" placeholder="Roofing, HVAC, plumbing"></div>
              <div class="filter-section"><label class="filter-label" for="location"><i data-lucide="map-pin"></i>Search location</label><input id="location" value="San Antonio, TX"></div>
              <div class="filter-section"><label class="filter-label" for="urls"><i data-lucide="link"></i>Known websites</label><textarea id="urls" placeholder="example-roofing.com"></textarea></div>
              <div class="filter-section"><div class="split"><div><label class="mini-label" for="city">City</label><input id="city" value="San Antonio"></div><div><label class="mini-label" for="state">State</label><input id="state" value="TX"></div></div></div>
              <div class="filter-section"><div class="split"><div><label class="mini-label" for="category">Industry</label><input id="category" placeholder="Roofing"></div><div><label class="mini-label" for="max_results">Maps results</label><input id="max_results" type="number" min="1" max="60" value="20"></div></div></div>
              <div class="filter-section"><div class="split"><div><label class="mini-label" for="max_pages">Pages/site</label><input id="max_pages" type="number" min="1" max="15" value="8"></div><div><label class="mini-label" for="verify_mx">Require MX</label><select id="verify_mx"><option value="false">No</option><option value="true">Yes</option></select></div></div></div>
              <div class="run-zone"><button id="keyword-run" class="primary" type="submit"><i data-lucide="search"></i>Run discovery</button></div>
            </form>
          </aside>

          <section class="results-pane" aria-live="polite">
            <div class="results-toolbar">
              <div class="results-title"><h2 id="results-heading">Company matches</h2><span id="result-count" class="result-count">No search run</span></div>
              <div class="toolbar-actions"><button id="download" class="secondary" type="button" disabled><i data-lucide="download"></i><span>Export CSV</span></button></div>
            </div>
            <div id="metrics" class="metrics hidden">
              <div class="metric"><div id="metric-matches" class="metric-value">0</div><div class="metric-label">Matches</div></div>
              <div class="metric"><div id="metric-emails" class="metric-value">0</div><div class="metric-label">Direct emails</div></div>
              <div class="metric"><div id="metric-catalog" class="metric-value">0</div><div class="metric-label">Companies in memory</div></div>
              <div class="metric"><div id="metric-usage" class="metric-value">0</div><div class="metric-label">AI calls estimated</div></div>
            </div>
            <div id="notice"></div>
            <div id="empty" class="empty"><div class="empty-inner"><div class="empty-icon"><i data-lucide="radar"></i></div><h3 id="empty-title">Find companies that resemble your best customers</h3><p id="empty-copy">Add ideal company domains and preview a scored, filterable match list before exporting direct-email leads.</p></div></div>
            <div id="table-wrap" class="table-wrap hidden">
              <table>
                <thead><tr><th class="col-score">Score</th><th class="col-company">Company</th><th class="col-fit">Why it fits</th><th class="col-signals">Signals</th><th class="col-contact">Contact</th><th class="col-actions">Fit</th></tr></thead>
                <tbody id="match-rows"></tbody>
              </table>
            </div>
            <pre id="keyword-preview" class="notice hidden"></pre>
          </section>
        </div>
      </main>
    </div>
    <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
    <script>
      const state = {{ csv: "", filename: "", queryId: "" }};
      const lookalikeForm = document.querySelector("#lookalike-form");
      const keywordForm = document.querySelector("#keyword-form");
      const empty = document.querySelector("#empty");
      const tableWrap = document.querySelector("#table-wrap");
      const rows = document.querySelector("#match-rows");
      const notice = document.querySelector("#notice");
      const metrics = document.querySelector("#metrics");
      const download = document.querySelector("#download");
      const keywordPreview = document.querySelector("#keyword-preview");
      const minScore = document.querySelector("#min_score");
      minScore.addEventListener("input", () => document.querySelector("#min_score_value").textContent = minScore.value);
      document.querySelector("#lookalike_candidates").addEventListener("input", (event) => document.querySelector("#candidate-estimate").textContent = event.target.value);

      document.querySelectorAll(".mode-tab").forEach((tab) => tab.addEventListener("click", () => {{
        document.querySelectorAll(".mode-tab").forEach((item) => item.classList.toggle("active", item === tab));
        const lookalike = tab.dataset.mode === "lookalike";
        lookalikeForm.classList.toggle("hidden", !lookalike);
        keywordForm.classList.toggle("hidden", lookalike);
        document.querySelector("#results-heading").textContent = lookalike ? "Company matches" : "Keyword leads";
        document.querySelector("#empty-title").textContent = lookalike ? "Find companies that resemble your best customers" : "Discover local businesses by trade";
        document.querySelector("#empty-copy").textContent = lookalike ? "Add ideal company domains and preview a scored, filterable match list before exporting direct-email leads." : "Choose a business type and location, or paste known websites, to build a direct-email lead list.";
        resetResults();
      }}));

      function resetResults() {{
        state.csv = ""; state.filename = ""; state.queryId = "";
        rows.textContent = ""; notice.textContent = ""; download.disabled = true;
        empty.classList.remove("hidden"); tableWrap.classList.add("hidden"); metrics.classList.add("hidden");
        keywordPreview.classList.add("hidden"); document.querySelector("#result-count").textContent = "No search run";
      }}

      function setBusy(button, busy, label) {{
        button.disabled = busy;
        button.innerHTML = busy ? '<i data-lucide="loader-circle"></i>Working...' : label;
        if (window.lucide) lucide.createIcons();
      }}

      function showError(message) {{
        notice.innerHTML = "";
        const box = document.createElement("div"); box.className = "notice error"; box.textContent = message; notice.appendChild(box);
      }}

      function badge(text) {{
        const item = document.createElement("span"); item.className = "signal"; item.textContent = text; return item;
      }}

      function renderMatches(data) {{
        state.csv = data.csv || ""; state.filename = "lookalike_leads.csv"; state.queryId = data.query_id;
        download.disabled = !state.csv;
        empty.classList.add("hidden"); tableWrap.classList.remove("hidden"); metrics.classList.remove("hidden"); keywordPreview.classList.add("hidden");
        document.querySelector("#result-count").textContent = `${{data.match_count}} ranked companies · ${{data.filtered_count}} filtered out`;
        document.querySelector("#metric-matches").textContent = data.match_count;
        document.querySelector("#metric-emails").textContent = data.direct_count;
        document.querySelector("#metric-catalog").textContent = data.catalog_size;
        document.querySelector("#metric-usage").textContent = data.usage.estimated_openai_calls;
        rows.textContent = "";

        data.matches.forEach((match) => {{
          const row = document.createElement("tr");
          const scoreCell = document.createElement("td");
          const grade = document.createElement("span"); grade.className = `grade grade-${{match.grade.toLowerCase()}}`; grade.textContent = `${{match.grade}}  ${{Math.round(match.score)}}`;
          scoreCell.appendChild(grade);

          const companyCell = document.createElement("td");
          const company = document.createElement("div"); company.className = "company-name"; company.textContent = match.business_name || match.domain;
          const domain = document.createElement("div"); domain.className = "domain"; domain.textContent = match.domain;
          const location = document.createElement("div"); location.className = "cell-note"; location.textContent = [match.industry, match.location].filter(Boolean).join(" · ");
          companyCell.append(company, domain, location);

          const fitCell = document.createElement("td"); const reason = document.createElement("div"); reason.className = "reason"; reason.textContent = match.reasons; fitCell.appendChild(reason);
          const signalsCell = document.createElement("td"); const badges = document.createElement("div"); badges.className = "badges";
          if (match.careers_active) badges.appendChild(badge("Hiring"));
          if (match.ecommerce) badges.appendChild(badge("E-commerce"));
          (match.technologies || []).slice(0, 3).forEach((item) => badges.appendChild(badge(item)));
          if (!badges.childElementCount) badges.appendChild(badge("Public website")); signalsCell.appendChild(badges);

          const contactCell = document.createElement("td");
          const owner = document.createElement("div"); owner.className = "contact-name"; owner.textContent = match.owner_name || "Owner not confirmed";
          const email = document.createElement("div"); email.className = "contact-email"; email.textContent = match.verified_email || match.phone || "No direct contact found";
          contactCell.append(owner, email);

          const actionsCell = document.createElement("td"); const pair = document.createElement("div"); pair.className = "action-pair";
          const fit = document.createElement("button"); fit.type = "button"; fit.className = "icon-button fit"; fit.title = "Mark as fit"; fit.setAttribute("aria-label", `Mark ${{match.domain}} as fit`); fit.innerHTML = '<i data-lucide="thumbs-up"></i>';
          const notFit = document.createElement("button"); notFit.type = "button"; notFit.className = "icon-button not-fit"; notFit.title = "Mark as not a fit"; notFit.setAttribute("aria-label", `Mark ${{match.domain}} as not a fit`); notFit.innerHTML = '<i data-lucide="thumbs-down"></i>';
          fit.addEventListener("click", () => saveFeedback(match.domain, "fit", fit, notFit));
          notFit.addEventListener("click", () => saveFeedback(match.domain, "not_fit", notFit, fit));
          pair.append(fit, notFit); actionsCell.appendChild(pair);
          row.append(scoreCell, companyCell, fitCell, signalsCell, contactCell, actionsCell); rows.appendChild(row);
        }});
        if (window.lucide) lucide.createIcons();
      }}

      async function saveFeedback(domain, label, activeButton, otherButton) {{
        try {{
          const response = await fetch("/api/lookalike-feedback", {{method: "POST", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({{query_id: state.queryId, domain, label}})}});
          if (!response.ok) throw new Error("Could not save feedback");
          activeButton.classList.add("active"); otherButton.classList.remove("active");
        }} catch (error) {{ showError(error.message); }}
      }}

      lookalikeForm.addEventListener("submit", async (event) => {{
        event.preventDefault(); notice.textContent = "";
        const button = document.querySelector("#lookalike-run"); setBusy(button, true, "");
        const payload = {{
          reference_urls: document.querySelector("#reference_urls").value,
          negative_urls: document.querySelector("#negative_urls").value,
          matching_mode: document.querySelector('input[name="matching_mode"]:checked').value,
          location: document.querySelector("#lookalike_location").value,
          city: document.querySelector("#lookalike_city").value,
          state: document.querySelector("#lookalike_state").value,
          max_candidates: Number(document.querySelector("#lookalike_candidates").value),
          max_results: Number(document.querySelector("#lookalike_results").value),
          max_pages: Number(document.querySelector("#lookalike_pages").value),
          min_score: Number(minScore.value),
          updated_within_months: Number(document.querySelector("#freshness").value),
          dedupe: document.querySelector("#lookalike_dedupe").value,
          verify_mx: document.querySelector("#lookalike_mx").value === "true",
          industries_any: document.querySelector("#industries_any").value,
          industries_none: document.querySelector("#industries_none").value,
          keywords_any: document.querySelector("#keywords_any").value,
          keywords_all: document.querySelector("#keywords_all").value,
          keywords_none: document.querySelector("#keywords_none").value,
          technologies_any: document.querySelector("#technologies_any").value,
          technologies_none: document.querySelector("#technologies_none").value,
          require_hiring: document.querySelector("#require_hiring").checked,
          ecommerce_only: document.querySelector("#ecommerce_only").checked
        }};
        try {{
          const response = await fetch("/api/lookalikes", {{method: "POST", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify(payload)}});
          const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Lookalike search failed"); renderMatches(data);
        }} catch (error) {{ showError(error.message); }}
        finally {{ setBusy(button, false, '<i data-lucide="sparkles"></i>Preview matches'); }}
      }});

      keywordForm.addEventListener("submit", async (event) => {{
        event.preventDefault(); notice.textContent = ""; const button = document.querySelector("#keyword-run"); setBusy(button, true, "");
        const payload = {{query: document.querySelector("#query").value, location: document.querySelector("#location").value, urls: document.querySelector("#urls").value, city: document.querySelector("#city").value, state: document.querySelector("#state").value, category: document.querySelector("#category").value, max_results: Number(document.querySelector("#max_results").value), max_pages: Number(document.querySelector("#max_pages").value), dedupe: "email", verify_mx: document.querySelector("#verify_mx").value === "true"}};
        try {{
          const response = await fetch("/api/scrape", {{method: "POST", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify(payload)}});
          const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Discovery failed");
          state.csv = data.csv || ""; state.filename = "scraped_leads.csv"; download.disabled = !state.csv; empty.classList.add("hidden"); tableWrap.classList.add("hidden"); metrics.classList.remove("hidden"); keywordPreview.classList.remove("hidden"); keywordPreview.textContent = data.preview || "No direct-email leads found.";
          document.querySelector("#result-count").textContent = `${{data.direct_count}} direct-email leads`;
          document.querySelector("#metric-matches").textContent = data.discovery_count; document.querySelector("#metric-emails").textContent = data.direct_count; document.querySelector("#metric-catalog").textContent = "—"; document.querySelector("#metric-usage").textContent = "—";
        }} catch (error) {{ showError(error.message); }} finally {{ setBusy(button, false, '<i data-lucide="search"></i>Run discovery'); }}
      }});

      download.addEventListener("click", () => {{
        if (!state.csv) return; const blob = new Blob([state.csv], {{type: "text/csv"}}); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = state.filename; link.click(); URL.revokeObjectURL(link.href);
      }});
      if (window.lucide) lucide.createIcons();
    </script>
  </body>
</html>"""

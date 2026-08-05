from __future__ import annotations


def render_dashboard(version: str, maps_configured: bool, openai_configured: bool) -> str:
    return (
        DASHBOARD_HTML.replace("__VERSION__", version)
        .replace("__MAPS_STATUS__", "Connected" if maps_configured else "Missing")
        .replace("__AI_STATUS__", "Connected" if openai_configured else "Missing")
        .replace("__MAPS_CLASS__", "good" if maps_configured else "bad")
        .replace("__AI_CLASS__", "good" if openai_configured else "bad")
    )


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>8-Thon Intelligence</title>
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
  <style>
    :root {
      color-scheme: light;
      --canvas: #f6f7fb; --surface: #ffffff; --soft: #f3f1ff; --soft-blue: #eef4ff;
      --line: #e2e5ed; --line-strong: #ccd1dc; --text: #20242d; --muted: #697386;
      --purple: #6548d8; --purple-dark: #5034bc; --purple-soft: #ece8ff;
      --blue: #376fe8; --mint: #08a88a; --red: #d94b62; --amber: #bd7a13;
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body { margin: 0; background: var(--canvas); color: var(--text); font: 14px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
    button, input, textarea, select { font: inherit; letter-spacing: 0; }
    button { cursor: pointer; }
    .hidden { display: none !important; }
    .shell { min-height: 100vh; display: grid; grid-template-columns: 60px minmax(0, 1fr); }
    .nav { position: sticky; top: 0; height: 100vh; background: #fff; border-right: 1px solid var(--line); display: flex; flex-direction: column; align-items: center; padding: 14px 8px; z-index: 5; }
    .brand { width: 36px; height: 36px; border-radius: 8px; display: grid; place-items: center; background: var(--purple); color: #fff; font-weight: 850; margin-bottom: 24px; }
    .nav button { width: 40px; height: 40px; border: 0; border-radius: 7px; background: transparent; color: #8b93a4; display: grid; place-items: center; margin-bottom: 7px; }
    .nav button.active { color: var(--purple); background: var(--purple-soft); }
    .nav .bottom { margin-top: auto; }
    .app { min-width: 0; }
    .topbar { height: 58px; padding: 0 16px; border-bottom: 1px solid var(--line); background: #fff; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .toolbar, .status-row, .view-tabs, .table-tools { display: flex; align-items: center; gap: 8px; }
    .table-tools select { width: auto; min-width: 105px; height: 34px; padding: 6px 9px; }
    .button { min-height: 34px; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: #454d5d; padding: 7px 12px; display: inline-flex; align-items: center; justify-content: center; gap: 7px; }
    .button:hover { border-color: #b9b1e9; color: var(--purple); }
    .button.primary { border-color: var(--purple); background: var(--purple); color: #fff; font-weight: 700; }
    .button.primary:hover { background: var(--purple-dark); }
    .button:disabled { opacity: .5; cursor: not-allowed; }
    .icon-button { width: 34px; height: 34px; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: #697386; display: grid; place-items: center; }
    .connection { font-size: 12px; color: var(--muted); display: inline-flex; align-items: center; gap: 6px; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--red); }
    .connection.good .dot { background: var(--mint); }
    .workspace { display: grid; grid-template-columns: 352px minmax(0, 1fr); height: calc(100vh - 58px); min-height: 620px; }
    .filters { overflow-y: auto; background: #fafbfe; border-right: 1px solid var(--line); }
    .filter-head { position: sticky; top: 0; z-index: 2; background: #fff; border-bottom: 1px solid var(--line); padding: 10px 12px; }
    .filter-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
    .filter-tab { min-height: 38px; border: 1px solid var(--line); border-radius: 7px; background: #fff; color: #50596a; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 7px; }
    .filter-tab.active { border-color: #c7bcff; background: var(--purple-soft); color: var(--purple); }
    .filter-form { padding: 10px; }
    .section { border: 1px solid var(--line); background: #fff; margin-bottom: 8px; border-radius: 7px; overflow: hidden; }
    .section summary { min-height: 43px; padding: 0 12px; list-style: none; display: flex; align-items: center; gap: 9px; font-weight: 700; cursor: pointer; }
    .section summary::-webkit-details-marker { display: none; }
    .section summary::after { content: "+"; margin-left: auto; color: #8892a3; font-size: 18px; font-weight: 400; }
    .section[open] summary { background: var(--soft-blue); border-bottom: 1px solid #dce6f8; }
    .section[open] summary::after { content: "−"; }
    .section-body { padding: 12px; }
    label { display: block; color: #5c6576; font-size: 12px; font-weight: 650; margin: 0 0 6px; }
    input, textarea, select { width: 100%; border: 1px solid var(--line-strong); border-radius: 6px; background: #fff; color: var(--text); padding: 9px 10px; outline: none; }
    input:focus, textarea:focus, select:focus { border-color: var(--purple); box-shadow: 0 0 0 3px rgba(101,72,216,.11); }
    textarea { min-height: 72px; resize: vertical; }
    .field { margin-bottom: 11px; }
    .field:last-child { margin-bottom: 0; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
    .segmented { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid var(--line-strong); border-radius: 6px; overflow: hidden; }
    .segmented input { position: absolute; width: 1px; height: 1px; opacity: 0; }
    .segmented label { margin: 0; padding: 8px; text-align: center; font-size: 12px; cursor: pointer; border-right: 1px solid var(--line); }
    .segmented label:last-child { border: 0; }
    .segmented input:checked + label { background: var(--purple-soft); color: var(--purple); font-weight: 800; }
    .checks { display: grid; gap: 8px; }
    .check { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #4f5868; }
    .check input { width: 15px; height: 15px; accent-color: var(--purple); }
    .run-dock { position: sticky; bottom: 0; padding: 10px; background: rgba(250,251,254,.96); border-top: 1px solid var(--line); }
    .run-dock .button { width: 100%; min-height: 42px; }
    .results { min-width: 0; overflow: hidden; background: #fff; display: flex; flex-direction: column; }
    .results-head { min-height: 58px; border-bottom: 1px solid var(--line); padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .view-tab { min-height: 36px; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: #4f5868; padding: 7px 13px; display: inline-flex; align-items: center; gap: 7px; font-weight: 700; }
    .view-tab.active { background: var(--purple-soft); color: var(--purple); border-color: #c9bfff; }
    .count { min-width: 22px; height: 20px; padding: 0 6px; border-radius: 10px; background: #edf0f6; color: #606a7c; display: inline-grid; place-items: center; font-size: 11px; }
    .view-tab.active .count { background: #dcd4ff; color: var(--purple-dark); }
    .progress-panel { border-bottom: 1px solid var(--line); padding: 10px 15px; background: #fbfaff; }
    .progress-line { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; margin-bottom: 7px; }
    .progress-line strong { color: var(--purple-dark); }
    .progress-track { height: 6px; background: #e8e5f5; border-radius: 3px; overflow: hidden; }
    .progress-bar { width: 0; height: 100%; background: var(--purple); transition: width .25s ease; }
    .summarybar { min-height: 44px; border-bottom: 1px solid var(--line); padding: 8px 15px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .summary-copy { color: var(--muted); font-size: 12px; }
    .summary-copy strong { color: var(--text); }
    .search { position: relative; width: 230px; }
    .search svg { position: absolute; left: 9px; top: 9px; color: #98a1b1; }
    .search input { padding-left: 31px; height: 34px; }
    .table-shell { flex: 1; overflow: auto; }
    table { width: 100%; min-width: 980px; border-collapse: collapse; }
    th { position: sticky; top: 0; z-index: 1; height: 42px; padding: 8px 12px; background: #fafbfe; border-bottom: 1px solid var(--line); color: #737d8e; font-size: 11px; text-align: left; text-transform: uppercase; font-weight: 750; }
    td { padding: 13px 12px; border-bottom: 1px solid #eceef3; vertical-align: middle; }
    tr:hover td { background: #fcfbff; }
    .score { width: 42px; height: 42px; border: 3px solid #10af98; border-radius: 50%; display: grid; place-items: center; color: #078b78; font-weight: 850; font-size: 12px; }
    .company-name { color: #262b34; font-weight: 800; margin-bottom: 3px; }
    .domain, .subtle { color: #818a9a; font-size: 11px; }
    .tag-list { display: flex; gap: 5px; flex-wrap: wrap; max-width: 280px; }
    .tag { padding: 3px 6px; border-radius: 4px; background: #eef3ff; color: #4168b1; font-size: 10px; }
    .contact-name { font-weight: 750; }
    .email { color: var(--purple); font-size: 12px; overflow-wrap: anywhere; }
    .socials { display: flex; gap: 5px; margin-top: 5px; }
    .social-link { width: 25px; height: 25px; display: grid; place-items: center; border: 1px solid var(--line); border-radius: 5px; color: #697386; text-decoration: none; }
    .fit-actions { display: flex; gap: 5px; }
    .fit-actions button.active { background: var(--purple-soft); color: var(--purple); border-color: #c9bfff; }
    .empty { flex: 1; display: grid; place-items: center; padding: 32px; text-align: center; color: var(--muted); }
    .empty-icon { width: 54px; height: 54px; margin: 0 auto 14px; border-radius: 10px; background: var(--purple-soft); color: var(--purple); display: grid; place-items: center; }
    .empty h2 { font-size: 16px; color: var(--text); margin: 0 0 5px; }
    .notice { margin: 10px 15px 0; padding: 9px 11px; border-radius: 6px; background: #fff1f3; color: #a82e45; border: 1px solid #f4ccd4; }
    @media (max-width: 980px) { .workspace { grid-template-columns: 310px minmax(0, 1fr); } .status-row { display: none; } }
    @media (max-width: 760px) {
      .shell { grid-template-columns: 1fr; } .nav { display: none; } .topbar { height: auto; min-height: 58px; flex-wrap: wrap; padding: 10px; }
      .workspace { height: auto; display: block; } .filters { max-height: none; border-right: 0; border-bottom: 1px solid var(--line); }
      .filter-head { position: static; } .results { min-height: 620px; } .results-head, .summarybar { align-items: flex-start; flex-direction: column; }
      .search { width: 100%; } .table-tools { width: 100%; } .table-tools .button { flex: 1; }
    }
  </style>
</head>
<body>
<div class="shell">
  <aside class="nav" aria-label="Main navigation">
    <div class="brand">8T</div>
    <button class="active" title="Search"><i data-lucide="search"></i></button>
    <button title="Saved lists"><i data-lucide="folder-search"></i></button>
    <button title="Exports"><i data-lucide="list"></i></button>
    <div class="bottom"><button title="Settings"><i data-lucide="settings"></i></button></div>
  </aside>
  <main class="app">
    <header class="topbar">
      <div class="toolbar">
        <button class="button" id="load-search"><i data-lucide="folder-open"></i>Load</button>
        <button class="button" id="save-search"><i data-lucide="save"></i>Save</button>
        <button class="button" id="clear-search"><i data-lucide="rotate-ccw"></i>Clear all</button>
      </div>
      <div class="status-row">
        <span class="connection __MAPS_CLASS__"><span class="dot"></span>Google Maps __MAPS_STATUS__</span>
        <span class="connection __AI_CLASS__"><span class="dot"></span>OpenAI __AI_STATUS__</span>
        <span class="connection">v__VERSION__</span>
      </div>
    </header>
    <div class="workspace">
      <aside class="filters">
        <div class="filter-head">
          <div class="filter-tabs">
            <button class="filter-tab active" data-mode="lookalike"><i data-lucide="scan-search"></i>Lookalikes</button>
            <button class="filter-tab" data-mode="keyword"><i data-lucide="sliders-horizontal"></i>Keywords</button>
          </div>
        </div>
        <form id="lookalike-form" class="filter-form">
          <details class="section" open>
            <summary><i data-lucide="building-2"></i>Lookalike companies</summary>
            <div class="section-body">
              <div class="field"><label for="reference_urls">Ideal company websites</label><textarea id="reference_urls" required placeholder="example-roofing.com"></textarea></div>
              <div class="field"><label for="negative_urls">Exclude lookalikes</label><textarea id="negative_urls" placeholder="software-example.com"></textarea></div>
              <div class="segmented">
                <input id="precise" name="matching_mode" type="radio" value="precise" checked><label for="precise">Precise</label>
                <input id="broad" name="matching_mode" type="radio" value="broad"><label for="broad">Broad</label>
              </div>
            </div>
          </details>
          <details class="section" open>
            <summary><i data-lucide="tags"></i>Industry tags</summary>
            <div class="section-body">
              <div class="field"><label for="tags_any">Include any</label><input id="tags_any" placeholder="roofing, plumbing, landscaping"></div>
              <div class="field"><label for="tags_none">Exclude</label><input id="tags_none" value="software, saas" placeholder="software, saas"></div>
            </div>
          </details>
          <details class="section">
            <summary><i data-lucide="map-pin"></i>Company location</summary>
            <div class="section-body">
              <div class="field"><label for="lookalike_location">Search area</label><input id="lookalike_location" value="San Antonio, TX"></div>
              <div class="grid-2"><div><label for="lookalike_city">City</label><input id="lookalike_city" value="San Antonio"></div><div><label for="lookalike_state">State</label><input id="lookalike_state" value="TX"></div></div>
            </div>
          </details>
          <details class="section">
            <summary><i data-lucide="key-round"></i>Keywords</summary>
            <div class="section-body">
              <div class="field"><label for="keywords_any">Include any</label><input id="keywords_any"></div>
              <div class="field"><label for="keywords_all">Include all</label><input id="keywords_all"></div>
              <div class="field"><label for="keywords_none">Exclude</label><input id="keywords_none"></div>
            </div>
          </details>
          <details class="section">
            <summary><i data-lucide="cpu"></i>Website technologies</summary>
            <div class="section-body"><div class="field"><label for="technologies_any">Include any</label><input id="technologies_any" placeholder="wordpress, servicetitan"></div><div class="field"><label for="technologies_none">Exclude</label><input id="technologies_none"></div></div>
          </details>
          <details class="section" open>
            <summary><i data-lucide="users"></i>Decision makers</summary>
            <div class="section-body">
              <div class="field"><label for="decision_maker_roles">Titles</label><textarea id="decision_maker_roles">owner, founder, president, ceo, principal, general manager</textarea></div>
              <div class="checks"><label class="check"><input id="require_owner" type="checkbox">Named decision maker only</label><label class="check"><input id="require_contact_email" type="checkbox">Direct email only</label></div>
            </div>
          </details>
          <details class="section">
            <summary><i data-lucide="shopping-cart"></i>Company signals</summary>
            <div class="section-body"><div class="checks"><label class="check"><input id="require_hiring" type="checkbox">Actively hiring</label><label class="check"><input id="ecommerce_only" type="checkbox">E-commerce</label></div></div>
          </details>
          <details class="section" open>
            <summary><i data-lucide="gauge"></i>Search volume</summary>
            <div class="section-body">
              <div class="grid-2"><div><label for="lookalike_candidates">Candidate pool</label><select id="lookalike_candidates"><option>80</option><option selected>160</option><option>240</option><option>300</option></select></div><div><label for="lookalike_results">Result target</label><select id="lookalike_results"><option>25</option><option selected>50</option><option>75</option><option>100</option></select></div></div>
              <div class="grid-2" style="margin-top:10px"><div><label for="min_score">Minimum score</label><input id="min_score" type="number" min="0" max="100" value="45"></div><div><label for="lookalike_pages">Pages per site</label><select id="lookalike_pages"><option>4</option><option selected>6</option><option>8</option></select></div></div>
              <input id="freshness" type="hidden" value="12"><input id="lookalike_dedupe" type="hidden" value="email"><input id="lookalike_mx" type="hidden" value="false">
            </div>
          </details>
          <div class="run-dock"><button id="lookalike-run" class="button primary" type="submit"><i data-lucide="sparkles"></i>Find companies</button></div>
        </form>
        <form id="keyword-form" class="filter-form hidden">
          <details class="section" open><summary><i data-lucide="search"></i>Keyword discovery</summary><div class="section-body"><div class="field"><label for="query">Business type</label><input id="query" placeholder="roofing contractor"></div><div class="field"><label for="location">Location</label><input id="location" value="San Antonio, TX"></div><div class="field"><label for="urls">Additional websites</label><textarea id="urls"></textarea></div><div class="grid-2"><div><label for="city">City</label><input id="city" value="San Antonio"></div><div><label for="state">State</label><input id="state" value="TX"></div></div><input id="category" type="hidden"><input id="max_results" type="hidden" value="60"><input id="max_pages" type="hidden" value="6"><input id="verify_mx" type="hidden" value="false"></div></details>
          <div class="run-dock"><button id="keyword-run" class="button primary" type="submit"><i data-lucide="search"></i>Run discovery</button></div>
        </form>
      </aside>
      <section class="results">
        <div class="results-head">
          <div class="view-tabs"><button class="view-tab active" data-view="companies"><i data-lucide="building-2"></i>Companies <span id="company-count" class="count">0</span></button><button class="view-tab" data-view="contacts"><i data-lucide="users"></i>Contacts <span id="contact-count" class="count">0</span></button></div>
          <div class="table-tools"><select id="result-sort" aria-label="Sort results"><option value="score">Best fit</option><option value="name">Company name</option><option value="contact">Named contacts</option></select><button id="download" class="button" disabled><i data-lucide="download"></i>Export CSV</button></div>
        </div>
        <div id="progress-panel" class="progress-panel hidden"><div class="progress-line"><strong id="progress-stage">Starting</strong><span id="progress-message">Preparing the search</span><span id="progress-value">0%</span></div><div class="progress-track"><div id="progress-bar" class="progress-bar"></div></div></div>
        <div id="notice"></div>
        <div id="summarybar" class="summarybar hidden"><div class="summary-copy"><strong id="result-count">0 companies</strong> <span id="result-detail"></span></div><div class="search"><i data-lucide="search"></i><input id="result-search" placeholder="Filter results"></div></div>
        <div id="empty" class="empty"><div><div class="empty-icon"><i data-lucide="scan-search"></i></div><h2>Build a company audience</h2><p>Add ideal companies and filters, then run the search.</p></div></div>
        <div id="company-table" class="table-shell hidden"><table><thead><tr><th>Fit</th><th>Company</th><th>Industry tags</th><th>Location</th><th>Signals</th><th>Decision maker</th><th>Feedback</th></tr></thead><tbody id="company-rows"></tbody></table></div>
        <div id="contact-table" class="table-shell hidden"><table><thead><tr><th>Decision maker</th><th>Title</th><th>Company</th><th>Email</th><th>Phone</th><th>LinkedIn</th><th>Source</th></tr></thead><tbody id="contact-rows"></tbody></table></div>
      </section>
    </div>
  </main>
</div>
<script>
  const state = { view: "companies", mode: "lookalike", companies: [], contacts: [], queryId: "", downloadUrl: "", pollTimer: null };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const value = (id) => $(id).value;
  const bool = (id) => $(id).checked;

  $$(".filter-tab").forEach(button => button.addEventListener("click", () => {
    state.mode = button.dataset.mode; $$(".filter-tab").forEach(item => item.classList.toggle("active", item === button));
    $("#lookalike-form").classList.toggle("hidden", state.mode !== "lookalike"); $("#keyword-form").classList.toggle("hidden", state.mode !== "keyword");
  }));
  $$(".view-tab").forEach(button => button.addEventListener("click", () => { state.view = button.dataset.view; renderView(); }));
  $("#result-search").addEventListener("input", renderView);
  $("#result-sort").addEventListener("change", renderView);

  function lookalikePayload() { return {
    reference_urls: value("#reference_urls"), negative_urls: value("#negative_urls"), matching_mode: $('input[name="matching_mode"]:checked').value,
    location: value("#lookalike_location"), city: value("#lookalike_city"), state: value("#lookalike_state"), max_candidates: Number(value("#lookalike_candidates")),
    max_results: Number(value("#lookalike_results")), max_pages: Number(value("#lookalike_pages")), min_score: Number(value("#min_score")), updated_within_months: 12,
    dedupe: "email", verify_mx: false, industries_any: "", industries_none: "", tags_any: value("#tags_any"), tags_none: value("#tags_none"),
    keywords_any: value("#keywords_any"), keywords_all: value("#keywords_all"), keywords_none: value("#keywords_none"), technologies_any: value("#technologies_any"),
    technologies_none: value("#technologies_none"), technologies_all: "", require_hiring: bool("#require_hiring"), ecommerce_only: bool("#ecommerce_only"),
    require_owner: bool("#require_owner"), require_contact_email: bool("#require_contact_email"), decision_maker_roles: value("#decision_maker_roles")
  }; }
  function keywordPayload() { return { query: value("#query"), location: value("#location"), urls: value("#urls"), city: value("#city"), state: value("#state"), category: value("#category"), max_results: 60, max_pages: 6, dedupe: "email", verify_mx: false }; }

  $("#lookalike-form").addEventListener("submit", event => { event.preventDefault(); startJob("/api/jobs/lookalikes", lookalikePayload()); });
  $("#keyword-form").addEventListener("submit", event => { event.preventDefault(); startJob("/api/jobs/scrape", keywordPayload()); });

  async function startJob(endpoint, payload) {
    clearError(); setBusy(true); showProgress(2, "Queued", "Starting the search");
    try {
      const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not start search"); sessionStorage.setItem("8thon-active-job", data.job_id); pollJob(data.job_id);
    } catch (error) { showError(error.message); setBusy(false); }
  }
  async function pollJob(jobId) {
    try {
      const response = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" }); const job = await response.json(); if (!response.ok) throw new Error(job.detail || "Could not read search status");
      showProgress(job.progress, job.stage, job.message);
      if (job.status === "completed") { finishJob(job); return; }
      if (job.status === "failed") throw new Error(job.error || "Search failed");
      state.pollTimer = setTimeout(() => pollJob(jobId), 1200);
    } catch (error) { showError(error.message); setBusy(false); }
  }
  function finishJob(job) {
    sessionStorage.removeItem("8thon-active-job"); const result = job.result || {}; state.companies = result.matches || []; state.contacts = result.contacts || []; state.queryId = result.query_id || ""; state.downloadUrl = job.download_url || "";
    $("#company-count").textContent = state.companies.length || result.discovery_count || 0; $("#contact-count").textContent = state.contacts.length || result.direct_count || 0;
    $("#download").disabled = !state.downloadUrl; $("#summarybar").classList.remove("hidden"); $("#empty").classList.add("hidden");
    $("#result-detail").textContent = result.candidates_discovered ? `from ${result.candidates_discovered} discovered candidates` : `${result.direct_count || 0} direct emails`;
    setBusy(false); setTimeout(() => $("#progress-panel").classList.add("hidden"), 900); renderView();
  }
  function renderView() {
    $$(".view-tab").forEach(button => button.classList.toggle("active", button.dataset.view === state.view));
    const term = value("#result-search").trim().toLowerCase(); const companies = state.companies.filter(item => JSON.stringify(item).toLowerCase().includes(term)); const contacts = state.contacts.filter(item => JSON.stringify(item).toLowerCase().includes(term)); const sort = value("#result-sort");
    if (sort === "name") companies.sort((a, b) => String(a.business_name || a.domain).localeCompare(String(b.business_name || b.domain)));
    else if (sort === "contact") companies.sort((a, b) => Number(Boolean(b.owner_name)) - Number(Boolean(a.owner_name)) || b.score - a.score);
    else companies.sort((a, b) => b.score - a.score);
    contacts.sort((a, b) => Number(Boolean(b.owner_name)) - Number(Boolean(a.owner_name)) || String(a.business_name).localeCompare(String(b.business_name)));
    $("#company-table").classList.toggle("hidden", state.view !== "companies" || !state.companies.length); $("#contact-table").classList.toggle("hidden", state.view !== "contacts" || !state.contacts.length);
    $("#result-count").textContent = state.view === "companies" ? `${companies.length} companies` : `${contacts.length} contacts`; renderCompanies(companies); renderContacts(contacts);
    if (window.lucide) lucide.createIcons();
  }
  function renderCompanies(items) {
    const rows = $("#company-rows"); rows.textContent = ""; items.forEach(match => {
      const row = document.createElement("tr"); const tags = (match.industry_tags || []).slice(0, 4).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("");
      const links = socialLinks(match); row.innerHTML = `<td><div class="score">${Math.round(match.score)}</div></td><td><div class="company-name">${escapeHtml(match.business_name || match.domain)}</div><div class="domain">${escapeHtml(match.domain)}</div>${links}</td><td><div class="tag-list">${tags}</div></td><td>${escapeHtml(match.location || "—")}</td><td><div class="subtle">${match.careers_active ? "Hiring · " : ""}${match.ecommerce ? "E-commerce · " : ""}${escapeHtml((match.technologies || []).slice(0, 2).join(", ") || "—")}</div></td><td><div class="contact-name">${escapeHtml(match.owner_name || "Not confirmed")}</div><div class="email">${escapeHtml(match.verified_email || match.phone || "")}</div></td><td><div class="fit-actions"><button class="icon-button fit" title="Mark as fit"><i data-lucide="thumbs-up"></i></button><button class="icon-button not-fit" title="Mark as not a fit"><i data-lucide="thumbs-down"></i></button></div></td>`;
      row.querySelector(".fit").addEventListener("click", event => saveFeedback(match.domain, "fit", event.currentTarget)); row.querySelector(".not-fit").addEventListener("click", event => saveFeedback(match.domain, "not_fit", event.currentTarget)); rows.appendChild(row);
    });
  }
  function renderContacts(items) {
    const rows = $("#contact-rows"); rows.textContent = ""; items.forEach(contact => { const row = document.createElement("tr"); const linkedIn = contact.linkedin_profile_url || contact.decision_maker_search_url || contact.linkedin_url; row.innerHTML = `<td><div class="contact-name">${escapeHtml(contact.owner_name || "Decision maker search")}</div><div class="subtle">${contact.owner_confidence ? `${contact.owner_confidence}% confidence` : ""}</div></td><td>${escapeHtml(contact.owner_role || "Owner / leader")}</td><td><div class="company-name">${escapeHtml(contact.business_name)}</div><div class="domain">${escapeHtml(contact.domain)}</div></td><td class="email">${escapeHtml(contact.verified_email || "—")}</td><td>${escapeHtml(contact.phone || "—")}</td><td>${linkedIn ? `<a class="button" href="${escapeAttr(linkedIn)}" target="_blank" rel="noopener"><i data-lucide="linkedin"></i>Open</a>` : "—"}</td><td>${contact.source_url ? `<a href="${escapeAttr(contact.source_url)}" target="_blank" rel="noopener">Evidence</a>` : "—"}</td>`; rows.appendChild(row); });
  }
  function socialLinks(match) { const links = []; if (match.website) links.push(`<a class="social-link" href="${escapeAttr(match.website)}" target="_blank" rel="noopener" title="Website"><i data-lucide="link"></i></a>`); if (match.linkedin_url) links.push(`<a class="social-link" href="${escapeAttr(match.linkedin_url)}" target="_blank" rel="noopener" title="LinkedIn"><i data-lucide="linkedin"></i></a>`); return `<div class="socials">${links.join("")}</div>`; }
  async function saveFeedback(domain, label, button) { try { const response = await fetch("/api/lookalike-feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query_id: state.queryId, domain, label }) }); if (!response.ok) throw new Error("Could not save feedback"); button.closest(".fit-actions").querySelectorAll("button").forEach(item => item.classList.remove("active")); button.classList.add("active"); } catch (error) { showError(error.message); } }
  function showProgress(progress, stage, message) { $("#progress-panel").classList.remove("hidden"); $("#progress-bar").style.width = `${progress}%`; $("#progress-value").textContent = `${progress}%`; $("#progress-stage").textContent = stage; $("#progress-message").textContent = message; }
  function setBusy(busy) { $("#lookalike-run").disabled = busy; $("#keyword-run").disabled = busy; }
  function showError(message) { sessionStorage.removeItem("8thon-active-job"); $("#notice").innerHTML = `<div class="notice">${escapeHtml(message)}</div>`; $("#progress-panel").classList.add("hidden"); }
  function clearError() { $("#notice").textContent = ""; }
  function escapeHtml(value) { const node = document.createElement("span"); node.textContent = String(value || ""); return node.innerHTML; }
  function escapeAttr(value) { return escapeHtml(value).replace(/"/g, "&quot;"); }
  $("#download").addEventListener("click", () => { if (state.downloadUrl) window.location.href = state.downloadUrl; });
  $("#save-search").addEventListener("click", () => {
    const saved = {}; $$("#lookalike-form input[id], #lookalike-form textarea[id], #lookalike-form select[id]").forEach(field => { saved[field.id] = field.type === "checkbox" || field.type === "radio" ? field.checked : field.value; });
    localStorage.setItem("8thon-search", JSON.stringify(saved));
  });
  $("#load-search").addEventListener("click", () => { const saved = JSON.parse(localStorage.getItem("8thon-search") || "null"); if (!saved) return; Object.entries(saved).forEach(([key, item]) => { const field = document.getElementById(key); if (!field) return; if (field.type === "checkbox" || field.type === "radio") field.checked = Boolean(item); else field.value = item; }); });
  $("#clear-search").addEventListener("click", () => { $("#lookalike-form").reset(); $("#tags_none").value = "software, saas"; state.companies = []; state.contacts = []; $("#company-count").textContent = "0"; $("#contact-count").textContent = "0"; $("#summarybar").classList.add("hidden"); $("#company-table").classList.add("hidden"); $("#contact-table").classList.add("hidden"); $("#empty").classList.remove("hidden"); });
  const activeJob = sessionStorage.getItem("8thon-active-job"); if (activeJob) { setBusy(true); pollJob(activeJob); }
  if (window.lucide) lucide.createIcons();
</script>
</body>
</html>"""

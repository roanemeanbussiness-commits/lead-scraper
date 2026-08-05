from __future__ import annotations

import html


def render_dashboard(version: str, ocean_configured: bool) -> str:
    ocean_state = "Connected" if ocean_configured else "Missing token"
    ocean_class = "connected" if ocean_configured else "missing"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>8-Thon Intelligence | Ocean Lead Search</title>
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
  <style>
    :root {{ --blue:#4f7df3; --blue-strong:#3566e8; --blue-soft:#eaf2ff; --ink:#172033; --muted:#69748a; --line:#dfe4ed; --panel:#f8f9fc; --white:#fff; --green:#19a979; --red:#d84c5b; --amber:#ad7410; }}
    * {{ box-sizing:border-box; }}
    html,body {{ margin:0; min-height:100%; font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink); background:#f7f8fb; font-size:14px; letter-spacing:0; }}
    button,input,select,textarea {{ font:inherit; color:inherit; letter-spacing:0; }}
    button {{ cursor:pointer; }}
    .app {{ min-height:100vh; display:grid; grid-template-columns:56px 340px minmax(0,1fr); }}
    .rail {{ background:var(--white); border-right:1px solid var(--line); display:flex; flex-direction:column; align-items:center; gap:10px; padding:12px 8px; position:sticky; top:0; height:100vh; z-index:5; }}
    .brand {{ width:36px; height:36px; display:grid; place-items:center; background:var(--blue); color:#fff; font-weight:800; border-radius:8px; margin-bottom:12px; }}
    .rail-btn,.icon-btn {{ width:36px; height:36px; border:1px solid transparent; background:transparent; display:grid; place-items:center; border-radius:7px; color:#7a8499; }}
    .rail-btn.active,.rail-btn:hover {{ background:var(--blue-soft); color:var(--blue-strong); }}
    .rail-spacer {{ flex:1; }}
    svg {{ width:18px; height:18px; stroke-width:1.8; }}
    .filters {{ background:var(--white); border-right:1px solid var(--line); min-height:100vh; padding:12px; overflow:auto; }}
    .utility-row {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:7px; margin-bottom:12px; }}
    .quiet-btn,.primary-btn,.download-btn {{ min-height:36px; border:1px solid var(--line); border-radius:7px; background:#fff; display:inline-flex; align-items:center; justify-content:center; gap:7px; padding:7px 12px; white-space:nowrap; }}
    .quiet-btn:hover {{ border-color:#b9c5dc; background:#fafbfe; }}
    .primary-btn {{ width:100%; background:var(--blue); border-color:var(--blue); color:#fff; font-weight:700; min-height:42px; margin-top:12px; }}
    .primary-btn:hover {{ background:var(--blue-strong); }}
    .primary-btn:disabled {{ opacity:.58; cursor:wait; }}
    .mode-tabs,.result-tabs {{ display:grid; grid-template-columns:1fr 1fr; padding:3px; background:#f0f2f7; border-radius:7px; gap:3px; }}
    .mode-tabs {{ margin-bottom:12px; }}
    .mode-btn,.result-tab {{ min-height:36px; border:0; border-radius:5px; background:transparent; color:#59657a; display:flex; align-items:center; justify-content:center; gap:7px; font-weight:650; }}
    .mode-btn.active,.result-tab.active {{ background:#fff; color:var(--ink); box-shadow:0 1px 3px rgba(20,33,61,.12); }}
    .filter-search {{ position:relative; margin-bottom:10px; }}
    .filter-search svg {{ position:absolute; left:11px; top:10px; color:#7d879a; }}
    .filter-search input {{ padding-left:36px; }}
    details {{ border:1px solid var(--line); border-radius:7px; margin-bottom:8px; background:#fff; overflow:hidden; }}
    summary {{ list-style:none; min-height:42px; display:flex; align-items:center; gap:9px; padding:9px 11px; font-weight:650; cursor:pointer; user-select:none; }}
    summary::-webkit-details-marker {{ display:none; }}
    summary::after {{ content:"+"; margin-left:auto; color:#8090a8; font-size:18px; font-weight:400; }}
    details[open] summary {{ background:#f4f7fc; border-bottom:1px solid var(--line); }}
    details[open] summary::after {{ content:"-"; }}
    .details-body {{ padding:11px; }}
    label {{ display:block; color:#5f6b80; font-size:12px; font-weight:650; margin:0 0 6px; }}
    input,select,textarea {{ width:100%; border:1px solid #ccd4e1; background:#fff; border-radius:6px; min-height:38px; padding:8px 10px; outline:none; }}
    textarea {{ resize:vertical; min-height:72px; }}
    input:focus,select:focus,textarea:focus {{ border-color:var(--blue); box-shadow:0 0 0 3px rgba(79,125,243,.12); }}
    .field {{ margin-bottom:10px; }}
    .field:last-child {{ margin-bottom:0; }}
    .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:9px; }}
    .check-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:7px 10px; }}
    .check {{ display:flex; gap:7px; align-items:center; font-size:12px; color:#39455a; }}
    .check input {{ width:16px; min-height:16px; margin:0; accent-color:var(--blue); }}
    .switch-row {{ display:flex; justify-content:space-between; align-items:center; gap:12px; }}
    .switch {{ position:relative; width:36px; height:20px; flex:0 0 auto; }}
    .switch input {{ opacity:0; position:absolute; }}
    .switch span {{ position:absolute; inset:0; border-radius:10px; background:#c9cfda; transition:.2s; }}
    .switch span::after {{ content:""; position:absolute; width:16px; height:16px; left:2px; top:2px; border-radius:50%; background:#fff; transition:.2s; box-shadow:0 1px 2px rgba(0,0,0,.2); }}
    .switch input:checked + span {{ background:var(--blue); }}
    .switch input:checked + span::after {{ transform:translateX(16px); }}
    .cost {{ margin-top:10px; background:#f4f7fc; border:1px solid var(--line); border-radius:7px; padding:10px; display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
    .cost strong {{ display:block; font-size:15px; }}
    .cost span {{ color:var(--muted); font-size:11px; }}
    .workspace {{ min-width:0; min-height:100vh; background:#fff; }}
    .topbar {{ height:62px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; padding:0 18px; gap:14px; position:sticky; top:0; background:rgba(255,255,255,.96); z-index:4; }}
    .title {{ display:flex; align-items:center; gap:10px; font-weight:750; font-size:15px; }}
    .provider {{ display:flex; align-items:center; gap:8px; color:#58647a; font-size:12px; }}
    .dot {{ width:8px; height:8px; border-radius:50%; background:var(--green); }}
    .dot.missing {{ background:var(--red); }}
    .credits {{ border-left:1px solid var(--line); padding-left:12px; }}
    .top-actions {{ display:flex; align-items:center; gap:8px; }}
    .download-btn {{ color:#fff; border-color:var(--blue); background:var(--blue); }}
    .download-btn:disabled {{ background:#b8c2d6; border-color:#b8c2d6; cursor:not-allowed; }}
    .content-head {{ min-height:66px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; gap:14px; padding:12px 18px; }}
    .result-tabs {{ width:330px; }}
    .count {{ min-width:24px; height:20px; display:inline-grid; place-items:center; border-radius:10px; background:#e4ebfb; color:#315dc9; font-size:11px; padding:0 6px; }}
    .search-results {{ width:min(280px,36vw); position:relative; }}
    .search-results svg {{ position:absolute; top:10px; left:10px; color:#8792a5; }}
    .search-results input {{ padding-left:35px; }}
    .summary {{ min-height:47px; display:flex; align-items:center; gap:14px; padding:8px 18px; border-bottom:1px solid var(--line); font-size:12px; }}
    .summary strong {{ font-size:13px; }}
    .pill {{ border-radius:11px; padding:3px 8px; background:#eef3fc; color:#49617f; }}
    .pill.good {{ background:#e5f7ef; color:#157959; }}
    .pill.warn {{ background:#fff3d7; color:#8b5d08; }}
    .progress {{ margin:12px 18px; border:1px solid #cad7f0; background:#f5f8ff; padding:12px; border-radius:7px; }}
    .progress-head {{ display:flex; justify-content:space-between; font-weight:700; margin-bottom:8px; }}
    .progress-track {{ height:7px; background:#dfe7f6; border-radius:4px; overflow:hidden; }}
    .progress-bar {{ height:100%; width:0; background:var(--blue); transition:width .25s; }}
    .progress-message {{ color:var(--muted); font-size:12px; margin-top:7px; }}
    .notice {{ margin:12px 18px; padding:11px 12px; border-radius:7px; background:#fff0f1; border:1px solid #f1c2c8; color:#a62c3b; }}
    .table-wrap {{ overflow:auto; width:100%; }}
    table {{ width:100%; border-collapse:collapse; table-layout:fixed; min-width:980px; }}
    th {{ height:42px; text-align:left; padding:9px 12px; font-size:11px; text-transform:uppercase; color:#718096; background:#fafbfd; border-bottom:1px solid var(--line); }}
    td {{ padding:13px 12px; border-bottom:1px solid #e7eaf0; vertical-align:middle; }}
    tbody tr:hover {{ background:#fbfcff; }}
    .company-name,.person-name {{ font-weight:720; color:#162034; line-height:1.35; }}
    .domain,.subtle {{ color:#758198; font-size:12px; margin-top:3px; overflow:hidden; text-overflow:ellipsis; }}
    .email {{ color:#3e66d5; font-size:12px; overflow-wrap:anywhere; }}
    .tag-list {{ display:flex; flex-wrap:wrap; gap:4px; }}
    .tag {{ background:#edf2ff; color:#3e61bf; border-radius:4px; padding:3px 6px; font-size:10px; max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .score {{ width:38px; height:38px; border:2px solid #31af91; border-radius:50%; display:grid; place-items:center; font-weight:750; color:#16816b; }}
    .score.na {{ border-color:#cfd6e2; color:#8994a7; }}
    .socials {{ display:flex; gap:4px; margin-top:5px; }}
    .social-link {{ width:22px; height:22px; display:grid; place-items:center; color:#718098; }}
    .social-link svg {{ width:15px; height:15px; }}
    .status {{ display:inline-flex; align-items:center; gap:5px; font-size:11px; text-transform:capitalize; }}
    .status::before {{ content:""; width:6px; height:6px; border-radius:50%; background:#a7afbd; }}
    .status.verified::before {{ background:var(--green); }}
    .status.guessed::before,.status.catchAll::before {{ background:#e1a32e; }}
    .empty {{ min-height:calc(100vh - 128px); display:grid; place-items:center; padding:32px; text-align:center; }}
    .empty-inner {{ max-width:440px; }}
    .empty-icon {{ width:58px; height:58px; display:grid; place-items:center; margin:0 auto 14px; color:var(--blue); background:var(--blue-soft); border-radius:8px; }}
    .empty-icon svg {{ width:28px; height:28px; }}
    .empty h2 {{ margin:0 0 8px; font-size:20px; }}
    .empty p {{ margin:0; color:var(--muted); line-height:1.5; }}
    .hidden {{ display:none !important; }}
    @media (max-width:1050px) {{ .app {{ grid-template-columns:52px 300px minmax(0,1fr); }} .topbar {{ padding:0 12px; }} .provider .provider-label {{ display:none; }} }}
    @media (max-width:760px) {{ .app {{ display:block; }} .rail {{ display:none; }} .filters {{ min-height:auto; border-right:0; border-bottom:1px solid var(--line); padding:10px; }} .workspace {{ min-height:70vh; }} .topbar {{ position:static; height:auto; min-height:58px; flex-wrap:wrap; }} .content-head {{ align-items:stretch; flex-direction:column; }} .result-tabs,.search-results {{ width:100%; }} .summary {{ flex-wrap:wrap; }} .utility-row {{ grid-template-columns:repeat(3,1fr); }} .details-body {{ padding:10px; }} }}
  </style>
</head>
<body>
<div class="app">
  <nav class="rail" aria-label="Primary navigation">
    <div class="brand">8T</div>
    <button class="rail-btn active" title="Search"><i data-lucide="search"></i></button>
    <button class="rail-btn" title="Saved searches"><i data-lucide="folder-search-2"></i></button>
    <button class="rail-btn" title="Lead exports"><i data-lucide="list"></i></button>
    <div class="rail-spacer"></div>
    <button class="rail-btn" title="Settings"><i data-lucide="settings"></i></button>
  </nav>

  <aside class="filters">
    <div class="utility-row">
      <button class="quiet-btn" id="load-search"><i data-lucide="folder-open"></i>Load</button>
      <button class="quiet-btn" id="save-search"><i data-lucide="save"></i>Save</button>
      <button class="quiet-btn" id="clear-search"><i data-lucide="rotate-ccw"></i>Clear</button>
    </div>
    <div class="mode-tabs">
      <button class="mode-btn active" type="button" data-mode="lookalike"><i data-lucide="scan-search"></i>Lookalikes</button>
      <button class="mode-btn" type="button" data-mode="filters"><i data-lucide="sliders-horizontal"></i>Filters</button>
    </div>
    <div class="filter-search"><i data-lucide="search"></i><input id="filter-search" placeholder="Search filters"></div>

    <form id="ocean-form">
      <details open data-filter="lookalike company domains reference">
        <summary><i data-lucide="building-2"></i>Company lookalikes</summary>
        <div class="details-body">
          <div class="field" id="reference-field"><label for="reference_domains">Reference domains</label><textarea id="reference_domains" placeholder="example.com&#10;anothercustomer.com"></textarea></div>
          <div class="field"><label for="negative_domains">Exclude domains</label><textarea id="negative_domains" placeholder="competitor.com"></textarea></div>
        </div>
      </details>

      <details open data-filter="target count companies emails credits">
        <summary><i data-lucide="gauge"></i>Search volume</summary>
        <div class="details-body">
          <div class="grid-2">
            <div><label for="target_type">Target</label><select id="target_type"><option value="companies">Companies</option><option value="emails">Verified emails</option></select></div>
            <div><label for="target_count">Target count</label><input id="target_count" type="number" min="1" max="1000" value="100"></div>
          </div>
          <div class="cost"><div><strong id="standard-cost">40</strong><span>max standard credits</span></div><div><strong id="email-cost">100</strong><span>max email credits</span></div></div>
        </div>
      </details>

      <details open data-filter="headquarter location country state city">
        <summary><i data-lucide="map-pin"></i>Headquarter location</summary>
        <div class="details-body">
          <div class="field"><label for="city">City</label><input id="city" value="San Antonio"></div>
          <div class="grid-2"><div><label for="state">State</label><input id="state" value="TX" maxlength="3"></div><div><label for="country">Country</label><input id="country" value="us" maxlength="2"></div></div>
        </div>
      </details>

      <details data-filter="industry keywords tags exclude">
        <summary><i data-lucide="tags"></i>Industries and keywords</summary>
        <div class="details-body">
          <div class="field"><label for="industries_any">Industries</label><input id="industries_any" placeholder="Construction, Consumer Services"></div>
          <div class="field"><label for="industries_none">Exclude industries</label><input id="industries_none" placeholder="Software, SaaS"></div>
          <div class="field"><label for="keywords_any">Keywords: any</label><textarea id="keywords_any" placeholder="pool construction, pool builder"></textarea></div>
          <div class="field"><label for="keywords_all">Keywords: all</label><input id="keywords_all"></div>
          <div class="field"><label for="keywords_none">Keywords: exclude</label><input id="keywords_none" value="software, saas"></div>
        </div>
      </details>

      <details data-filter="employees size revenue year founded ecommerce">
        <summary><i data-lucide="users"></i>Company profile</summary>
        <div class="details-body">
          <div class="field"><label for="company_sizes">Employee sizes</label><input id="company_sizes" placeholder="2-10, 11-50, 51-200"></div>
          <div class="field"><label for="revenues">Revenue ranges</label><input id="revenues" placeholder="1-10M, 10-50M"></div>
          <div class="grid-2"><div><label for="year_from">Founded after</label><input id="year_from" type="number" min="0" max="2100"></div><div><label for="year_to">Founded before</label><input id="year_to" type="number" min="0" max="2100"></div></div>
          <div class="field" style="margin-top:10px"><label for="ecommerce">E-commerce</label><select id="ecommerce"><option value="any">Any</option><option value="include">Only e-commerce</option><option value="exclude">Exclude e-commerce</option></select></div>
        </div>
      </details>

      <details data-filter="technologies apps website stack">
        <summary><i data-lucide="cpu"></i>Technologies</summary>
        <div class="details-body"><label for="technologies_any">Uses any technology</label><textarea id="technologies_any" placeholder="HubSpot, Shopify, WordPress"></textarea></div>
      </details>

      <details open data-filter="people contacts owner decision maker seniority department title email">
        <summary><i data-lucide="contact-round"></i>Decision makers</summary>
        <div class="details-body">
          <div class="switch-row field"><div><label>Find contacts</label><span class="subtle">Ocean people search</span></div><label class="switch"><input id="find_contacts" type="checkbox" checked><span></span></label></div>
          <div class="field"><label for="seniorities">Seniorities</label><input id="seniorities" value="Owner, Founder, C-Level, Partner, VP, Head, Director"></div>
          <div class="field"><label for="departments">Departments</label><input id="departments" value="Founder/Owner, Management, Operations"></div>
          <div class="field"><label for="job_titles">Job title keywords</label><textarea id="job_titles">owner, founder, president, chief executive officer, principal, general manager</textarea></div>
          <div class="grid-2"><div><label for="people_per_company">People / company</label><input id="people_per_company" type="number" min="1" max="10" value="1"></div><div><label for="dedupe_months">Dedupe months</label><input id="dedupe_months" type="number" min="1" max="120" value="12"></div></div>
          <div class="switch-row" style="margin-top:10px"><div><label>Reveal emails</label><span class="subtle">Uses email credits</span></div><label class="switch"><input id="reveal_emails" type="checkbox" checked><span></span></label></div>
        </div>
      </details>
      <button class="primary-btn" id="run-search" type="submit"><i data-lucide="search"></i>Run Ocean search</button>
    </form>
  </aside>

  <main class="workspace">
    <header class="topbar">
      <div class="title"><i data-lucide="waves"></i>Ocean lead search</div>
      <div class="top-actions">
        <div class="provider"><span class="dot {ocean_class}"></span><span class="provider-label">Ocean.io {html.escape(ocean_state)}</span><span class="credits" id="credit-balance">Credits --</span><span>v{html.escape(version)}</span></div>
        <button class="download-btn" id="download" disabled><i data-lucide="download"></i>Export CSV</button>
      </div>
    </header>
    <div class="content-head">
      <div class="result-tabs">
        <button class="result-tab active" data-view="companies"><i data-lucide="building-2"></i>Companies <span class="count" id="company-count">0</span></button>
        <button class="result-tab" data-view="people"><i data-lucide="users"></i>People <span class="count" id="people-count">0</span></button>
      </div>
      <div class="search-results"><i data-lucide="search"></i><input id="result-search" placeholder="Filter results"></div>
    </div>
    <div id="notice"></div>
    <section class="progress hidden" id="progress-panel">
      <div class="progress-head"><span id="progress-stage">Starting</span><span id="progress-value">0%</span></div>
      <div class="progress-track"><div class="progress-bar" id="progress-bar"></div></div>
      <div class="progress-message" id="progress-message"></div>
    </section>
    <div class="summary hidden" id="summary">
      <strong id="result-count">0 companies</strong><span class="pill" id="email-summary">0 emails</span><span class="pill" id="target-summary">Target 0/0</span><span class="pill" id="usage-summary">0 credits</span>
    </div>
    <section class="empty" id="empty">
      <div class="empty-inner"><div class="empty-icon"><i data-lucide="scan-search"></i></div><h2>Build an Ocean audience</h2><p>Select company and decision-maker filters, then run a search.</p></div>
    </section>
    <section class="table-wrap hidden" id="companies-view">
      <table><colgroup><col style="width:72px"><col style="width:260px"><col style="width:170px"><col style="width:155px"><col style="width:100px"><col style="width:110px"><col style="width:220px"></colgroup>
        <thead><tr><th>Match</th><th>Company</th><th>Industry</th><th>Location</th><th>Size</th><th>People</th><th>Decision maker</th></tr></thead><tbody id="company-rows"></tbody>
      </table>
    </section>
    <section class="table-wrap hidden" id="people-view">
      <table><colgroup><col style="width:220px"><col style="width:190px"><col style="width:220px"><col style="width:230px"><col style="width:120px"><col style="width:120px"></colgroup>
        <thead><tr><th>Person</th><th>Role</th><th>Company</th><th>Email</th><th>Status</th><th>LinkedIn</th></tr></thead><tbody id="people-rows"></tbody>
      </table>
    </section>
  </main>
</div>
<script>
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const state = {{ mode:"lookalike", view:"companies", companies:[], people:[], downloadUrl:"", activeJob:"" }};
  const textValue = selector => $(selector).value.trim();
  const numericValue = selector => Number($(selector).value || 0);
  const boolValue = selector => $(selector).checked;

  function payload() {{
    return {{
      mode:state.mode, reference_domains:textValue("#reference_domains"), negative_domains:textValue("#negative_domains"),
      keywords_any:textValue("#keywords_any"), keywords_all:textValue("#keywords_all"), keywords_none:textValue("#keywords_none"),
      industries_any:textValue("#industries_any"), industries_none:textValue("#industries_none"), technologies_any:textValue("#technologies_any"),
      company_sizes:textValue("#company_sizes"), revenues:textValue("#revenues"), country:textValue("#country"), city:textValue("#city"), state:textValue("#state"), ecommerce:textValue("#ecommerce"),
      year_founded_from:numericValue("#year_from") || null, year_founded_to:numericValue("#year_to") || null,
      target_type:textValue("#target_type"), target_count:numericValue("#target_count"), find_contacts:boolValue("#find_contacts"), reveal_emails:boolValue("#reveal_emails"),
      people_per_company:numericValue("#people_per_company"), seniorities:textValue("#seniorities"), departments:textValue("#departments"), job_titles:textValue("#job_titles"), dedupe_months:numericValue("#dedupe_months")
    }};
  }}

  $$(".mode-btn").forEach(button => button.addEventListener("click", () => {{ state.mode=button.dataset.mode; $$(".mode-btn").forEach(item=>item.classList.toggle("active",item===button)); $("#reference-field").classList.toggle("hidden",state.mode!=="lookalike"); }}));
  $$(".result-tab").forEach(button => button.addEventListener("click", () => {{ state.view=button.dataset.view; render(); }}));
  $("#result-search").addEventListener("input",render);
  $("#filter-search").addEventListener("input",event => {{ const term=event.target.value.toLowerCase(); $$("details[data-filter]").forEach(item=>item.classList.toggle("hidden",term && !item.dataset.filter.includes(term))); }});
  ["#target_type","#target_count","#find_contacts","#reveal_emails","#people_per_company"].forEach(selector=>$(selector).addEventListener("change",updateCost));
  $("#target_count").addEventListener("input",updateCost);

  function updateCost() {{ const target=numericValue("#target_count"); const emails=textValue("#target_type")==="emails"; const companies=emails?Math.ceil(target/.65):target; const contacts=boolValue("#find_contacts")?companies*numericValue("#people_per_company"):0; $("#standard-cost").textContent=((companies+contacts)*.2).toFixed(1); $("#email-cost").textContent=boolValue("#reveal_emails")?contacts:0; }}

  $("#ocean-form").addEventListener("submit",async event => {{ event.preventDefault(); clearNotice(); setBusy(true); showProgress(2,"Starting","Submitting Ocean.io search"); try {{ const response=await fetch("/api/jobs/ocean",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(payload())}}); const body=await response.json(); if(!response.ok) throw new Error(body.detail||"Could not start search"); state.activeJob=body.job_id; sessionStorage.setItem("8thon-ocean-job",body.job_id); pollJob(body.job_id); }} catch(error) {{ showError(error.message); setBusy(false); }} }});

  async function pollJob(jobId) {{ try {{ const response=await fetch(`/api/jobs/${{jobId}}`); const job=await response.json(); if(!response.ok) throw new Error(job.detail||"Search status unavailable"); showProgress(job.progress,job.stage,job.message); if(job.status==="completed") {{ finish(job); return; }} if(job.status==="failed") throw new Error(job.error||"Ocean search failed"); setTimeout(()=>pollJob(jobId),1000); }} catch(error) {{ showError(error.message); setBusy(false); }} }}

  function finish(job) {{ const result=job.result||{{}}; state.companies=result.matches||[]; state.people=result.contacts||[]; state.downloadUrl=job.download_url||""; sessionStorage.removeItem("8thon-ocean-job"); $("#download").disabled=!state.downloadUrl; $("#company-count").textContent=state.companies.length; $("#people-count").textContent=state.people.length; $("#email-summary").textContent=`${{result.direct_count||0}} emails`; $("#target-summary").textContent=`Target ${{result.target_achieved||0}}/${{result.target_count||0}}`; $("#target-summary").className=`pill ${{result.target_met?"good":"warn"}}`; $("#usage-summary").textContent=`${{result.estimated_standard_credits||0}} standard + ${{result.estimated_email_credits||0}} email credits`; $("#summary").classList.remove("hidden"); setBusy(false); showProgress(100,"Complete",result.reveal_complete===false?"Results ready; some email checks timed out":"Results and CSV are ready"); setTimeout(()=>$("#progress-panel").classList.add("hidden"),1200); render(); loadCredits(); }}

  function render() {{ const term=textValue("#result-search").toLowerCase(); const companies=state.companies.filter(item=>JSON.stringify(item).toLowerCase().includes(term)); const people=state.people.filter(item=>JSON.stringify(item).toLowerCase().includes(term)); $$(".result-tab").forEach(button=>button.classList.toggle("active",button.dataset.view===state.view)); $("#empty").classList.toggle("hidden",state.companies.length>0||state.people.length>0); $("#companies-view").classList.toggle("hidden",state.view!=="companies"||!state.companies.length); $("#people-view").classList.toggle("hidden",state.view!=="people"||!state.people.length); $("#result-count").textContent=state.view==="companies"?`${{companies.length}} companies`:`${{people.length}} people`; renderCompanies(companies); renderPeople(people); if(window.lucide)lucide.createIcons(); }}

  function renderCompanies(items) {{ const body=$("#company-rows"); body.textContent=""; items.forEach(item=>{{ const row=document.createElement("tr"); const tags=(item.industry_tags||[]).slice(0,3).map(tag=>`<span class="tag">${{escapeHtml(tag)}}</span>`).join(""); const score=Number(item.score||0); row.innerHTML=`<td><div class="score ${{score?"":"na"}}">${{score?Math.round(score):"--"}}</div></td><td><div class="company-name">${{escapeHtml(item.business_name||item.domain)}}</div><div class="domain">${{escapeHtml(item.domain)}}</div><div class="socials">${{item.website?`<a class="social-link" href="${{escapeAttr(item.website)}}" target="_blank" title="Website"><i data-lucide="link"></i></a>`:""}}${{item.linkedin_url?`<a class="social-link" href="${{escapeAttr(item.linkedin_url)}}" target="_blank" title="LinkedIn"><i data-lucide="linkedin"></i></a>`:""}}</div></td><td><div class="tag-list">${{tags||"--"}}</div></td><td>${{escapeHtml(item.location||"--")}}</td><td>${{escapeHtml(item.company_size||"--")}}</td><td>${{escapeHtml(item.people_count||"--")}}</td><td><div class="person-name">${{escapeHtml(item.owner_name||"Not found")}}</div><div class="subtle">${{escapeHtml(item.owner_role||"")}}</div><div class="email">${{escapeHtml(item.verified_email||"")}}</div></td>`; body.appendChild(row); }}); }}

  function renderPeople(items) {{ const body=$("#people-rows"); body.textContent=""; items.forEach(item=>{{ const row=document.createElement("tr"); row.innerHTML=`<td><div class="person-name">${{escapeHtml(item.owner_name||"Unknown")}}</div><div class="subtle">${{escapeHtml((item.seniorities||[]).join(", "))}}</div></td><td>${{escapeHtml(item.owner_role||"--")}}</td><td><div class="company-name">${{escapeHtml(item.business_name||item.domain)}}</div><div class="domain">${{escapeHtml(item.domain)}}</div></td><td class="email">${{escapeHtml(item.verified_email||"--")}}</td><td><span class="status ${{escapeAttr(item.email_status||"")}}">${{escapeHtml(item.email_status||"not revealed")}}</span></td><td>${{item.linkedin_profile_url?`<a class="quiet-btn" href="${{escapeAttr(item.linkedin_profile_url)}}" target="_blank"><i data-lucide="linkedin"></i>Open</a>`:"--"}}</td>`; body.appendChild(row); }}); }}

  async function loadCredits() {{ try {{ const response=await fetch("/api/ocean/credits"); if(!response.ok)return; const data=await response.json(); const standard=Number(data.credits?.oneTime||0)+Number(data.credits?.recurrent||0); const emails=Number(data.emailCredits?.oneTime||0)+Number(data.emailCredits?.recurrent||0); $("#credit-balance").textContent=`${{standard}} standard / ${{emails}} email`; }} catch(_error) {{}} }}
  function showProgress(value,stage,message) {{ $("#progress-panel").classList.remove("hidden"); $("#progress-bar").style.width=`${{value}}%`; $("#progress-value").textContent=`${{value}}%`; $("#progress-stage").textContent=stage; $("#progress-message").textContent=message; }}
  function setBusy(busy) {{ $("#run-search").disabled=busy; }}
  function showError(message) {{ sessionStorage.removeItem("8thon-ocean-job"); $("#notice").innerHTML=`<div class="notice">${{escapeHtml(message)}}</div>`; $("#progress-panel").classList.add("hidden"); }}
  function clearNotice() {{ $("#notice").textContent=""; }}
  function escapeHtml(value) {{ const node=document.createElement("span"); node.textContent=String(value??""); return node.innerHTML; }}
  function escapeAttr(value) {{ return escapeHtml(value).replace(/"/g,"&quot;"); }}
  $("#download").addEventListener("click",()=>{{ if(state.downloadUrl)location.href=state.downloadUrl; }});
  $("#save-search").addEventListener("click",()=>{{ const saved={{mode:state.mode}}; $$("#ocean-form input[id],#ocean-form textarea[id],#ocean-form select[id]").forEach(field=>saved[field.id]=field.type==="checkbox"?field.checked:field.value); localStorage.setItem("8thon-ocean-search",JSON.stringify(saved)); }});
  $("#load-search").addEventListener("click",()=>{{ const saved=JSON.parse(localStorage.getItem("8thon-ocean-search")||"null"); if(!saved)return; if(saved.mode)$( `.mode-btn[data-mode="${{saved.mode}}"]` ).click(); Object.entries(saved).forEach(([id,value])=>{{ const field=document.getElementById(id); if(!field)return; if(field.type==="checkbox")field.checked=Boolean(value); else field.value=value; }}); updateCost(); }});
  $("#clear-search").addEventListener("click",()=>{{ $("#ocean-form").reset(); state.companies=[];state.people=[];state.downloadUrl="";$("#download").disabled=true;$("#summary").classList.add("hidden");render();updateCost(); }});
  const activeJob=sessionStorage.getItem("8thon-ocean-job"); if(activeJob){{setBusy(true);pollJob(activeJob);}} updateCost();loadCredits();if(window.lucide)lucide.createIcons();
</script>
</body>
</html>"""

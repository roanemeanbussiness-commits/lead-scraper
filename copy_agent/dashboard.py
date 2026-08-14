from __future__ import annotations


def render_dashboard(version: str, openai_ok: bool) -> str:
    status_text = "Connected" if openai_ok else "Add OpenAI_api secret"
    status_class = "ok" if openai_ok else "bad"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>8-Thon Copy Studio</title>
<script src="https://unpkg.com/marked@12.0.2/marked.min.js"></script>
<style>
  :root {{ --bg:#0e1116; --panel:#161b23; --panel2:#1d242f; --line:#2a3342; --ink:#e8ecf3; --muted:#8b96a8; --accent:#5b8cff; --accent2:#7aa2ff; --good:#2fbf8f; --bad:#e06c75; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; height:100%; background:var(--bg); color:var(--ink); font:14px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .app {{ display:grid; grid-template-columns:280px 1fr; height:100vh; }}
  .side {{ background:var(--panel); border-right:1px solid var(--line); display:flex; flex-direction:column; min-width:0; }}
  .brand {{ display:flex; align-items:center; gap:10px; padding:16px 14px; border-bottom:1px solid var(--line); }}
  .logo {{ width:34px; height:34px; border-radius:8px; background:linear-gradient(135deg,var(--accent),#9b6bff); display:grid; place-items:center; font-weight:800; }}
  .brand b {{ font-size:15px; }} .brand span {{ display:block; color:var(--muted); font-size:11px; }}
  .newchat {{ margin:12px 14px 6px; padding:10px; border-radius:8px; border:1px solid var(--line); background:var(--panel2); color:var(--ink); cursor:pointer; font-weight:650; }}
  .newchat:hover {{ border-color:var(--accent); }}
  .convos {{ flex:1; overflow:auto; padding:6px 8px; }}
  .convo {{ display:flex; align-items:center; gap:6px; padding:9px 10px; border-radius:7px; cursor:pointer; color:var(--muted); font-size:13px; }}
  .convo.active,.convo:hover {{ background:var(--panel2); color:var(--ink); }}
  .convo .t {{ flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .convo .del {{ opacity:0; border:0; background:none; color:var(--muted); cursor:pointer; font-size:14px; }}
  .convo:hover .del {{ opacity:1; }}
  .teach {{ border-top:1px solid var(--line); padding:12px 14px; }}
  .teach h4 {{ margin:0 0 8px; font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }}
  .teach input {{ width:100%; padding:9px 10px; border-radius:7px; border:1px solid var(--line); background:var(--panel2); color:var(--ink); }}
  .teach button {{ margin-top:8px; width:100%; padding:9px; border-radius:7px; border:0; background:var(--accent); color:#fff; font-weight:650; cursor:pointer; }}
  .teach button:disabled {{ opacity:.55; cursor:wait; }}
  .teach .memlink {{ margin-top:8px; text-align:center; }}
  .teach .memlink a {{ color:var(--muted); font-size:12px; cursor:pointer; text-decoration:underline; }}
  .status {{ padding:10px 14px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; display:flex; justify-content:space-between; }}
  .dot {{ color:var(--good); }} .dot.bad {{ color:var(--bad); }}
  .main {{ display:flex; flex-direction:column; min-width:0; }}
  .chat {{ flex:1; overflow-y:auto; padding:26px 0 12px; }}
  .inner {{ max-width:860px; margin:0 auto; padding:0 20px; }}
  .msg {{ margin-bottom:18px; display:flex; gap:12px; }}
  .avatar {{ flex:0 0 30px; width:30px; height:30px; border-radius:7px; display:grid; place-items:center; font-size:12px; font-weight:800; }}
  .msg.user .avatar {{ background:var(--panel2); color:var(--muted); }}
  .msg.bot .avatar {{ background:linear-gradient(135deg,var(--accent),#9b6bff); color:#fff; }}
  .bubble {{ min-width:0; flex:1; }}
  .bubble .md {{ overflow-wrap:anywhere; }}
  .bubble .md pre {{ background:var(--panel); border:1px solid var(--line); padding:12px; border-radius:8px; overflow-x:auto; }}
  .bubble .md code {{ background:var(--panel); padding:1px 5px; border-radius:4px; font-size:13px; }}
  .bubble .md pre code {{ background:none; padding:0; }}
  .bubble .md h1,.bubble .md h2,.bubble .md h3 {{ margin:14px 0 6px; }}
  .bubble .md p {{ margin:8px 0; }}
  .bubble .md blockquote {{ border-left:3px solid var(--accent); margin:8px 0; padding:2px 12px; color:var(--muted); }}
  .copybtn {{ margin-top:6px; border:1px solid var(--line); background:none; color:var(--muted); font-size:11px; padding:4px 9px; border-radius:6px; cursor:pointer; }}
  .copybtn:hover {{ color:var(--ink); border-color:var(--accent); }}
  .hello {{ text-align:center; margin-top:9vh; }}
  .hello h1 {{ font-size:26px; margin:14px 0 6px; }}
  .hello p {{ color:var(--muted); max-width:520px; margin:0 auto 22px; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:center; max-width:640px; margin:0 auto; }}
  .chip {{ border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:16px; padding:8px 14px; font-size:13px; cursor:pointer; }}
  .chip:hover {{ border-color:var(--accent); }}
  .composer {{ border-top:1px solid var(--line); background:var(--panel); padding:14px 20px 16px; }}
  .box {{ max-width:860px; margin:0 auto; }}
  .row {{ display:flex; gap:10px; align-items:flex-end; background:var(--panel2); border:1px solid var(--line); border-radius:12px; padding:10px 12px; }}
  .row:focus-within {{ border-color:var(--accent); }}
  textarea {{ flex:1; background:none; border:0; color:var(--ink); font:inherit; resize:none; outline:none; max-height:180px; }}
  .send {{ border:0; background:var(--accent); color:#fff; width:38px; height:38px; border-radius:9px; font-size:16px; cursor:pointer; }}
  .send:disabled {{ opacity:.5; cursor:wait; }}
  .below {{ display:flex; justify-content:space-between; align-items:center; margin-top:8px; color:var(--muted); font-size:12px; }}
  .toggle {{ display:flex; align-items:center; gap:7px; cursor:pointer; user-select:none; }}
  .toggle input {{ accent-color:var(--accent); }}
  dialog {{ background:var(--panel); color:var(--ink); border:1px solid var(--line); border-radius:12px; max-width:680px; width:92vw; max-height:80vh; padding:0; }}
  dialog::backdrop {{ background:rgba(0,0,0,.55); }}
  .dlghead {{ display:flex; justify-content:space-between; align-items:center; padding:14px 18px; border-bottom:1px solid var(--line); }}
  .dlgbody {{ padding:14px 18px; overflow:auto; max-height:62vh; }}
  .learning {{ border:1px solid var(--line); border-radius:9px; padding:12px; margin-bottom:10px; }}
  .learning h5 {{ margin:0 0 6px; }} .learning .meta {{ color:var(--muted); font-size:11px; margin-bottom:6px; }}
  .learning details {{ color:var(--muted); font-size:13px; }}
  .xbtn {{ border:0; background:none; color:var(--muted); cursor:pointer; font-size:15px; }}
  @media (max-width:820px) {{ .app {{ grid-template-columns:1fr; }} .side {{ display:none; }} }}
</style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="brand"><div class="logo">8T</div><div><b>Copy Studio</b><span>LinkedIn · YouTube · Direct response</span></div></div>
    <button class="newchat" id="new-chat">+ New chat</button>
    <div class="convos" id="convos"></div>
    <div class="teach">
      <h4>Teach it</h4>
      <input id="yt-url" placeholder="Paste a YouTube link to learn from">
      <button id="yt-learn">Learn from video</button>
      <div class="memlink"><a id="open-memory">View memory</a></div>
    </div>
    <div class="status"><span>v{version}</span><span class="dot {status_class}">● {status_text}</span></div>
  </aside>
  <main class="main">
    <div class="chat" id="chat"><div class="inner" id="thread">
      <div class="hello" id="hello">
        <div class="logo" style="margin:0 auto;width:52px;height:52px;font-size:20px;">8T</div>
        <h1>8-Thon Copy Studio</h1>
        <p>Your copywriting strategist for LinkedIn, YouTube, and everything that sells AI implementation. Ask for copy, feed it videos, turn on research mode for live trends.</p>
        <div class="chips" id="chips">
          <button class="chip">Write a LinkedIn post about a lesson from building our lead scraper</button>
          <button class="chip">Write a YouTube script: how a local business can use AI this month</button>
          <button class="chip">Give me 10 hooks about verified leads vs guessed emails</button>
          <button class="chip">Rewrite my LinkedIn headline and About section</button>
          <button class="chip">Research mode: what's trending in AI for small business this week?</button>
        </div>
      </div>
    </div></div>
    <div class="composer"><div class="box">
      <div class="row">
        <textarea id="input" rows="1" placeholder="Ask for copy... (Enter to send, Shift+Enter for a new line)"></textarea>
        <button class="send" id="send" title="Send">➤</button>
      </div>
      <div class="below">
        <label class="toggle"><input type="checkbox" id="research"> Research mode - browse the live web for trends</label>
        <span id="model-note"></span>
      </div>
    </div></div>
  </main>
</div>
<dialog id="memory">
  <div class="dlghead"><b>Learned memory</b><button class="xbtn" id="close-memory">✕</button></div>
  <div class="dlgbody" id="memory-list"></div>
</dialog>
<script>
const $ = s => document.querySelector(s);
let conversationId = "";
let busy = false;
marked.setOptions({{ breaks: true }});

function el(tag, cls, text) {{ const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }}

function addMessage(role, markdown) {{
  $("#hello")?.remove();
  const wrap = el("div", "msg " + (role === "user" ? "user" : "bot"));
  const av = el("div", "avatar", role === "user" ? "You" : "8T");
  const bubble = el("div", "bubble");
  const md = el("div", "md");
  md.innerHTML = marked.parse(markdown || "");
  bubble.appendChild(md);
  if (role !== "user") {{
    const btn = el("button", "copybtn", "Copy");
    btn.onclick = () => {{ navigator.clipboard.writeText(md.innerText); btn.textContent = "Copied"; setTimeout(() => btn.textContent = "Copy", 1200); }};
    bubble.appendChild(btn);
  }}
  wrap.append(av, bubble);
  $("#thread").appendChild(wrap);
  scrollDown();
  return md;
}}

function scrollDown() {{ const c = $("#chat"); c.scrollTop = c.scrollHeight; }}

async function loadConversations() {{
  const list = await (await fetch("/api/conversations")).json();
  const box = $("#convos"); box.innerHTML = "";
  for (const c of list) {{
    const row = el("div", "convo" + (c.id === conversationId ? " active" : ""));
    const t = el("span", "t", c.title); row.appendChild(t);
    const del = el("button", "del", "✕");
    del.onclick = async ev => {{ ev.stopPropagation(); await fetch("/api/conversations/" + c.id, {{ method: "DELETE" }}); if (c.id === conversationId) newChat(); loadConversations(); }};
    row.appendChild(del);
    row.onclick = () => openConversation(c.id);
    box.appendChild(row);
  }}
}}

async function openConversation(id) {{
  conversationId = id;
  const data = await (await fetch("/api/conversations/" + id)).json();
  $("#thread").innerHTML = "";
  for (const m of data.messages) addMessage(m.role === "user" ? "user" : "bot", m.content);
  loadConversations();
}}

function newChat() {{ conversationId = ""; location.reload(); }}
$("#new-chat").onclick = newChat;

async function send() {{
  const input = $("#input");
  const text = input.value.trim();
  if (!text || busy) return;
  busy = true; $("#send").disabled = true;
  input.value = ""; autosize();
  addMessage("user", text);
  const md = addMessage("bot", "…");
  let acc = "";
  try {{
    const res = await fetch("/api/chat", {{
      method: "POST", headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ message: text, conversation_id: conversationId, research: $("#research").checked }})
    }});
    if (!res.ok) {{ const err = await res.json().catch(() => ({{}})); md.innerHTML = marked.parse("**Error:** " + (err.detail || res.status)); busy = false; $("#send").disabled = false; return; }}
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {{
      const {{ done, value }} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {{ stream: true }});
      const events = buffer.split("\\n\\n"); buffer = events.pop();
      for (const evt of events) {{
        const line = evt.split("\\n").find(l => l.startsWith("data: "));
        if (!line) continue;
        const data = JSON.parse(line.slice(6));
        if (data.type === "start") conversationId = data.conversation_id;
        else if (data.type === "delta") {{ acc += data.text; md.innerHTML = marked.parse(acc); scrollDown(); }}
        else if (data.type === "error") {{ md.innerHTML = marked.parse("**Error:** " + data.message); }}
      }}
    }}
  }} catch (e) {{ md.innerHTML = marked.parse("**Error:** " + e.message); }}
  busy = false; $("#send").disabled = false;
  loadConversations();
}}

$("#send").onclick = send;
$("#input").addEventListener("keydown", e => {{ if (e.key === "Enter" && !e.shiftKey) {{ e.preventDefault(); send(); }} }});
function autosize() {{ const t = $("#input"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 180) + "px"; }}
$("#input").addEventListener("input", autosize);
document.querySelectorAll("#chips .chip").forEach(chip => chip.onclick = () => {{
  const text = chip.textContent;
  if (text.startsWith("Research mode")) $("#research").checked = true;
  $("#input").value = text.replace(/^Research mode: /, ""); autosize(); $("#input").focus();
}});

$("#yt-learn").onclick = async () => {{
  const url = $("#yt-url").value.trim();
  if (!url) return;
  const btn = $("#yt-learn"); btn.disabled = true; btn.textContent = "Watching & learning…";
  try {{
    const res = await fetch("/api/youtube/ingest", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ url }}) }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.status);
    $("#yt-url").value = "";
    addMessage("bot", "**Learned from that video.** It's now in my memory and I'll apply it going forward.\\n\\n" + data.summary);
  }} catch (e) {{ addMessage("bot", "**Couldn't learn from that video:** " + e.message); }}
  btn.disabled = false; btn.textContent = "Learn from video";
}};

$("#open-memory").onclick = async () => {{
  const list = await (await fetch("/api/learnings")).json();
  const box = $("#memory-list"); box.innerHTML = "";
  if (!list.length) box.appendChild(el("p", "", "Nothing learned yet. Feed it YouTube links or save notes."));
  for (const item of list) {{
    const card = el("div", "learning");
    const head = el("div", "dlghead"); head.style.padding = "0"; head.style.border = "0";
    head.appendChild(el("h5", "", item.title));
    const del = el("button", "xbtn", "🗑");
    del.onclick = async () => {{ await fetch("/api/learnings/" + item.id, {{ method: "DELETE" }}); card.remove(); }};
    head.appendChild(del);
    card.appendChild(head);
    card.appendChild(el("div", "meta", item.source_type + (item.source_ref ? " · " + item.source_ref : "") + " · " + item.created_at));
    const details = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = "Show lesson";
    const body = el("div", "md"); body.innerHTML = marked.parse(item.content);
    details.append(summary, body); card.appendChild(details);
    box.appendChild(card);
  }}
  $("#memory").showModal();
}};
$("#close-memory").onclick = () => $("#memory").close();

fetch("/api/status").then(r => r.json()).then(s => {{ $("#model-note").textContent = s.model; }});
loadConversations();
</script>
</body>
</html>"""

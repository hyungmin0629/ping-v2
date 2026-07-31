"""docs/erd.json → 카드형 ERD 아티팩트. erd.json 을 다시 뽑았으면 이것도 다시 돌린다."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "erd-board.html"
sys.stdout.reconfigure(encoding="utf-8")

data = json.loads((ROOT / "docs" / "erd.json").read_text(encoding="utf-8"))
n_tables = len(data["tables"])
n_cols = sum(len(t["columns"]) for t in data["tables"])
n_edges = len(data["edges"])

# 도메인을 4열로 나눈다. 큰 도메인이 한 열을 독차지하지 않도록 손으로 배치했다 —
# 자동 배치는 열 높이가 들쭉날쭉해진다.
COLUMNS = [
    ["기준 정보", "학교 정보"],
    ["유저", "친구", "게시판"],
    ["질문과 투표"],
    ["하트", "신고와 제재"],
]

OUT.write_text(f"""<title>ping-v2 스키마 ERD</title>
<style>
:root {{
  --bg:#F5F7F6; --card:#FFFFFF; --card-2:#EDF1EF;
  --ink:#151A18; --ink-2:#54615C; --ink-3:#84938C;
  --rule:#D6DEDA; --rule-soft:#E7EDEA;
  --accent:#0F6E5C; --type:#3A7F97; --fk:#A8621A;
  --shadow:0 1px 2px rgba(20,35,28,.06), 0 3px 12px rgba(20,35,28,.045);
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: "Pretendard", -apple-system, "Segoe UI", "Apple SD Gothic Neo",
          "Malgun Gothic", system-ui, sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0E1312; --card:#171D1B; --card-2:#202826;
           --ink:#E2E9E6; --ink-2:#96A29D; --ink-3:#6A7873;
           --rule:#2A3431; --rule-soft:#222B28;
           --accent:#4FC0A6; --type:#63AEC7; --fk:#D69A4F;
           --shadow:0 1px 2px rgba(0,0,0,.45), 0 3px 12px rgba(0,0,0,.3); }}
}}
:root[data-theme="dark"] {{ --bg:#0E1312; --card:#171D1B; --card-2:#202826;
  --ink:#E2E9E6; --ink-2:#96A29D; --ink-3:#6A7873; --rule:#2A3431; --rule-soft:#222B28;
  --accent:#4FC0A6; --type:#63AEC7; --fk:#D69A4F;
  --shadow:0 1px 2px rgba(0,0,0,.45), 0 3px 12px rgba(0,0,0,.3); }}
:root[data-theme="light"] {{ --bg:#F5F7F6; --card:#FFFFFF; --card-2:#EDF1EF;
  --ink:#151A18; --ink-2:#54615C; --ink-3:#84938C; --rule:#D6DEDA; --rule-soft:#E7EDEA;
  --accent:#0F6E5C; --type:#3A7F97; --fk:#A8621A;
  --shadow:0 1px 2px rgba(20,35,28,.06), 0 3px 12px rgba(20,35,28,.045); }}

* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--sans);
  line-height:1.6; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1500px; margin:0 auto; padding:40px clamp(14px,3vw,28px) 72px;
  display:flex; flex-direction:column; gap:24px; }}

.eyebrow {{ font-family:var(--mono); font-size:11px; letter-spacing:.15em;
  text-transform:uppercase; color:var(--accent); }}
h1 {{ font-family:var(--mono); font-size:clamp(24px,3.2vw,36px); font-weight:650;
  letter-spacing:-.02em; margin:6px 0 8px; }}
.lede {{ color:var(--ink-2); max-width:72ch; margin:0; font-size:14.5px; }}

.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(108px,1fr)); gap:1px;
  background:var(--rule); border:1px solid var(--rule); border-radius:4px; overflow:hidden; }}
.stat {{ background:var(--card); padding:12px 14px; display:flex; flex-direction:column; gap:2px; }}
.stat b {{ font-family:var(--mono); font-size:20px; font-weight:600;
  font-variant-numeric:tabular-nums; letter-spacing:-.02em; }}
.stat span {{ font-size:10.5px; color:var(--ink-3); font-family:var(--mono); letter-spacing:.05em; }}

.controls {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:11px 13px;
  background:var(--card); border:1px solid var(--rule); border-radius:4px;
  position:sticky; top:0; z-index:5; }}
.clabel {{ font-family:var(--mono); font-size:10px; letter-spacing:.13em;
  text-transform:uppercase; color:var(--ink-3); margin-right:2px; }}
.chip, .btn {{ font-family:var(--mono); font-size:11.5px; padding:5px 10px;
  border:1px solid var(--rule); border-radius:3px; background:transparent;
  color:var(--ink-2); cursor:pointer; display:inline-flex; align-items:center; gap:6px; }}
.chip:hover, .btn:hover {{ border-color:var(--ink-3); color:var(--ink); }}
.chip[aria-pressed="false"] {{ opacity:.35; }}
.chip i {{ width:9px; height:9px; border-radius:2px; border:1px solid rgba(0,0,0,.15); flex:none; }}
.btn[aria-pressed="true"] {{ background:var(--card-2); border-color:var(--accent); color:var(--ink); }}
.spacer {{ flex:1 1 auto; }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}

.board-scroll {{ overflow-x:auto; }}
.board {{ position:relative; min-width:1320px; padding:2px; }}
#edges {{ position:absolute; inset:0; width:100%; height:100%; pointer-events:none;
  z-index:0; overflow:visible; }}
#edges path {{ fill:none; stroke:var(--ink-3); stroke-width:1; opacity:.22; }}
#edges path.hot {{ stroke:var(--accent); stroke-width:1.8; opacity:1; }}
#edges path.cold {{ opacity:.05; }}
.cols {{ position:relative; z-index:1; display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr)); gap:20px; align-items:start; }}
.col {{ display:flex; flex-direction:column; gap:10px; }}
.dhead {{ font-family:var(--mono); font-size:10px; letter-spacing:.16em; text-transform:uppercase;
  color:var(--ink-3); padding-bottom:3px; border-bottom:1px solid var(--rule); margin-top:8px;
  display:flex; justify-content:space-between; align-items:center; }}
.col > .dhead:first-child {{ margin-top:0; }}
.dhead i {{ width:9px; height:9px; border-radius:2px; border:1px solid rgba(0,0,0,.15); }}

.node {{ display:block; width:100%; text-align:left; background:var(--card);
  border:1px solid var(--rule); border-left:3px solid var(--dc,#999); border-radius:3px;
  padding:0; cursor:pointer; font:inherit; color:inherit; box-shadow:var(--shadow);
  transition:border-color .12s, transform .12s, opacity .12s; overflow:hidden; }}
.node:hover {{ transform:translateY(-1px); border-color:var(--ink-3); }}
.node.dim {{ opacity:.16; }}
.node.sel {{ border-color:var(--accent);
  box-shadow:0 0 0 2px color-mix(in srgb, var(--accent) 26%, transparent), var(--shadow); }}
.nm {{ font-family:var(--mono); font-size:12.5px; font-weight:650; letter-spacing:-.01em;
  display:flex; justify-content:space-between; gap:8px; padding:7px 9px;
  background:var(--card-2); border-bottom:1px solid var(--rule-soft); word-break:break-all; }}
.nm .cnt {{ font-weight:400; color:var(--ink-3); font-size:10px; }}
.cap {{ display:block; padding:4px 9px 5px; font-size:10.5px; color:var(--ink-2);
  border-bottom:1px dashed var(--rule-soft); line-height:1.45; }}
.cols-list {{ display:block; padding:5px 9px 7px; }}
.crow {{ display:flex; gap:7px; align-items:baseline; font-family:var(--mono);
  font-size:10px; line-height:1.75; white-space:nowrap; }}
.cname {{ color:var(--ink-2); }}
.crow.key .cname {{ color:var(--ink); font-weight:600; }}
.ctype {{ color:var(--type); margin-left:auto; }}
.badge {{ font-size:8.5px; letter-spacing:.06em; padding:0 3px; border-radius:2px;
  border:1px solid currentColor; flex:none; }}
.b-pk {{ color:var(--accent); }}
.b-fk {{ color:var(--fk); }}
.nn {{ color:var(--ink-3); font-size:8.5px; }}
body:not(.show-types) .ctype {{ display:none; }}
body.keys-only .crow:not(.key) {{ display:none; }}

.detail {{ background:var(--card); border:1px solid var(--rule); border-radius:4px;
  padding:16px 18px; min-height:120px; }}
.detail-empty {{ color:var(--ink-3); font-family:var(--mono); font-size:13px; margin:0; }}
.detail h3 {{ font-family:var(--mono); font-size:15px; margin:0 0 2px; font-weight:650; }}
.detail .meta {{ font-family:var(--mono); font-size:11px; color:var(--ink-3); margin-bottom:10px; }}
.detail .dt {{ font-family:var(--sans); font-size:13px; font-weight:500; color:var(--ink-2); }}
.detail .why {{ font-size:13.5px; color:var(--ink-2); margin:0 0 16px; max-width:82ch;
  padding-left:11px; border-left:2px solid var(--accent); line-height:1.65; }}
.detail .why.muted {{ border-left-color:var(--rule); color:var(--ink-3); }}
.dgrid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:20px; }}
.dgrid h4 {{ font-family:var(--mono); font-size:10px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--ink-3); margin:0 0 7px; }}
table {{ border-collapse:collapse; width:100%; font-family:var(--mono); font-size:11.5px; }}
th {{ text-align:left; font-size:9.5px; letter-spacing:.1em; text-transform:uppercase;
  color:var(--ink-3); font-weight:600; border-bottom:1px solid var(--rule);
  padding:0 10px 4px 0; white-space:nowrap; }}
td {{ padding:3px 10px 3px 0; border-bottom:1px solid var(--rule-soft); vertical-align:top;
  white-space:nowrap; }}
td.t {{ color:var(--type); }} td.n {{ color:var(--ink-3); }}
td.k .pk {{ color:var(--accent); font-weight:600; }}
td.k .fk {{ color:var(--fk); font-weight:600; }}
.rel {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:4px; }}
.rel li {{ font-family:var(--mono); font-size:11px; color:var(--ink-2);
  padding-left:10px; border-left:2px solid var(--rule); }}
.rel em {{ font-style:normal; color:var(--ink); }}
.scroller {{ overflow-x:auto; }}
.usage {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:22px;
  background:var(--card); border:1px solid var(--rule); border-radius:4px; padding:18px 20px; }}
.usage h3 {{ font-family:var(--mono); font-size:13px; margin:0 0 3px; font-weight:650; }}
.usage .sub {{ font-size:12px; color:var(--ink-2); margin:0 0 14px; max-width:60ch; }}
.ugroup {{ margin-bottom:15px; }}
.ugroup:last-child {{ margin-bottom:0; }}
.ugroup > p {{ font-family:var(--mono); font-size:9.5px; letter-spacing:.13em;
  text-transform:uppercase; color:var(--ink-3); margin:0 0 6px;
  padding-bottom:3px; border-bottom:1px solid var(--rule-soft); }}
.ulist {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:7px; }}
.ulist li {{ padding-left:10px; border-left:2px solid var(--zc,var(--rule)); }}
.ulist b {{ font-family:var(--mono); font-size:11.5px; font-weight:600; display:block; }}
.ulist span {{ font-size:11.5px; color:var(--ink-2); line-height:1.5; }}
.z-live {{ --zc:var(--accent); }}
.z-no-screen {{ --zc:var(--fk); }}
.z-no-writer {{ --zc:#B4484B; }}
.tally {{ list-style:none; margin:0; padding:0; }}
.tally li {{ display:flex; justify-content:space-between; gap:10px; font-family:var(--mono);
  font-size:11.5px; padding:2.5px 0; border-bottom:1px solid var(--rule-soft); }}
.tally li:last-child {{ border-bottom:0; }}
.tally .n {{ font-variant-numeric:tabular-nums; color:var(--ink); }}
.tally .z {{ color:var(--ink-3); }}
footer {{ font-family:var(--mono); font-size:11px; color:var(--ink-3);
  border-top:1px solid var(--rule); padding-top:14px; }}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">ping-v2 · 살아 있는 스키마에서 뽑음</div>
    <h1>ERD</h1>
    <p class="lede">테이블 상자에 <strong>모든 컬럼과 타입</strong>, 그리고 그 테이블이
    무엇인지가 한 줄로 붙어 있다. 상자를 누르면 <strong>왜 이 구조인지</strong>와
    제약·관계가 아래에 펼쳐진다. 설명은 <code>db/ddl/*.sql</code> 의 주석에서 그대로
    뽑았고, 구조는 <code>pg_catalog</code> 에서 읽었다 — 손으로 옮겨 적은 것이 없다.</p>
  </header>

  <section class="stats">
    <div class="stat"><b>{n_tables}</b><span>테이블</span></div>
    <div class="stat"><b>{n_cols}</b><span>컬럼</span></div>
    <div class="stat"><b>{n_edges}</b><span>외래키</span></div>
    <div class="stat"><b>{len(data['domains'])}</b><span>도메인</span></div>
  </section>

  <section class="controls" id="controls">
    <span class="clabel">도메인</span>
    <span id="chips"></span>
    <span class="spacer"></span>
    <button class="btn" id="tType" aria-pressed="true">타입</button>
    <button class="btn" id="tKeys" aria-pressed="false">키만</button>
    <button class="btn" id="reset">선택 해제</button>
  </section>

  <div class="board-scroll">
    <div class="board" id="board">
      <svg id="edges" aria-hidden="true"></svg>
      <div class="cols" id="cols"></div>
    </div>
  </div>

  <section class="detail" id="detail" aria-live="polite">
    <p class="detail-empty">테이블을 누르면 컬럼 정의와 관계가 여기 펼쳐집니다.</p>
  </section>

  <section class="usage">
    <div>
      <h3>비어 있는 표</h3>
      <p class="sub">구조가 있다고 쓰이는 것은 아니다. 어떤 표가 왜 비었는지를
      갈라 두면, <strong>기능이 없어서 빈 것</strong>과 <strong>아무도 아직 안 해서
      빈 것</strong>이 섞이지 않는다.</p>
      <div id="empties"></div>
    </div>
    <div>
      <h3>쌓인 활동</h3>
      <p class="sub">사람이 만든 행만 센다. 마스터 표(선택지 목록)와 외부에서 받아온
      참조 표는 뺐다 — <code>withdrawal_reason</code> 6행은 탈퇴 사유 <em>선택지</em>가
      6개라는 뜻이지 탈퇴가 6건이라는 뜻이 아니다.</p>
      <ul class="tally" id="tally"></ul>
    </div>
  </section>

  <footer>
    <p>생성물이다 — <code>python db/erd.py</code> 가 <code>docs/erd.json</code> 을 다시 뽑는다.
    전체 정의는 <code>db/ddl/</code> 이 진실이다. 기준 {date.today():%Y-%m-%d}</p>
  </footer>
</div>

<script>
const DATA = {json.dumps(data, ensure_ascii=False)};
const LAYOUT = {json.dumps(COLUMNS, ensure_ascii=False)};
const FILL = {{"기준 정보":"#8FA8A0","유저":"#4E9E86","친구":"#7FA65E","질문과 투표":"#C0A24A",
  "하트":"#C98A55","신고와 제재":"#C07A7A","학교 정보":"#6E8FBF","게시판":"#9781B8","기타":"#999"}};

const byName = new Map(DATA.tables.map(t => [t.name, t]));
const cols = document.getElementById("cols");
const svg  = document.getElementById("edges");
const chips = document.getElementById("chips");
let selected = null;
const hidden = new Set();

for (const [ci, domains] of LAYOUT.entries()) {{
  const col = document.createElement("div");
  col.className = "col";
  for (const d of domains) {{
    const members = DATA.tables.filter(t => t.domain === d);
    if (!members.length) continue;
    const h = document.createElement("div");
    h.className = "dhead";
    h.innerHTML = `<span>${{d}}</span><i style="background:${{FILL[d]}}"></i>`;
    col.appendChild(h);
    for (const t of members) col.appendChild(nodeEl(t));
  }}
  cols.appendChild(col);
}}

function nodeEl(t) {{
  const el = document.createElement("button");
  el.className = "node";
  el.type = "button";
  el.id = "n-" + t.name;
  el.dataset.name = t.name;
  el.dataset.domain = t.domain;
  el.style.setProperty("--dc", FILL[t.domain] || "#999");
  const rows = t.columns.map(c => {{
    const key = c.pk || c.fk;
    const badge = c.pk ? '<span class="badge b-pk">PK</span>'
                : c.fk ? '<span class="badge b-fk">FK</span>' : "";
    const nn = c.null ? '' : '<span class="nn">•</span>';
    return `<span class="crow ${{key ? "key" : ""}}">${{badge}}<span class="cname">${{c.name}}</span>`
         + `${{nn}}<span class="ctype">${{c.type}}</span></span>`;
  }}).join("");
  const cap = t.title ? `<span class="cap">${{t.title}}</span>` : "";
  el.innerHTML = `<span class="nm">${{t.name}}<span class="cnt">${{t.columns.length}}</span></span>`
               + cap + `<span class="cols-list">${{rows}}</span>`;
  el.addEventListener("click", () => select(t.name === selected ? null : t.name));
  return el;
}}

for (const d of DATA.domains) {{
  const b = document.createElement("button");
  b.className = "chip"; b.type = "button"; b.setAttribute("aria-pressed", "true");
  b.innerHTML = `<i style="background:${{FILL[d]}}"></i>${{d}}`;
  b.addEventListener("click", () => {{
    hidden.has(d) ? hidden.delete(d) : hidden.add(d);
    b.setAttribute("aria-pressed", String(!hidden.has(d)));
    applyFilter(); requestAnimationFrame(draw);
  }});
  chips.appendChild(b);
}}

function applyFilter() {{
  for (const el of document.querySelectorAll(".node"))
    el.style.display = hidden.has(el.dataset.domain) ? "none" : "";
  for (const h of document.querySelectorAll(".dhead"))
    h.style.display = hidden.has(h.firstChild.textContent) ? "none" : "";
}}

function draw() {{
  const box = document.getElementById("board").getBoundingClientRect();
  svg.setAttribute("viewBox", `0 0 ${{box.width}} ${{box.height}}`);
  svg.innerHTML = "";
  for (const e of DATA.edges) {{
    const a = document.getElementById("n-" + e.from);
    const b = document.getElementById("n-" + e.to);
    if (!a || !b || a.offsetParent === null || b.offsetParent === null) continue;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const x1 = ra.left - box.left + ra.width / 2, y1 = ra.top - box.top + 10;
    const x2 = rb.left - box.left + rb.width / 2, y2 = rb.top - box.top + 10;
    const dx = Math.max(40, Math.abs(x2 - x1) * .45);
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", `M${{x1}},${{y1}} C${{x1 + (x2 > x1 ? dx : -dx)}},${{y1}} `
                      + `${{x2 - (x2 > x1 ? dx : -dx)}},${{y2}} ${{x2}},${{y2}}`);
    if (e.null) p.setAttribute("stroke-dasharray", "3 3");
    if (selected) p.classList.add(e.from === selected || e.to === selected ? "hot" : "cold");
    svg.appendChild(p);
  }}
}}

function select(name) {{
  selected = name;
  for (const el of document.querySelectorAll(".node")) {{
    el.classList.toggle("sel", el.dataset.name === name);
    const linked = !name || el.dataset.name === name ||
      DATA.edges.some(e => (e.from === name && e.to === el.dataset.name) ||
                           (e.to === name && e.from === el.dataset.name));
    el.classList.toggle("dim", Boolean(name) && !linked);
  }}
  renderDetail(name);
  draw();
}}

function renderDetail(name) {{
  const d = document.getElementById("detail");
  if (!name) {{
    d.innerHTML = '<p class="detail-empty">테이블을 누르면 컬럼 정의와 관계가 여기 펼쳐집니다.</p>';
    return;
  }}
  const t = byName.get(name);
  const rows = t.columns.map(c => `<tr>
      <td class="${{c.pk || c.fk ? "k" : ""}}">${{c.name}}</td>
      <td class="t">${{c.type}}</td>
      <td class="n">${{c.null ? "NULL 허용" : "NOT NULL"}}</td>
      <td class="k">${{c.pk ? '<span class="pk">PK</span>'
                      : c.fk ? `<span class="fk">FK → ${{c.fk}}</span>` : ""}}</td>
    </tr>`).join("");
  const out = DATA.edges.filter(e => e.from === name)
    .map(e => `<li><em>${{e.col}}</em> → ${{e.to}}${{e.null ? " (NULL 허용)" : ""}}</li>`).join("");
  const inc = DATA.edges.filter(e => e.to === name)
    .map(e => `<li>${{e.from}}.<em>${{e.col}}</em> → 여기</li>`).join("");
  const uq = t.uniques.map(u => `<li>UNIQUE (<em>${{u}}</em>)</li>`).join("");
  const why = t.note
    ? `<p class="why">${{t.note}}</p>`
    : (t.title ? "" : '<p class="why muted">DDL 에 설명 주석이 없는 테이블이다.</p>');
  d.innerHTML = `<h3>${{t.name}}${{t.title ? ` <span class="dt">${{t.title}}</span>` : ""}}</h3>
    <div class="meta">${{t.domain}} · ${{rowText(name)}} · 컬럼 ${{t.columns.length}} ·
      나가는 FK ${{DATA.edges.filter(e => e.from === name).length}} ·
      들어오는 FK ${{DATA.edges.filter(e => e.to === name).length}}</div>
    ${{why}}
    <div class="dgrid">
      <div><h4>컬럼</h4><div class="scroller"><table>
        <thead><tr><th>이름</th><th>타입</th><th>NULL</th><th>키</th></tr></thead>
        <tbody>${{rows}}</tbody></table></div></div>
      <div>
        <h4>이 테이블이 참조하는 것</h4><ul class="rel">${{out || "<li>없음</li>"}}</ul>
        <h4 style="margin-top:14px">이 테이블을 참조하는 것</h4><ul class="rel">${{inc || "<li>없음</li>"}}</ul>
        ${{uq ? `<h4 style="margin-top:14px">UNIQUE 제약</h4><ul class="rel">${{uq}}</ul>` : ""}}
      </div>
    </div>`;
}}

// 실데이터 현황 ------------------------------------------------------
// 숫자도 사유도 erd.json 에서 온다. 여기 손으로 적지 않는다 —
// 적는 순간 DB 가 바뀌어도 이 페이지만 옛말을 하게 된다.
const USE = DATA.data || null;

function rowText(name) {{
  if (!USE) return "";
  const n = USE.counts[name];
  if (n === undefined) return "";
  return n === 0 ? "비어 있음" : `${{n.toLocaleString()}}행`;
}}

if (USE) {{
  const ZONE = [
    ["live",      "기능은 살아 있는데 아직 아무도 안 했다"],
    ["no-screen", "화면이나 실행 코드가 없다"],
    ["no-writer", "계획에는 있는데 쓰는 코드가 없다"],
  ];
  const empties = Object.keys(USE.counts).filter(k => USE.counts[k] === 0).sort();
  document.getElementById("empties").innerHTML = ZONE.map(([kind, label]) => {{
    const mine = empties.filter(t => (USE.empty_reason[t] || {{}}).kind === kind);
    if (!mine.length) return "";
    return `<div class="ugroup"><p>${{label}} · ${{mine.length}}</p>
      <ul class="ulist z-${{kind}}">${{mine.map(t =>
        `<li><b>${{t}}</b><span>${{USE.empty_reason[t].why}}</span></li>`).join("")}}</ul></div>`;
  }}).join("");

  // 사유를 안 적어둔 빈 표가 생기면 조용히 사라지지 않게 드러낸다.
  const unlabelled = empties.filter(t => !USE.empty_reason[t]);
  if (unlabelled.length) {{
    document.getElementById("empties").innerHTML +=
      `<div class="ugroup"><p>사유 미기재 · ${{unlabelled.length}}</p>
       <ul class="ulist"><li><b>${{unlabelled.join(", ")}}</b>
       <span>db/erd.py 의 EMPTY_REASON 에 추가할 것.</span></li></ul></div>`;
  }}

  const acts = Object.keys(USE.counts)
    .filter(t => USE.kind[t] === "activity")
    .sort((a, b) => USE.counts[b] - USE.counts[a]);
  document.getElementById("tally").innerHTML = acts.map(t =>
    `<li><span>${{t}}</span><span class="${{USE.counts[t] ? "n" : "z"}}">${{
      USE.counts[t] ? USE.counts[t].toLocaleString() : "—"}}</span></li>`).join("");
}}

document.body.classList.add("show-types");
document.getElementById("tType").addEventListener("click", (e) => {{
  const on = e.currentTarget.getAttribute("aria-pressed") === "true";
  e.currentTarget.setAttribute("aria-pressed", String(!on));
  document.body.classList.toggle("show-types", !on);
  requestAnimationFrame(draw);
}});
document.getElementById("tKeys").addEventListener("click", (e) => {{
  const on = e.currentTarget.getAttribute("aria-pressed") === "true";
  e.currentTarget.setAttribute("aria-pressed", String(!on));
  document.body.classList.toggle("keys-only", !on);
  requestAnimationFrame(draw);
}});
document.getElementById("reset").addEventListener("click", () => select(null));

new ResizeObserver(() => draw()).observe(document.getElementById("board"));
addEventListener("load", draw);
draw();
</script>
""", encoding="utf-8")
print(f"생성 — 테이블 {n_tables} / 컬럼 {n_cols} / FK {n_edges}")

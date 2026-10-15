"""Generate a single self-contained HTML browser for the corpus.

No CDN, no build step, no framework: the data is inlined as JSON and the sorting
and filtering is vanilla JS. The page therefore works opened straight from disk
(file://) as well as from GitHub Pages, and keeps working when today's table
library has had four breaking releases.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import DOCS_DIR, Vocabularies

NEW_WINDOW_DAYS = 30


def _pack(rows: list[dict], vocab: Vocabularies) -> dict:
    """Compact the rows: vocabulary terms become indices into shared name lists."""
    fam = list(vocab.algorithm_families)
    pde = list(vocab.pde_targets)
    cap = list(vocab.capability_axes)
    idx = ({n: i for i, n in enumerate(fam)},
           {n: i for i, n in enumerate(pde)},
           {n: i for i, n in enumerate(cap)})
    split = lambda s: [p for p in (x.strip() for x in s.split(";")) if p]
    packed = []
    for r in rows:
        packed.append({
            "i": r["arxiv_id"], "d": r["published"], "t": r["title"],
            "a": r["first_author"], "na": r["n_authors"],
            "c": r["citations_crossref"], "v": r["venue"] or "",
            "f": sorted(idx[0][x] for x in split(r["algorithm_families"]) if x in idx[0]),
            "p": sorted(idx[1][x] for x in split(r["pde_targets"]) if x in idx[1]),
            "x": sorted(idx[2][x] for x in split(r["capability_axes"]) if x in idx[2]),
            "q": 1 if r["cfd_facing"] else 0,
            "s": r["first_seen"], "ab": r["abstract"],
        })
    return {"rows": packed, "fam": fam, "pde": pde, "cap": cap}


def build(rows: list[dict], vocab: Vocabularies, outdir: Path | None = None,
          title: str = "Quantum algorithms for PDEs — literature watch") -> Path:
    outdir = outdir or DOCS_DIR
    outdir.mkdir(parents=True, exist_ok=True)
    payload = _pack(rows, vocab)
    payload["meta"] = {
        "generated": date.today().isoformat(),
        "n_total": len(rows),
        "n_cfd": sum(1 for r in rows if r["cfd_facing"]),
        "n_cited": sum(1 for r in rows if r["citations_crossref"] is not None),
        "schema_version": vocab.schema_version,
        "new_window_days": NEW_WINDOW_DAYS,
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.replace("__TITLE__", title).replace("__PAYLOAD__", blob)
    path = outdir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { --fg:#1a1a1a; --mut:#666; --line:#e2e2e2; --accent:#B5179E; --bg:#fff; --chip:#f3f3f5; }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         color:var(--fg); background:var(--bg); }
  header { padding:18px 22px 10px; border-bottom:1px solid var(--line); }
  h1 { margin:0 0 4px; font-size:17px; font-weight:600; }
  .meta { color:var(--mut); font-size:12px; }
  .controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center;
              padding:12px 22px; border-bottom:1px solid var(--line);
              position:sticky; top:0; background:var(--bg); z-index:20; }
  input[type=search], input[type=number], select {
      font:inherit; padding:5px 8px; border:1px solid var(--line); border-radius:5px;
      background:var(--bg); color:var(--fg); }
  input[type=search] { min-width:260px; flex:1 1 260px; }
  input[type=number] { width:72px; }
  details.facet { position:relative; }
  details.facet > summary { list-style:none; cursor:pointer; padding:5px 10px;
      border:1px solid var(--line); border-radius:5px; white-space:nowrap;
      user-select:none; font-size:13px; }
  details.facet > summary::-webkit-details-marker { display:none; }
  details.facet[open] > summary { border-color:var(--accent); color:var(--accent); }
  .panel { position:absolute; z-index:30; top:calc(100% + 4px); left:0; min-width:330px;
      max-height:340px; overflow:auto; background:var(--bg); border:1px solid var(--line);
      border-radius:6px; box-shadow:0 6px 24px rgba(0,0,0,.12); padding:6px; }
  .panel label { display:flex; gap:7px; align-items:flex-start; padding:3px 6px;
      border-radius:4px; cursor:pointer; font-size:13px; }
  .panel label:hover { background:var(--chip); }
  .panel .n { margin-left:auto; color:var(--mut); font-variant-numeric:tabular-nums;
      font-size:12px; padding-left:10px; }
  .toggle { display:flex; gap:6px; align-items:center; font-size:13px; white-space:nowrap; }
  button { font:inherit; padding:5px 10px; border:1px solid var(--line); border-radius:5px;
      background:var(--bg); color:var(--fg); cursor:pointer; }
  button:hover { border-color:var(--accent); color:var(--accent); }
  .count { padding:8px 22px; color:var(--mut); font-size:12px; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--line);
      vertical-align:top; }
  th { position:sticky; top:53px; background:var(--bg); cursor:pointer;
      font-size:12px; font-weight:600; color:var(--mut); white-space:nowrap; z-index:10; }
  th:hover { color:var(--accent); }
  th .arrow { opacity:.45; font-size:10px; }
  tbody tr:hover { background:#fafafa; }
  td.date, td.cite { white-space:nowrap; font-variant-numeric:tabular-nums; color:var(--mut); }
  td.title { cursor:pointer; }
  td.title b { font-weight:500; }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .chips { margin-top:3px; display:flex; flex-wrap:wrap; gap:3px; }
  .chip { font-size:10.5px; background:var(--chip); color:#444; border-radius:3px;
      padding:1px 5px; white-space:nowrap; }
  .chip.cap { background:#fdeef8; color:#8d1178; }
  .badge { font-size:10px; background:var(--accent); color:#fff; border-radius:3px;
      padding:1px 5px; margin-left:6px; vertical-align:1px; }
  tr.abs td { background:#fbfbfc; color:#333; font-size:13px; padding-top:0; }
  .hint { color:var(--mut); font-size:12px; padding:0 22px 26px; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="meta" id="meta"></div>
</header>

<div class="controls">
  <input type="search" id="q" placeholder="Search title, abstract, author — space-separated terms must all match">
  <label class="toggle">year <input type="number" id="y0" placeholder="from"></label>
  <label class="toggle">to <input type="number" id="y1" placeholder="to"></label>
  <details class="facet" id="f-fam"><summary>Algorithm family</summary><div class="panel"></div></details>
  <details class="facet" id="f-pde"><summary>PDE target</summary><div class="panel"></div></details>
  <details class="facet" id="f-cap"><summary>Capability axis</summary><div class="panel"></div></details>
  <label class="toggle"><input type="checkbox" id="cfd"> CFD-facing only</label>
  <label class="toggle"><input type="checkbox" id="new"> New</label>
  <button id="reset">Reset</button>
  <button id="csv">Download CSV</button>
</div>

<div class="count" id="count"></div>
<table>
  <thead><tr>
    <th data-k="d">Submitted <span class="arrow"></span></th>
    <th data-k="t">Title <span class="arrow"></span></th>
    <th data-k="a">First author <span class="arrow"></span></th>
    <th data-k="c">Cites <span class="arrow"></span></th>
  </tr></thead>
  <tbody id="tb"></tbody>
</table>
<p class="hint">Click a title to show its abstract. Tags are regex matches over title and
abstract, so they record what a paper advertises — treat them as a lower bound, not a
reading of the full text.</p>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const ROWS = P.rows, FAM = P.fam, PDE = P.pde, CAP = P.cap, META = P.meta;
const sel = {f:new Set(), p:new Set(), x:new Set()};
let sortKey = 'd', sortDir = -1;

const newCutoff = (() => {
  const d = new Date(META.generated);
  d.setDate(d.getDate() - META.new_window_days);
  return d.toISOString().slice(0, 10);
})();

document.getElementById('meta').textContent =
  `${META.n_total} papers · ${META.n_cfd} CFD-facing · ${META.n_cited} with Crossref citation counts`
  + ` · vocabulary v${META.schema_version} · updated ${META.generated}`;

// ---- facet panels -------------------------------------------------------
function buildFacet(id, names, key) {
  const panel = document.querySelector('#' + id + ' .panel');
  const counts = names.map((_, i) => ROWS.filter(r => r[key].includes(i)).length);
  names.map((name, i) => ({name, i, n: counts[i]}))
       .sort((a, b) => b.n - a.n)
       .forEach(({name, i, n}) => {
    const label = document.createElement('label');
    label.innerHTML = `<input type="checkbox" value="${i}"><span>${name}</span><span class="n">${n}</span>`;
    label.querySelector('input').addEventListener('change', e => {
      e.target.checked ? sel[key].add(i) : sel[key].delete(i);
      syncSummary(id, key, names);
      render();
    });
    panel.appendChild(label);
  });
}
function syncSummary(id, key, names) {
  const s = document.querySelector('#' + id + ' summary');
  const base = {f: 'Algorithm family', p: 'PDE target', x: 'Capability axis'}[key];
  s.textContent = sel[key].size ? `${base} (${sel[key].size})` : base;
}
buildFacet('f-fam', FAM, 'f');
buildFacet('f-pde', PDE, 'p');
buildFacet('f-cap', CAP, 'x');
document.addEventListener('click', e => {
  document.querySelectorAll('details.facet[open]').forEach(d => {
    if (!d.contains(e.target)) d.removeAttribute('open');
  });
});

// ---- filtering ----------------------------------------------------------
function current() {
  const terms = document.getElementById('q').value.toLowerCase().split(/\s+/).filter(Boolean);
  const y0 = parseInt(document.getElementById('y0').value, 10);
  const y1 = parseInt(document.getElementById('y1').value, 10);
  const cfdOnly = document.getElementById('cfd').checked;
  const newOnly = document.getElementById('new').checked;
  const hasAll = (have, want) => [...want].every(v => have.includes(v));
  return ROWS.filter(r => {
    if (cfdOnly && !r.q) return false;
    if (newOnly && !(r.s >= newCutoff)) return false;
    const yr = parseInt(r.d.slice(0, 4), 10);
    if (!isNaN(y0) && yr < y0) return false;
    if (!isNaN(y1) && yr > y1) return false;
    if (sel.f.size && !hasAll(r.f, sel.f)) return false;
    if (sel.p.size && !hasAll(r.p, sel.p)) return false;
    if (sel.x.size && !hasAll(r.x, sel.x)) return false;
    if (terms.length) {
      const hay = (r.t + ' ' + r.ab + ' ' + r.a).toLowerCase();
      if (!terms.every(t => hay.includes(t))) return false;
    }
    return true;
  }).sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (sortKey === 'c') { va = va === null ? -1 : va; vb = vb === null ? -1 : vb; }
    if (typeof va === 'string') return sortDir * va.localeCompare(vb);
    return sortDir * (va - vb);
  });
}

// ---- rendering ----------------------------------------------------------
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function render() {
  const rows = current();
  document.getElementById('count').textContent =
    `showing ${rows.length} of ${ROWS.length}` +
    (rows.length ? ` · ${rows.filter(r => r.q).length} CFD-facing in this selection` : '');
  const tb = document.getElementById('tb');
  tb.innerHTML = '';
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    const tr = document.createElement('tr');
    const chips = [...r.f.map(i => `<span class="chip">${esc(FAM[i])}</span>`),
                   ...r.x.map(i => `<span class="chip cap">${esc(CAP[i])}</span>`)].join('');
    tr.innerHTML =
      `<td class="date">${r.d}</td>` +
      `<td class="title"><b>${esc(r.t)}</b>` +
        (r.s >= newCutoff ? '<span class="badge">new</span>' : '') +
        ` <a href="https://arxiv.org/abs/${r.i}" target="_blank" rel="noopener">${r.i}</a>` +
        `<div class="chips">${chips}</div></td>` +
      `<td>${esc(r.a)}${r.na > 1 ? ' <span class="n">+' + (r.na - 1) + '</span>' : ''}</td>` +
      `<td class="cite">${r.c === null ? '—' : r.c}</td>`;
    tr.querySelector('td.title').addEventListener('click', () => {
      const next = tr.nextElementSibling;
      if (next && next.classList.contains('abs')) { next.remove(); return; }
      const ab = document.createElement('tr');
      ab.className = 'abs';
      ab.innerHTML = `<td></td><td colspan="3">${esc(r.ab)}` +
        (r.v ? `<div class="chips"><span class="chip">${esc(r.v)}</span></div>` : '') + `</td>`;
      tr.after(ab);
    });
    frag.appendChild(tr);
  }
  tb.appendChild(frag);
}

document.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
  const k = th.dataset.k;
  sortDir = (k === sortKey) ? -sortDir : (k === 't' || k === 'a' ? 1 : -1);
  sortKey = k;
  document.querySelectorAll('th .arrow').forEach(a => a.textContent = '');
  th.querySelector('.arrow').textContent = sortDir === 1 ? '\u25b2' : '\u25bc';
  render();
}));
['q','y0','y1','cfd','new'].forEach(id =>
  document.getElementById(id).addEventListener('input', render));
document.getElementById('reset').addEventListener('click', () => {
  ['q','y0','y1'].forEach(id => document.getElementById(id).value = '');
  ['cfd','new'].forEach(id => document.getElementById(id).checked = false);
  Object.values(sel).forEach(s => s.clear());
  document.querySelectorAll('.panel input').forEach(i => i.checked = false);
  syncSummary('f-fam','f',FAM); syncSummary('f-pde','p',PDE); syncSummary('f-cap','x',CAP);
  render();
});
document.getElementById('csv').addEventListener('click', () => {
  const cols = ['arxiv_id','published','title','first_author','citations_crossref','venue',
                'cfd_facing','algorithm_families','pde_targets','capability_axes','url'];
  const q = v => '"' + String(v === null || v === undefined ? '' : v).replace(/"/g, '""') + '"';
  const lines = [cols.join(',')];
  for (const r of current()) {
    lines.push([r.i, r.d, r.t, r.a, r.c === null ? '' : r.c, r.v, r.q,
                r.f.map(i => FAM[i]).join('; '), r.p.map(i => PDE[i]).join('; '),
                r.x.map(i => CAP[i]).join('; '), 'https://arxiv.org/abs/' + r.i].map(q).join(','));
  }
  const url = URL.createObjectURL(new Blob([lines.join('\n')], {type:'text/csv'}));
  const a = document.createElement('a');
  a.href = url; a.download = 'quantum_pde_filtered.csv'; a.click();
  URL.revokeObjectURL(url);
});

document.querySelector('th[data-k="d"] .arrow').textContent = '\u25bc';
render();
</script>
</body>
</html>
"""

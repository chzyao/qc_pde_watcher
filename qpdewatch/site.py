"""Generate a single self-contained HTML browser for the corpus.

No CDN, no build step, no framework: the data is inlined as JSON and the
sorting, filtering, starring and TeX rendering are vanilla JS. The page
therefore works opened straight from disk (file://) as well as from GitHub
Pages, and keeps working when today's table library has had four breaking
releases.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import favourites as favs
from .config import DOCS_DIR, Vocabularies

NEW_WINDOW_DAYS = 30


def _pack(rows: list[dict], vocab: Vocabularies, starred: dict[str, str]) -> dict:
    """Compact the rows: vocabulary terms become indices into shared name lists."""
    names = {
        "fam": list(vocab.algorithm_families),
        "pde": list(vocab.pde_targets),
        "cap": list(vocab.capability_axes),
        "doc": list(vocab.document_types),
        "set": list(vocab.problem_settings),
    }
    src_names = sorted({r["source_label"] for r in rows})
    idx = {k: {n: i for i, n in enumerate(v)} for k, v in names.items()}
    split = lambda s: [p for p in (x.strip() for x in s.split(";")) if p]
    to_idx = lambda key, s: sorted(idx[key][x] for x in split(s) if x in idx[key])

    packed = []
    for r in rows:
        packed.append({
            "i": r["uid"], "d": r["published"], "t": r["title"],
            "lbl": r["arxiv_id"] or (r["doi"] or ""),
            "u": r["url"],
            "tr": 1 if r["tier"] == "adjacent" else 0,
            "sl": r["source_label"],
            "ha": 1 if r["has_abstract"] else 0,
            "au": r["authors"], "na": r["n_authors"],
            "c": r["citations_crossref"], "v": r["venue"] or "",
            "f": to_idx("fam", r["algorithm_families"]),
            "p": to_idx("pde", r["pde_targets"]),
            "x": to_idx("cap", r["capability_axes"]),
            "dt": to_idx("doc", r["document_types"]),
            "ps": to_idx("set", r["problem_settings"]),
            "pc": r["problem_class"],
            "rv": 1 if r["is_review"] else 0,
            "q": 1 if r["cfd_facing"] else 0,
            "s": r["first_seen"], "ab": r["abstract"],
        })
    classes = sorted({r["problem_class"] for r in rows})
    return {"rows": packed, **names, "pclass": classes, "src": src_names,
            "seed": {k: v for k, v in starred.items()}}


def build(rows: list[dict], vocab: Vocabularies, outdir: Path | None = None,
          title: str = "Quantum algorithms for PDEs — literature watch",
          starred: dict[str, str] | None = None) -> Path:
    outdir = outdir or DOCS_DIR
    outdir.mkdir(parents=True, exist_ok=True)
    starred = favs.load() if starred is None else starred
    payload = _pack(rows, vocab, starred)
    payload["meta"] = {
        "generated": date.today().isoformat(),
        "n_total": len(rows),
        "n_core": sum(1 for r in rows if r["tier"] == "core"),
        "n_adjacent": sum(1 for r in rows if r["tier"] == "adjacent"),
        "n_cfd": sum(1 for r in rows if r["cfd_facing"] and r["tier"] == "core"),
        "n_cited": sum(1 for r in rows if r["citations_crossref"] is not None),
        "n_review": sum(1 for r in rows if r["is_review"]),
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
  :root { --fg:#1a1a1a; --mut:#666; --line:#e2e2e2; --accent:#B5179E; --bg:#fff;
          --chip:#f3f3f5; --star:#e8a500; }
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
  input[type=search] { min-width:230px; flex:1 1 230px; }
  input[type=number] { width:72px; }
  details.facet { position:relative; }
  details.facet > summary { list-style:none; cursor:pointer; padding:5px 10px;
      border:1px solid var(--line); border-radius:5px; white-space:nowrap;
      user-select:none; font-size:13px; }
  details.facet > summary::-webkit-details-marker { display:none; }
  details.facet[open] > summary { border-color:var(--accent); color:var(--accent); }
  .panel { position:absolute; z-index:30; top:calc(100% + 4px); left:0; min-width:340px;
      max-height:340px; overflow:auto; background:var(--bg); border:1px solid var(--line);
      border-radius:6px; box-shadow:0 6px 24px rgba(0,0,0,.12); padding:6px; }
  .panel .mode { font-size:11px; color:var(--mut); padding:3px 7px 6px; border-bottom:1px solid var(--line);
      margin-bottom:4px; }
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
  th.star, td.star { width:26px; padding-left:16px; padding-right:0; cursor:pointer;
      user-select:none; }
  td.star { color:#ccc; font-size:15px; line-height:1.2; }
  td.star.on { color:var(--star); }
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
  .chip.rev { background:#1a1a1a; color:#fff; }
  .chip.inv { background:#e8f1ff; color:#14478f; }
  .chip.adj { background:#fff4e0; color:#8a5a00; }
  .chip.noab { background:#f0f0f0; color:#888; }
  .chip.src { background:#eef6ee; color:#2a5c2a; }
  .badge { font-size:10px; background:var(--accent); color:#fff; border-radius:3px;
      padding:1px 5px; margin-left:6px; vertical-align:1px; }
  tr.abs td { background:#fbfbfc; color:#333; font-size:13px; padding-top:0; }
  tr.abs .authors { color:var(--mut); font-size:12px; margin-bottom:6px; }
  .hint { color:var(--mut); font-size:12px; padding:0 22px 26px; }
  .m { font-family:"Latin Modern Math",Georgia,"Times New Roman",serif; font-style:italic; }
  .m sup, .m sub { font-style:normal; font-size:.75em; }
  .m .op { font-style:normal; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="meta" id="meta"></div>
</header>

<div class="controls">
  <input type="search" id="q" placeholder="Search title, abstract, authors">
  <label class="toggle">year <input type="number" id="y0" placeholder="from"></label>
  <label class="toggle">to <input type="number" id="y1" placeholder="to"></label>
  <details class="facet" id="f-fam"><summary>Algorithm family</summary><div class="panel"></div></details>
  <details class="facet" id="f-pde"><summary>PDE target</summary><div class="panel"></div></details>
  <details class="facet" id="f-cap"><summary>Capability axis</summary><div class="panel"></div></details>
  <details class="facet" id="f-doc"><summary>Document type</summary><div class="panel"></div></details>
  <details class="facet" id="f-pcl"><summary>Problem</summary><div class="panel"></div></details>
  <details class="facet" id="f-src"><summary>Source</summary><div class="panel"></div></details>
  <label class="toggle" title="Papers with a quantum method but no PDE target — browsable, and excluded from every coverage statistic"><input type="checkbox" id="adj"> Adjacent</label>
  <label class="toggle"><input type="checkbox" id="cfd"> CFD</label>
  <label class="toggle"><input type="checkbox" id="rev"> Reviews</label>
  <label class="toggle"><input type="checkbox" id="fav"> &#9733; Starred</label>
  <label class="toggle"><input type="checkbox" id="new"> New</label>
  <button id="reset">Reset</button>
  <button id="export">Export favourites</button>
  <button id="csv">Download CSV</button>
</div>

<div class="count" id="count"></div>
<table>
  <thead><tr>
    <th class="star" title="Starred">&#9733;</th>
    <th data-k="d">Submitted <span class="arrow"></span></th>
    <th data-k="t">Title <span class="arrow"></span></th>
    <th data-k="au">Authors <span class="arrow"></span></th>
    <th data-k="c">Cites <span class="arrow"></span></th>
  </tr></thead>
  <tbody id="tb"></tbody>
</table>
<p class="hint">Click a title for the abstract and the full author list. Stars are kept in
this browser; use <b>Export favourites</b> and replace <code>data/favourites.txt</code> to
make them permanent. Tags are regex matches over title and abstract, so they record what a
paper advertises — a lower bound, not a reading of the full text.</p>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const ROWS = P.rows, META = P.meta;
const NAMES = {f:P.fam, p:P.pde, x:P.cap, dt:P.doc, pc:P.pclass, sl:P.src};
// AND within the analytical facets (find papers covering BOTH axes); OR within
// the categorical ones, where a paper only ever has one value.
const MODE = {f:'and', p:'and', x:'and', dt:'or', pc:'or', sl:'or'};
const sel = {f:new Set(), p:new Set(), x:new Set(), dt:new Set(), pc:new Set(), sl:new Set()};
let sortKey = 'd', sortDir = -1;

const newCutoff = (() => {
  const d = new Date(META.generated);
  d.setDate(d.getDate() - META.new_window_days);
  return d.toISOString().slice(0, 10);
})();

// ---- favourites: seeded from data/favourites.txt, then browser-local --------
const FAVKEY = 'qpdewatch:favourites';
let FAV;
try { FAV = JSON.parse(localStorage.getItem(FAVKEY)) || null; } catch (e) { FAV = null; }
if (!FAV) { FAV = Object.assign({}, P.seed); saveFav(); }
function saveFav() {
  try { localStorage.setItem(FAVKEY, JSON.stringify(FAV)); } catch (e) {}
}

document.getElementById('meta').textContent =
  `${META.n_core} core papers · ${META.n_cfd} CFD-facing · ${META.n_adjacent} adjacent `
  + `(hidden by default) · ${META.n_review} reviews · `
  + `${META.n_cited} with Crossref counts · vocabulary v${META.schema_version} · `
  + `updated ${META.generated}`;

// ---- minimal TeX rendering -------------------------------------------------
// arXiv abstracts are plain text with TeX fragments. A full engine (KaTeX) is
// ~300 KB of vendored assets; this covers the subset that actually shows up in
// this corpus — exponents, subscripts, operators, Greek — and leaves anything
// it does not know as legible text rather than mangling it.
const SYM = {
  times:'\u00d7', cdot:'\u00b7', pm:'\u00b1', mp:'\u2213', approx:'\u2248',
  sim:'\u223c', simeq:'\u2243', equiv:'\u2261', neq:'\u2260', ne:'\u2260',
  leq:'\u2264', le:'\u2264', geq:'\u2265', ge:'\u2265', ll:'\u226a', gg:'\u226b',
  to:'\u2192', rightarrow:'\u2192', leftarrow:'\u2190', Rightarrow:'\u21d2',
  mapsto:'\u21a6', propto:'\u221d', in:'\u2208', notin:'\u2209', subset:'\u2282',
  subseteq:'\u2286', cup:'\u222a', cap:'\u2229', infty:'\u221e', partial:'\u2202',
  nabla:'\u2207', sum:'\u2211', int:'\u222b', oint:'\u222e', prod:'\u220f',
  sqrt:'\u221a', otimes:'\u2297', oplus:'\u2295', dagger:'\u2020', hbar:'\u210f',
  ell:'\u2113', langle:'\u27e8', rangle:'\u27e9', lvert:'|', rvert:'|',
  lVert:'\u2016', rVert:'\u2016', ldots:'\u2026', dots:'\u2026', cdots:'\u22ef',
  forall:'\u2200', exists:'\u2203', emptyset:'\u2205', star:'\u22c6',
  prime:'\u2032', circ:'\u2218', deg:'\u00b0', perp:'\u22a5', angle:'\u2220',
  alpha:'\u03b1', beta:'\u03b2', gamma:'\u03b3', delta:'\u03b4', epsilon:'\u03b5',
  varepsilon:'\u03b5', zeta:'\u03b6', eta:'\u03b7', theta:'\u03b8', vartheta:'\u03d1',
  iota:'\u03b9', kappa:'\u03ba', lambda:'\u03bb', mu:'\u03bc', nu:'\u03bd',
  xi:'\u03be', pi:'\u03c0', rho:'\u03c1', sigma:'\u03c3', tau:'\u03c4',
  upsilon:'\u03c5', phi:'\u03c6', varphi:'\u03c6', chi:'\u03c7', psi:'\u03c8',
  omega:'\u03c9', Gamma:'\u0393', Delta:'\u0394', Theta:'\u0398', Lambda:'\u039b',
  Xi:'\u039e', Pi:'\u03a0', Sigma:'\u03a3', Upsilon:'\u03a5', Phi:'\u03a6',
  Psi:'\u03a8', Omega:'\u03a9'
};
const ROMAN = /^(log|ln|exp|sin|cos|tan|sinh|cosh|tanh|min|max|arg|det|dim|lim|sup|inf|mod|Re|Im|tr|rank|diag|mathcal|mathrm|mathbf|mathbb|text|textrm|operatorname|left|right|big|Big|bigg|Bigg|displaystyle|quad|qquad|nonumber|label)$/;

// Combining accents: \vec{u} becomes u followed by U+20D7, which renders as a
// single glyph in any font with decent combining-mark support.
const ACCENT = {vec:'\u20d7', widetilde:'\u0303', tilde:'\u0303', widehat:'\u0302',
                hat:'\u0302', bar:'\u0304', overline:'\u0304', dot:'\u0307',
                ddot:'\u0308', check:'\u030c', acute:'\u0301', grave:'\u0300'};

function math(src) {
  let s = src;
  s = s.replace(/\\(?:left|right|displaystyle|nonumber|rm|it|bf|!|,|;|:|\s)/g, ' ');
  s = s.replace(/\\(vec|widetilde|tilde|widehat|hat|bar|overline|dot|ddot|check|acute|grave)\s*\{([^{}]*)\}/g,
                (m0, acc, inner) => inner + ACCENT[acc]);
  s = s.replace(/\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, '($1)/($2)');
  s = s.replace(/\\sqrt\s*\{([^{}]*)\}/g, '\u221a($1)');
  s = s.replace(/\\(?:lvert|rvert|vert|mid)\b/g, '|');
  s = s.replace(/\\\|/g, '\u2016');
  s = s.replace(/\\(?:mathcal|mathrm|mathbf|mathbb|text|textrm|operatorname)\s*\{([^{}]*)\}/g,
                '<span class="op">$1</span>');
  s = s.replace(/\\([A-Za-z]+)/g, (m0, w) => {
    if (SYM[w]) return SYM[w];
    if (ROMAN.test(w)) return '<span class="op">' + w + '</span>';
    return w;
  });
  // exponents and subscripts, innermost braces first
  for (let k = 0; k < 4; k++) {
    s = s.replace(/\^\s*\{([^{}]*)\}/g, '<sup>$1</sup>')
         .replace(/_\s*\{([^{}]*)\}/g, '<sub>$1</sub>')
         .replace(/\^(-?[A-Za-z0-9+\u2212])/g, '<sup>$1</sup>')
         .replace(/_(-?[A-Za-z0-9+\u2212])/g, '<sub>$1</sub>');
  }
  s = s.replace(/[{}]/g, '').replace(/\s{2,}/g, ' ');
  return '<span class="m">' + s + '</span>';
}

const esc = s => String(s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function tex(raw) {
  // Escape first so the source text can never inject markup; the math() output
  // is the only HTML we add, and it is built from already-escaped input.
  let s = esc(raw);
  // Text-mode macros first: these appear in abstracts outside any $...$.
  s = s.replace(/\\(?:begin|end)\s*\{[^{}]*\}/g, '');
  s = s.replace(/\\(?:cite|citep|citet|ref|eqref|label|footnote)\s*\{[^{}]*\}/g, '');
  s = s.replace(/\\(?:emph|textit|textsl)\s*\{([^{}]*)\}/g, '<em>$1</em>');
  s = s.replace(/\\(?:textbf|bf)\s*\{([^{}]*)\}/g, '<b>$1</b>');
  s = s.replace(/\\(?:texttt|textsc|textrm|text|mathrm|mathbf|mathbb|mathcal)\s*\{([^{}]*)\}/g, '$1');
  s = s.replace(/\\url\s*\{([^{}]*)\}/g, '$1');
  // Old-style font groups: {\it foo}, {\em foo}, {\bf foo}
  s = s.replace(/\{\\(?:it|em|sl)\s+([^{}]*)\}/g, '<em>$1</em>');
  s = s.replace(/\{\\(?:bf)\s+([^{}]*)\}/g, '<b>$1</b>');
  s = s.replace(/\{\\(?:rm|tt|sc)\s+([^{}]*)\}/g, '$1');
  // Then math segments.
  s = s.replace(/\$\$([\s\S]+?)\$\$/g, (m0, inner) => math(inner));
  s = s.replace(/\\\(([\s\S]+?)\\\)/g, (m0, inner) => math(inner));
  s = s.replace(/\\\[([\s\S]+?)\\\]/g, (m0, inner) => math(inner));
  s = s.replace(/\$([^$]+?)\$/g, (m0, inner) => math(inner));
  // Symbol macros also turn up outside any $...$. Only names in SYM are touched,
  // and the HTML produced above contains no backslashes, so this cannot corrupt it.
  s = s.replace(/\\([A-Za-z]+)/g, (m0, w) => SYM[w] !== undefined ? SYM[w] : m0);
  s = s.replace(/\\([%&_#$ ])/g, '$1');
  return s;
}

// ---- facet panels ----------------------------------------------------------
function buildFacet(id, key, names, counter) {
  const panel = document.querySelector('#' + id + ' .panel');
  const mode = document.createElement('div');
  mode.className = 'mode';
  mode.textContent = MODE[key] === 'and'
    ? 'Selecting several requires a paper to have all of them'
    : 'Selecting several matches any of them';
  panel.appendChild(mode);
  names.map((name, i) => ({name, i, n: counter(i)}))
       .sort((a, b) => b.n - a.n)
       .forEach(({name, i, n}) => {
    const label = document.createElement('label');
    label.innerHTML = `<input type="checkbox" value="${i}"><span>${esc(name)}</span>` +
                      `<span class="n">${n}</span>`;
    label.querySelector('input').addEventListener('change', e => {
      const v = (key === 'pc' || key === 'sl') ? name : i;
      e.target.checked ? sel[key].add(v) : sel[key].delete(v);
      syncSummary(id, key);
      render();
    });
    panel.appendChild(label);
  });
}
const BASE = {f:'Algorithm family', p:'PDE target', x:'Capability axis',
              dt:'Document type', pc:'Problem', sl:'Source'};
function syncSummary(id, key) {
  const s = document.querySelector('#' + id + ' summary');
  s.textContent = sel[key].size ? `${BASE[key]} (${sel[key].size})` : BASE[key];
}
buildFacet('f-fam', 'f',  NAMES.f,  i => ROWS.filter(r => r.f.includes(i)).length);
buildFacet('f-pde', 'p',  NAMES.p,  i => ROWS.filter(r => r.p.includes(i)).length);
buildFacet('f-cap', 'x',  NAMES.x,  i => ROWS.filter(r => r.x.includes(i)).length);
buildFacet('f-doc', 'dt', NAMES.dt, i => ROWS.filter(r => r.dt.includes(i)).length);
buildFacet('f-pcl', 'pc', NAMES.pc, i => ROWS.filter(r => r.pc === NAMES.pc[i]).length);
buildFacet('f-src', 'sl', NAMES.sl, i => ROWS.filter(r => r.sl === NAMES.sl[i]).length);
document.addEventListener('click', e => {
  document.querySelectorAll('details.facet[open]').forEach(d => {
    if (!d.contains(e.target)) d.removeAttribute('open');
  });
});

// ---- filtering -------------------------------------------------------------
function current() {
  const terms = document.getElementById('q').value.toLowerCase().split(/\s+/).filter(Boolean);
  const y0 = parseInt(document.getElementById('y0').value, 10);
  const y1 = parseInt(document.getElementById('y1').value, 10);
  const withAdj = document.getElementById('adj').checked;
  const cfdOnly = document.getElementById('cfd').checked;
  const revOnly = document.getElementById('rev').checked;
  const favOnly = document.getElementById('fav').checked;
  const newOnly = document.getElementById('new').checked;
  const all = (have, want) => [...want].every(v => have.includes(v));
  const any = (have, want) => [...want].some(v => have.includes(v));
  const match = (have, key) => !sel[key].size ||
        (MODE[key] === 'and' ? all(have, sel[key]) : any(have, sel[key]));
  return ROWS.filter(r => {
    if (!withAdj && r.tr) return false;
    if (cfdOnly && !r.q) return false;
    if (revOnly && !r.rv) return false;
    if (favOnly && !(r.i in FAV)) return false;
    if (newOnly && !(r.s >= newCutoff)) return false;
    const yr = parseInt(r.d.slice(0, 4), 10);
    if (!isNaN(y0) && yr < y0) return false;
    if (!isNaN(y1) && yr > y1) return false;
    if (!match(r.f, 'f') || !match(r.p, 'p') || !match(r.x, 'x') || !match(r.dt, 'dt'))
      return false;
    if (sel.pc.size && !sel.pc.has(r.pc)) return false;
    if (sel.sl.size && !sel.sl.has(r.sl)) return false;
    if (terms.length) {
      const hay = (r.t + ' ' + r.ab + ' ' + r.au).toLowerCase();
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

// ---- rendering -------------------------------------------------------------
function shortAuthors(r) {
  const list = r.au.split('; ');
  if (list.length <= 3) return esc(list.join(', '));
  return esc(list.slice(0, 2).join(', ')) +
         ` <span class="n">+${list.length - 2} more</span>`;
}
function render() {
  const rows = current();
  document.getElementById('count').textContent =
    `showing ${rows.length} of ${ROWS.length}` +
    (rows.length ? ` · ${rows.filter(r => r.q).length} CFD-facing · ` +
                   `${rows.filter(r => r.i in FAV).length} starred` : '');
  const tb = document.getElementById('tb');
  tb.innerHTML = '';
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    const tr = document.createElement('tr');
    const chips = [
      r.rv ? '<span class="chip rev">review</span>' : '',
      r.tr ? '<span class="chip adj">adjacent</span>' : '',
      `<span class="chip src">${esc(r.sl)}</span>`,
      r.ha ? '' : '<span class="chip noab">no abstract</span>',
      r.pc !== 'Forward (assumed)' ? `<span class="chip inv">${esc(r.pc)}</span>` : '',
      ...r.f.map(i => `<span class="chip">${esc(NAMES.f[i])}</span>`),
      ...r.x.map(i => `<span class="chip cap">${esc(NAMES.x[i])}</span>`)
    ].join('');
    tr.innerHTML =
      `<td class="star${r.i in FAV ? ' on' : ''}">${r.i in FAV ? '\u2605' : '\u2606'}</td>` +
      `<td class="date">${r.d}</td>` +
      `<td class="title"><b>${tex(r.t)}</b>` +
        (r.s >= newCutoff ? '<span class="badge">new</span>' : '') +
        ` <a href="${r.u}" target="_blank" rel="noopener">${esc(r.lbl)}</a>` +
        `<div class="chips">${chips}</div></td>` +
      `<td>${shortAuthors(r)}</td>` +
      `<td class="cite">${r.c === null ? '\u2014' : r.c}</td>`;
    tr.querySelector('td.star').addEventListener('click', ev => {
      ev.stopPropagation();
      if (r.i in FAV) delete FAV[r.i]; else FAV[r.i] = '';
      saveFav();
      render();
    });
    tr.querySelector('td.title').addEventListener('click', () => {
      const next = tr.nextElementSibling;
      if (next && next.classList.contains('abs')) { next.remove(); return; }
      const ab = document.createElement('tr');
      ab.className = 'abs';
      ab.innerHTML = `<td></td><td></td><td colspan="3">` +
        `<div class="authors">${esc(r.au.split('; ').join(', '))}</div>` +
        tex(r.ab) +
        (r.v ? `<div class="chips"><span class="chip">${esc(r.v)}</span></div>` : '') +
        `</td>`;
      tr.after(ab);
    });
    frag.appendChild(tr);
  }
  tb.appendChild(frag);
}

document.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
  const k = th.dataset.k;
  sortDir = (k === sortKey) ? -sortDir : (k === 't' || k === 'au' ? 1 : -1);
  sortKey = k;
  document.querySelectorAll('th .arrow').forEach(a => a.textContent = '');
  th.querySelector('.arrow').textContent = sortDir === 1 ? '\u25b2' : '\u25bc';
  render();
}));
['q','y0','y1','adj','cfd','rev','fav','new'].forEach(id =>
  document.getElementById(id).addEventListener('input', render));
document.getElementById('reset').addEventListener('click', () => {
  ['q','y0','y1'].forEach(id => document.getElementById(id).value = '');
  ['adj','cfd','rev','fav','new'].forEach(id => document.getElementById(id).checked = false);
  Object.values(sel).forEach(s => s.clear());
  document.querySelectorAll('.panel input').forEach(i => i.checked = false);
  Object.keys(BASE).forEach(k => syncSummary({f:'f-fam',p:'f-pde',x:'f-cap',
                                              dt:'f-doc',pc:'f-pcl',sl:'f-src'}[k], k));
  render();
});

function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], {type: type}));
  const a = document.createElement('a');
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}
document.getElementById('export').addEventListener('click', () => {
  const byId = Object.fromEntries(ROWS.map(r => [r.i, r]));
  const lines = [
    '# Starred papers \u2014 one arXiv ID per line, optional note after \'#\'.',
    '# This file is the durable record; the HTML viewer seeds its stars from it.',
    '# After starring in the browser, use "Export favourites" and replace this file.',
    ''];
  for (const id of Object.keys(FAV).sort()) {
    const note = FAV[id] || (byId[id] ? byId[id].t.slice(0, 60) : '');
    lines.push(note ? `${id}  # ${note}` : id);
  }
  download('favourites.txt', lines.join('\n') + '\n', 'text/plain');
});
document.getElementById('csv').addEventListener('click', () => {
  const cols = ['uid','published','title','authors','citations_crossref','venue',
                'tier','source_label','has_abstract','cfd_facing','is_review','problem_class',
                'algorithm_families','pde_targets','capability_axes','starred','url'];
  const q = v => '"' + String(v === null || v === undefined ? '' : v).replace(/"/g, '""') + '"';
  const lines = [cols.join(',')];
  for (const r of current()) {
    lines.push([r.i, r.d, r.t, r.au, r.c === null ? '' : r.c, r.v,
                r.tr ? 'adjacent' : 'core', r.sl, r.ha, r.q, r.rv, r.pc,
                r.f.map(i => NAMES.f[i]).join('; '),
                r.p.map(i => NAMES.p[i]).join('; '),
                r.x.map(i => NAMES.x[i]).join('; '),
                (r.i in FAV) ? 1 : 0,
                r.u].map(q).join(','));
  }
  download('quantum_pde_filtered.csv', lines.join('\n'), 'text/csv');
});

document.querySelector('th[data-k="d"] .arrow').textContent = '\u25bc';
render();
</script>
</body>
</html>
"""

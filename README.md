# quantum-pde-watch

A tracked, weekly-updating corpus of the literature on **quantum algorithms for solving
classical PDEs**, with a CFD emphasis. Harvests arXiv, enriches with Crossref citation
counts, tags every paper against controlled vocabularies of algorithm families, PDE targets
and capability axes, and publishes a sortable/filterable HTML table plus the gap-map
coverage figures.

Browse the current corpus: `docs/index.html` (open it from disk, or serve it with GitHub
Pages). The flat exports live in `data/`.

---

## Quickstart

```bash
git clone <your-fork> && cd quantum-pde-watch
python -m venv .venv && source .venv/bin/activate     # Python >= 3.11 (tomllib)
pip install -e ".[figures]"                          # or: pip install -r requirements.txt

qpdewatch stats                 # what is on file  (same as: python -m qpdewatch stats)
python -m qpdewatch build       # re-tag and regenerate every output, no network
python -m qpdewatch update      # the weekly job: harvest, enrich, build
```

`build` is offline and idempotent — run it freely after editing a vocabulary.
`update` touches the network and is what the GitHub Action runs.

---

## What it produces

| Path | What it is |
|---|---|
| `data/corpus.jsonl` | The corpus itself, one JSON record per line, sorted by submission date. The only file that accumulates state. |
| `data/corpus.csv` | Flat export: one row per screened paper with all tags, citations and the abstract. |
| `data/coverage_matrix_counts.csv` | Algorithm family × capability axis, paper counts, CFD-facing subset. |
| `data/coverage_matrix_fraction.csv` | Same matrix as fraction of each family's papers. |
| `data/gap_scorecard.csv` | Per-axis coverage before/from 2024 — the "is the gap closing?" table. |
| `data/state.json` | Last harvest date and record count. Drives the incremental cutoff. |
| `data/favourites.txt` | Starred papers — one arXiv ID per line, optional note after `#`. Committed, so stars are portable and show up in git. |
| `docs/index.html` | Self-contained browser: search, facet filters, column sorting, CSV export of the current selection. |
| `docs/coverage_matrix.png`, `docs/gap_trajectory.png` | The two gap-map figures. |

`corpus.jsonl` is deliberately newline-delimited JSON rather than a database: each weekly
commit then shows exactly which papers arrived, and `git log -p data/corpus.jsonl` is a
readable history of the field.

---

## How it works

**1. Harvest** (`qpdewatch/harvest.py`). Runs every query in `config/queries.toml` against
the arXiv API, newest-first, two pages of 200 per query, 3 s between requests (arXiv's
stated rate limit — do not lower it). Records are de-duplicated on arXiv ID and remember
which queries matched them.

*Incremental by default.* `data/state.json` records the last harvest date; the next run
only pages back to that date minus a 10-day overlap, then stops. A weekly run therefore
costs about a minute instead of re-downloading everything. `--full` ignores the cutoff.

**2. Enrich** (`qpdewatch/enrich.py`). Looks each title up in Crossref and keeps the match
when title similarity exceeds 0.90. Most records are preprint-only and never match; a miss
is cached with a `checked` date so the same hopeless titles are not re-queried weekly.
Matched records are refreshed every `--refresh-days` (default 90) so counts stay current.
Capped at `--max-requests` per run (default 400) to keep the Action inside its time budget;
leftovers are picked up next week. Set the `CROSSREF_MAILTO` environment variable to join
Crossref's polite pool.

**3. Screen and tag** (`qpdewatch/tag.py`). A record is kept if its title+abstract matches
both `quantum_terms` and `pde_terms` and its title does not match `hard_exclude`. Surviving
records are tagged against three vocabularies, and marked `cfd_facing` if any of their PDE
targets is in `cfd_pde_targets`.

Tags are **derived, never stored**: every `build` recomputes them from the current
vocabularies, so editing `config/vocabularies.toml` re-tags the whole corpus rather than
only new arrivals.

**4. Build** (`qpdewatch/coverage.py`, `qpdewatch/site.py`). Writes the flat exports, the
coverage matrices, the scorecard, the two figures and the HTML browser.

---

## The viewer

`docs/index.html` is one self-contained file — data inlined, vanilla JS, no CDN — so it
works from `file://` and from Pages alike.

- **Search** over title, abstract and all authors; space-separated terms must all match.
- **Facets** for algorithm family, PDE target, capability axis, document type and problem
  class. The three analytical facets use AND within the facet (find papers covering *both*
  readout and geometry); the two categorical ones use OR. Each panel says which.
- **Quick toggles** for CFD-facing, reviews, starred and new-in-30-days.
- **Starring.** Click the star in the first column. Stars live in browser localStorage,
  seeded on first visit from `data/favourites.txt`. Press **Export favourites**, replace
  `data/favourites.txt` with the download and commit — now the star is permanent, survives
  a cache clear, and is there on your other machines. The viewer is a static page, so this
  file-plus-localStorage split is what makes starring durable without a backend.
- **TeX rendering.** arXiv abstracts are plain text containing TeX, so `$3.7\times10^{-12}$`
  used to display raw. `qpdewatch/site.py` ships a small renderer covering the subset that
  actually occurs in this corpus: exponents and subscripts, fractions, roots, accents
  (`\vec`, `\bar`, `\widetilde`), Greek, operators and relations, text macros (`\emph`,
  `\cite`, `\text`), and old-style `{\it …}` groups. Across all 733 titles and abstracts it
  leaves three unrecognised tokens, all of which are literal text rather than TeX. Anything
  it does not know is left as legible source rather than mangled. A full engine (KaTeX,
  MathJax) would be exact but means ~300 KB of vendored assets and breaks the
  single-file property — worth doing only if the simple renderer starts to grate.
- **Download CSV** exports whatever is currently filtered, including a `starred` column.

## Editing the vocabularies

Everything that defines the map lives in `config/vocabularies.toml` as case-insensitive
Python regexes in TOML literal strings (single-quoted, so backslashes need no escaping):

```toml
[algorithm_families]
"LCU / LCHS" = '(linear combination of unitaries|\bLCU\b|\bLCHS\b|linear combination of Hamiltonian simulation)'
```

Add a family, split an axis, tighten a pattern, then `python -m qpdewatch build` and the
whole corpus is re-tagged. Bump `schema_version` when you change semantics — it is a quoted
string on a 0.x series (`"0.1"`, `"0.2"`, `"0.3"`) and stays below 1.0 while the vocabulary
is still moving; quoting matters so `"0.10"` sorts after `"0.9"`. It is stamped
into the HTML header so a published table says which vocabulary produced it.

Adding a query to `config/queries.toml` costs one HTTP round trip per run. If a new query
should back-fill history, run `python -m qpdewatch harvest --full` once.

### Document type and problem setting (v0.3)

Two vocabularies classify the paper rather than its subject.

`[document_types]` detects reviews, surveys, perspectives, tutorials, benchmark studies and
software releases. These patterns are deliberately **precision-first**: they fire on
self-description ("this survey", "we present a comprehensive review") or on title position,
never on a bare "we review", which appears in ordinary research intros constantly. Tuning it
the loose way flagged 16 papers of which 3 were plainly not reviews; the current rules flag
10, all genuine. A missed review is a minor annoyance, a research paper mislabelled as a
survey is misleading. `is_review` in the CSV is the narrow Review/survey flag only — use the
document-type facet if you also want perspectives and tutorials.

`[problem_settings]` detects inverse problems and data assimilation, PDE-constrained
optimisation and control, and uncertainty quantification. The derived `problem_class` column
collapses these to one value with that precedence, falling back to **"Forward (assumed)"**.
Read that label literally: forward and inverse are not symmetric in how papers describe
themselves — inverse, control and UQ work announces itself, while a forward solver rarely
says so — therefore "Forward (assumed)" means *no inverse-type signal was found*, which is
an absence of evidence rather than a positive detection.

### Known vocabulary caveats

- **Tags measure what a paper advertises.** They are regex matches over title and abstract,
  not a reading of the full text. A paper can treat boundary conditions carefully in §4
  without saying so in the abstract. Axis totals are therefore **lower bounds**; column
  marginals are robust, individual cells are approximate.
- **v0.3 splits quantum machine learning out of the variational family.** It had been
  folded into `Variational / VQA / quantum ML`, which conflated two different things: a
  variational PDE solver optimises circuit parameters against a residual, while a QML
  surrogate learns a map from data. `Quantum machine learning / surrogates` now covers
  QPINNs, quantum neural operators, reservoir computing, kernels, generative models and
  reinforcement learning, and resolves 60 papers — 30 of which are *not* variational, so
  they were previously filed under a family name that misdescribed them. Papers that are
  both keep both tags.
- `v0.2` fixes two defects found in the first pass: there was no
  Lindbladian/open-system family (the density-matrix route to non-unitary dynamics was
  invisible, split across Schrödingerisation and LCU/LCHS), and the Boltzmann PDE target
  required the literal phrase "Boltzmann equation", so bare "lattice Boltzmann" did not
  match and 23 of 64 lattice-Boltzmann papers were wrongly tagged as not CFD-facing.
  Numbers produced under different vocabulary versions are not directly comparable. Concretely: the gap-map
  report was written against 700 screened / 201 CFD-facing papers under v0.1; the seeded
  corpus here is 733 screened / 225 CFD-facing under v0.2 and later, from 1,392 harvested records.
  The increase comes from the lattice-Boltzmann fix (quantum lattice Boltzmann goes from
  43 to 66 CFD-facing papers, overtaking the variational family as the largest) and from
  three added Lindbladian/open-system queries. `docs/gap_map.md` reproduces the report as
  written; its figures and percentages are the v1 numbers, while `docs/*.png` are
  regenerated under the current vocabulary and will differ.
- Some classical Koopman and tensor-train work matches the quantum screen. That is
  deliberate — quantum-inspired tensor-network solvers are the moving classical baseline —
  but it means family counts are not purely quantum.

---

## Publishing the table

**GitHub Pages.** Settings → Pages → *Deploy from a branch* → branch `main`, folder
`/docs`. The weekly Action commits a regenerated `docs/index.html`, so the published page
tracks the corpus with no extra step. Nothing is fetched at runtime and there is no CDN, so
the page also works opened directly from disk.

**If you outgrow a single page**, two good options, in order of how much they ask of you:

- **[Datasette](https://datasette.io).** `pip install datasette`, convert the CSV to SQLite
  with `sqlite-utils insert corpus.db papers data/corpus.csv --csv`, then
  `datasette publish` or run it locally. You get faceted search, saved SQL queries, a JSON
  API and full-text search over abstracts for roughly zero code. This is the natural next
  step once you want to *ask questions of* the corpus rather than browse it.
- **Observable Framework or Quarto**, if you want the gap-map narrative and the table in
  one document that rebuilds in CI. More machinery, nicer prose-plus-data output.

A third option worth knowing about: keep the corpus as it is and point a notebook at
`data/corpus.csv`. For ad-hoc analysis that beats any UI.

---

## The weekly job

`.github/workflows/weekly.yml` runs Mondays at 06:17 UTC and on manual dispatch. It
harvests, enriches, rebuilds, writes `python -m qpdewatch stats` into the run summary, and
commits `data/` and `docs/` only if something changed. The commit message carries the
number of corpus lines added, so the repo history doubles as a weekly digest.

To get a notification instead of (or besides) a commit, add a step that posts the diff of
`data/corpus.jsonl` — new lines are new papers, and the file is sorted by submission date,
so `git diff HEAD~1 -- data/corpus.jsonl | grep '^+' | jq -r .title` is a usable digest.

Optional: set a repository variable `CROSSREF_MAILTO` to your address for Crossref's
polite pool.

---

## Provenance

The seed corpus was assembled from 31 arXiv queries, screened to the records matching both
a quantum-method term and a differential-equation term, and tagged with the vocabularies in
`config/vocabularies.toml`. The screen is deterministic — no language model is involved at
any stage, so the pipeline is fully reproducible from the config. The three tagging
vocabularies were verified to reproduce the original hand-checked corpus exactly on all 700
rows before being committed here.

Citation counts come from Crossref and cover only papers with a published version; in a
field this recent that is roughly half the corpus, and a zero means "no Crossref match",
not "uncited". Treat the counts as a floor.

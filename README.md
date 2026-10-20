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
qpdewatch update                # the weekly job: harvest, discover, enrich, build
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

## Sources and tiers

**Two sources.** arXiv is harvested from `config/queries.toml`; Crossref is searched from
`config/queries_crossref.toml` to catch work that was never preprinted. Records are matched
on DOI, then normalised title, then fuzzily above 0.93 similarity — a Crossref hit that
matches an existing arXiv paper contributes its DOI, venue and citation count to that record
instead of creating a second row. The arXiv record stays canonical: it has the full
abstract, the author list and the version history.

Crossref's `query.bibliographic` is a fuzzy relevance search that returns its full quota
however thin the match, so Crossref records failing the *quantum* half of the screen are
dropped at ingest rather than stored and re-screened forever. The arXiv harvest is kept
whole, because those queries were targeted to begin with and the stored feed is the
reproducible record of what they returned.

`config/seed_dois.toml` is the escape hatch: paste a DOI and `discover` fetches it whatever
the queries return. Seeds bypass the ingest screen because you asked for them on purpose.

**Every published record has an abstract.** A paper you cannot read is a paper you cannot
judge, and its tags would be title-only guesses, so `build` withholds any screened-in record
whose abstract is still missing. Withheld is not deleted: the record stays in
`data/corpus.jsonl` and `discover` keeps retrying it against arXiv by title match, so it
appears as soon as the text is found. `qpdewatch stats` and `build` both report the pending
count. `build --include-abstractless` overrides this if you ever need the full list.

**Source labels.** Every record carries a `source_label` — `arXiv (preprint only)`,
`Academia.edu`, `APS`, `Elsevier`, `IOP`, `Springer`, `Nature Portfolio`, `AIP`, `IEEE`,
`MDPI` and so on — driven by ordered regex rules in `config/sources.toml` and exposed as a
facet in the viewer. The rules match against `"<publisher> | <venue>"`, first match wins, so
specific journals go above the publishers that own them. A record with no venue at all is
labelled a preprint: in practice "arXiv" is most useful as a tag meaning *not published
anywhere yet*, since a paper on arXiv **and** in Physical Review is more usefully filed
under APS.

**Two tiers.**

| Tier | Meaning | In the statistics? |
|---|---|---|
| `core` | A quantum method **and** a differential-equation target. | Yes |
| `adjacent` | A quantum method but no PDE target — QML for chemistry, quantum simulation, general quantum-computing surveys. | **No** |

The viewer hides the adjacent tier behind a toggle. Coverage percentages are computed over
core papers **that have an abstract**, via `coverage.statistical_rows`. Both exclusions
matter: tags are regex over title plus abstract, so counting an abstract-less record as "a
paper that fails to address axis X" would push every percentage down for a bibliographic
reason rather than a scientific one. Crossref supplies an abstract for only about a third of
its records; `discover` backfills the rest from arXiv by title match, and whatever is still
missing is flagged `has_abstract = false` and held out.

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
- **Starring.** Click the star in the first column. `data/favourites.txt` is authoritative
  and localStorage is the working copy. Press **Export favourites**, replace
  `data/favourites.txt` with the download and commit — now the star is permanent, survives
  a cache clear, and is there on your other machines. The viewer is a static page, so this
  file-plus-localStorage split is what makes starring durable without a backend.

  The browser also remembers *which* seed it adopted, so **when the committed file changes
  the file wins** and the working copy is replaced. That is what makes editing or emptying
  `data/favourites.txt` and redeploying actually take effect; without it the file was
  write-only after a browser's first visit. The cost is the other half of the contract:
  stars you added in the browser and never exported are dropped the next time the file
  changes. To clear all stars, empty the file, commit, and redeploy — or, for an immediate
  local effect without a deploy, run
  `localStorage.removeItem('qpdewatch:favourites')` in the browser console.
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
is still moving. Quoting matters because an unquoted `0.10` is parsed as a float equal to
`0.1`, silently colliding the tenth revision with the first. Note that string ordering is
*not* version ordering either — `"0.10" < "0.9"` lexically — so compare versions by reading
the changelog, not by sorting. It is stamped
into the HTML header so a published table says which vocabulary produced it.

Adding a query to `config/queries.toml` costs one HTTP round trip per run. If a new query
should back-fill history, run `python -m qpdewatch harvest --full` once.

### Document type and problem setting (v0.3)

Two vocabularies classify the paper rather than its subject.

`[document_types]` detects reviews, surveys, perspectives, tutorials, benchmark studies and
software releases. These patterns are deliberately **precision-first**: they fire on
self-description ("this survey", "we present a comprehensive review") or on title position,
never on a bare "we review", which appears in ordinary research intros constantly. The loose
version flagged 16 papers; tightening removed **6** of them and the current rules flag 10,
all genuine. Of the 6 removed, 3 were plainly not reviews (a noise-gate paper, a lattice-gas
algorithm paper, and a terse MHD title whose abstract merely opened "We review") and 3 are
better described as something else — they are now picked up by `Perspective / roadmap`,
`Tutorial / pedagogical` and `Benchmark / comparative study` respectively, so they are still
findable, just not as reviews. A missed review is a minor annoyance, a research paper mislabelled as a
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

## Maintenance

Written for the case that actually matters: you come back after four months and
need to change something without breaking a corpus you can no longer re-derive.

**What is source and what is derived.** `data/corpus.jsonl`, `data/favourites.txt`,
`data/state.json`, `config/` and `qpdewatch/` are the source of truth and are tracked.
Everything else under `data/` and `docs/` is derived, gitignored, and rebuilt by
`qpdewatch build` in seconds. If you ever see a derived file in a diff, something has gone
wrong with `.gitignore`. `docs/gap_map.md` is prose, so it *is* tracked.

**Before changing a regex, run the tests.** `pytest` (31 tests, offline, under a second).
They exist because tagging fails silently: a pattern that stops matching changes every
percentage in the gap map and nothing in the output looks broken. The suite pins the
behaviours that were expensive to get right — the review-detection false positives, the
`Forward (assumed)` fallback, Crossref de-duplication, and the rule that adjacent and
abstract-less papers never enter a statistic. Vocabulary v0.4 exists because a test caught
that five algorithm families were invisible to the screen.

**After changing a vocabulary**, bump `schema_version`, note it in `CHANGELOG.md` with the
before/after counts, and remember that figures and percentages from different versions are
not comparable.

**`qpdewatch check`** validates the stored corpus: required fields, ISO dates, keys matching
their records, and records claiming the same DOI or title. Errors fail CI; duplicates are
warnings, because which copy to keep is your call. It runs in CI and in the weekly job.

**If the weekly job goes quiet.** Scheduled workflows are disabled after 60 days of
repository inactivity (GitHub emails first; `workflow_dispatch` re-enables). The job now
fails loudly rather than silently collecting nothing, so a red run means "arXiv refused",
not "no new papers" — and `state.json` does not advance on a failed run, so the missed
window is retried in full next time.

**Rate limits.** arXiv allows one request per three seconds and answers an over-quota
client with `429 Rate exceeded`. `qpdewatch harvest` treats that as a sustained block:
it backs off, aborts, and leaves `state.json` untouched. Do not "fix" a 429 by retrying
harder — every attempt counts against the same quota. If you are developing against the
harvester, work from the committed corpus with `qpdewatch build` instead, which needs no
network at all.

**Reproducing the corpus from scratch** costs one `qpdewatch harvest --full` plus
`qpdewatch discover`, roughly 10 minutes of mostly waiting. Nothing in the pipeline needs
an API key, and no language model is involved at any stage.

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

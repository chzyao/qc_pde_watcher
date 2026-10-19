# Changelog

Dated entries, newest first. The thing most worth recording is **why a number
changed**, because corpus counts move for both scientific and bookkeeping
reasons and a year later you will not remember which was which.

Vocabulary versions (`config/vocabularies.toml` → `schema_version`) stay on a
0.x series while the tagging keeps moving. Counts produced under different
vocabulary versions are not comparable.

## Unreleased

### Changed
- **An abstract is now required for publication.** Screened-in records without
  one are withheld from `corpus.csv` and the viewer rather than shown as stubs
  with title-only tags. They stay in `corpus.jsonl` and the backfill keeps
  retrying, so this is a display decision, not deletion. This supersedes the
  earlier approach of publishing them flagged and excluding them from
  statistics. 300 records were withheld on the first build under this rule.

### Added
- `source_label` on every record, from ordered rules in `config/sources.toml`:
  `arXiv (preprint only)`, `Academia.edu`, `APS`, `Elsevier`, `IOP`, `Springer`,
  `Nature Portfolio`, `AIP`, `IEEE`, `ACM`, `Wiley`, `MDPI` and more. Exposed as
  a viewer facet and a CSV column.

### Fixed
- **Future publication dates.** Crossref's `issued` is often a *planned print
  issue*, so Elsevier records arrived dated 2027-01-01 and sorted above
  everything real. `best_date()` now takes the earliest non-future of
  `published-online`, `issued`, `published-print` and `created`. The 8 affected
  records were repaired in place; `check` treats a future date as an error.

### Vocabulary v0.4
- **Screen recall fix.** `quantum_terms` did not recognise QML, quantum lattice
  Boltzmann, Lindbladian, reservoir-computing or quantum-walk vocabulary, so
  papers using only those names were dropped before they could be tagged — even
  though `[algorithm_families]` has entries for all five. Found by the new test
  suite, not by reading output. Measured effect: core-with-abstract 850 → **984**,
  CFD-facing 253 → **282**. Those 134 papers were being discarded before they
  could be tagged, so every v0.3 and earlier coverage percentage was computed on
  a corpus missing them.

### Added
- `tests/` (31 tests) and `.github/workflows/tests.yml` running on 3.11 and 3.13.
  Entirely offline, so CI cannot fail because arXiv is rate-limiting you.
- `qpdewatch check`: corpus integrity validation. Structural problems are errors
  and fail CI; duplicate DOIs and titles are warnings, since choosing which copy
  to keep is a judgement call.
- The weekly job now fails loudly when arXiv queries failed, instead of staying
  green while collecting nothing.

### Changed
- **Derived outputs are no longer committed.** `data/corpus.csv`, the coverage
  matrices, the scorecard, `docs/index.html` and the figures are gitignored and
  rebuilt by `qpdewatch build`. They were adding ~5 MB to every commit for
  information fully recoverable from `data/corpus.jsonl`. The site is now
  published from the Action's Pages artifact — set Settings → Pages → Source to
  "GitHub Actions".
- Crossref de-duplication now runs *before* the ingest screen, so a terse
  journal record still enriches the arXiv paper it matches.
- Dependencies carry upper bounds.

## 2026-10-19

- Crossref added as a discovery source, not just a citation lookup: +124 core
  papers (21 CFD-facing) from venues arXiv never surfaced.
- `core` / `adjacent` tiers. Adjacent = quantum method, no PDE target; browsable
  but excluded from every statistic.
- Coverage statistics restricted to core papers *with an abstract*. Crossref
  carries one for only ~1/3 of records, and counting untagged papers as "failing
  to address axis X" would depress every percentage for a bibliographic reason.
- `config/seed_dois.toml` for papers no keyword query reaches.
- arXiv client made rate-limit aware: 429/503 aborts the run rather than
  deepening the block, and `state.json` only advances after a clean run.
- Vocabulary v0.3: `[document_types]`, `[problem_settings]`, QML split out of
  the variational family, version moved to a quoted 0.x string.

## 2026-10-15

- Favourites, full author lists, inline TeX rendering in the viewer.
- Vocabulary v0.2: Lindbladian/open-system family; lattice-Boltzmann fix in the
  Boltzmann PDE target. Corpus 700 → 733 screened, 201 → 225 CFD-facing.

## 2026-10-14

- First version: arXiv harvest, Crossref citation enrichment, controlled
  vocabulary tagging, coverage matrices, HTML viewer. Vocabulary v0.1,
  700 screened papers, 201 CFD-facing.

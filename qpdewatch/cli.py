"""Command line interface.

    python -m qpdewatch update            # the weekly job: harvest, enrich, build
    python -m qpdewatch update --full     # ignore the incremental cutoff
    python -m qpdewatch build             # re-tag and rebuild outputs, no network
    python -m qpdewatch harvest --since 2026-01-01
    python -m qpdewatch enrich --max-requests 200
    python -m qpdewatch stats
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from . import coverage, enrich as enrich_mod, harvest as harvest_mod, site, store, tag
from .config import DATA_DIR, DOCS_DIR, load_queries, load_vocabularies

OVERLAP_DAYS = 10  # re-check a window before the last run, so nothing slips through


def _cutoff(state: dict, full: bool) -> str | None:
    if full or "last_harvest" not in state:
        return None
    last = datetime.fromisoformat(state["last_harvest"]).date()
    return (last - timedelta(days=OVERLAP_DAYS)).isoformat()


def do_harvest(args) -> dict:
    corpus = store.load_corpus()
    state = store.load_state()
    since = args.since or _cutoff(state, args.full)
    print(f"harvesting (since={since or 'beginning of time'}), {len(corpus)} already on file")
    queries = load_queries()
    found, failed = harvest_mod.harvest(queries, since=since, max_pages=args.max_pages)
    n_new, n_upd = store.merge(corpus, found)
    store.save_corpus(corpus)
    # Only advance the cutoff on a clean run, so a throttled run is retried in full
    # next time instead of silently leaving a hole in the record.
    if not failed:
        state["last_harvest"] = date.today().isoformat()
    state["n_records"] = len(corpus)
    state["last_failed_queries"] = failed
    store.save_state(state)
    print(f"  {len(found)} records seen, {n_new} new, {n_upd} updated, {len(corpus)} total")
    return corpus


def do_enrich(args, corpus: dict | None = None) -> dict:
    corpus = corpus if corpus is not None else store.load_corpus()
    enrich_mod.enrich(corpus, max_requests=args.max_requests, refresh_days=args.refresh_days)
    store.save_corpus(corpus)
    return corpus


def do_build(args, corpus: dict | None = None) -> None:
    corpus = corpus if corpus is not None else store.load_corpus()
    vocab = load_vocabularies()
    rows = tag.build_rows(corpus, vocab)
    if not rows:
        raise SystemExit("no records survived the screen — check config/vocabularies.toml")
    csv_path = tag.write_csv(rows)
    tables = coverage.write_tables(rows, vocab)
    html = site.build(rows, vocab)
    n_cfd = sum(1 for r in rows if r["cfd_facing"])
    print(f"  {len(rows)} screened rows ({n_cfd} CFD-facing) -> {csv_path.name}, "
          f"{', '.join(p.name for p in tables)}, {html.relative_to(html.parent.parent)}")
    if not args.no_figures:
        try:
            figs = coverage.write_figures(rows, vocab)
            print(f"  figures -> {', '.join(p.name for p in figs)}")
        except ImportError:
            print("  figures skipped (matplotlib not installed)")


def do_stats(_args) -> None:
    corpus = store.load_corpus()
    vocab = load_vocabularies()
    rows = tag.build_rows(corpus, vocab)
    cfd = [r for r in rows if r["cfd_facing"]]
    print(f"records on file : {len(corpus)}")
    print(f"pass screen     : {len(rows)}")
    print(f"CFD-facing      : {len(cfd)}")
    print(f"crossref matched: {sum(1 for r in rows if r['citations_crossref'] is not None)}")
    print(f"state           : {store.load_state()}")
    print("\nby year (CFD-facing):")
    years: dict[int, int] = {}
    for r in cfd:
        years[r["year"]] = years.get(r["year"], 0) + 1
    for y in sorted(years):
        print(f"  {y}  {'#' * years[y]} {years[y]}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="qpdewatch", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_harvest_args(p):
        p.add_argument("--since", help="ISO date; only page back this far")
        p.add_argument("--full", action="store_true", help="ignore the incremental cutoff")
        p.add_argument("--max-pages", type=int, default=2, help="pages of 200 per query")

    def add_enrich_args(p):
        p.add_argument("--max-requests", type=int, default=400)
        p.add_argument("--refresh-days", type=int, default=90)

    def add_build_args(p):
        p.add_argument("--no-figures", action="store_true")

    p = sub.add_parser("harvest", help="fetch new arXiv records"); add_harvest_args(p)
    p = sub.add_parser("enrich", help="fill in Crossref citation counts"); add_enrich_args(p)
    p = sub.add_parser("build", help="re-tag and regenerate outputs (no network)")
    add_build_args(p)
    p = sub.add_parser("update", help="harvest + enrich + build")
    add_harvest_args(p); add_enrich_args(p); add_build_args(p)
    sub.add_parser("stats", help="summarise what is on file")

    args = ap.parse_args(argv)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    if args.cmd == "harvest":
        do_harvest(args)
    elif args.cmd == "enrich":
        do_enrich(args)
    elif args.cmd == "build":
        do_build(args)
    elif args.cmd == "update":
        corpus = do_harvest(args)
        corpus = do_enrich(args, corpus)
        do_build(args, corpus)
    elif args.cmd == "stats":
        do_stats(args)


if __name__ == "__main__":
    main()

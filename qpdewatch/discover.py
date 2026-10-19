"""Crossref as a *discovery* source, not just a citation lookup.

arXiv misses anything that was never preprinted — a probe of three queries found
23 in-scope journal-only papers in venues including npj Quantum Information,
Communications Physics and AVS Quantum Science. Crossref indexes essentially
every DOI-issuing venue, needs no key, and we already call it for citations.

Two things make this harder than "add a second feed":

1. Duplicates. Most of this literature is on arXiv *and* in a journal. Records
   are matched on DOI first, then on a normalised title, then fuzzily; a hit
   enriches the existing record with its journal DOI and venue rather than
   creating a second row.
2. Missing abstracts. Only about a third of Crossref records carry one, and our
   tags are regex over title plus abstract. `backfill_abstracts` recovers what
   it can from arXiv by title; whatever is left is marked and held out of the
   coverage statistics by `coverage.statistical_rows`.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import time
import tomllib
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from . import harvest as arxiv
from .config import CONFIG_DIR

API = "https://api.crossref.org/works?"
POLITE_DELAY = 0.6
TITLE_MATCH = 0.93


def load_queries(path: Path | None = None) -> list[str]:
    path = path or CONFIG_DIR / "queries_crossref.toml"
    return list(tomllib.loads(path.read_text(encoding="utf-8"))["queries"])


def normalise(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def strip_jats(xml: str | None) -> str:
    """Crossref abstracts are JATS XML; keep the text, drop the markup and the
    redundant leading 'Abstract' heading."""
    if not xml:
        return ""
    text = " ".join(re.sub(r"<[^>]+>", " ", xml).split())
    return re.sub(r"^Abstract[:\s]*", "", text, flags=re.I)


def search(query: str, rows: int = 100, from_date: str = "2015-01-01",
           mailto: str | None = None, timeout: int = 60) -> list[dict]:
    params = {
        "query.bibliographic": query, "rows": rows,
        "filter": f"from-pub-date:{from_date},type:journal-article",
        # published-online/print and created are needed by best_date(); publisher
        # drives the source label.
        "select": "title,DOI,abstract,author,container-title,issued,publisher,"
                  "published-online,published-print,created,"
                  "is-referenced-by-count,type",
    }
    if mailto:
        params["mailto"] = mailto
    req = urllib.request.Request(API + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["message"]["items"]


def _date_parts(item: dict, field: str) -> str:
    parts = (item.get(field) or {}).get("date-parts") or [[]]
    y, m, d = (list(parts[0]) + [None, None, None])[:3]
    return f"{y:04d}-{m or 1:02d}-{d or 1:02d}" if y else ""


def best_date(item: dict, today: str | None = None) -> str:
    """The earliest date the work was actually available.

    Crossref's `issued` is documented as the earliest known publication date,
    but publishers routinely set it to a *planned print issue* — Elsevier in
    particular — so an article online today can arrive carrying 2027-01-01. A
    corpus sorted by date then opens on papers from the future.

    Preference order is the earliest non-future of the real candidates, falling
    back to `created` (the Crossref deposit stamp, which cannot be in the
    future) and finally clamping. Clamping is last resort: a wrong-but-plausible
    date is worse than an obviously-today one only if it is silent, and `check`
    flags any that slip through.
    """
    today = today or date.today().isoformat()
    candidates = [_date_parts(item, f) for f in
                  ("published-online", "issued", "published-print", "created")]
    real = sorted(d for d in candidates if d and d <= today)
    if real:
        return real[0]
    created = _date_parts(item, "created")
    if created and created <= today:
        return created
    return today


def to_record(item: dict) -> dict:
    doi = (item.get("DOI") or "").lower()
    issued = item.get("issued", {}).get("date-parts", [[None]])[0]
    y = issued[0] if issued else None
    published = best_date(item)
    authors = [" ".join(p for p in (a.get("given"), a.get("family")) if p).strip()
               for a in item.get("author", [])]
    venue = (item.get("container-title") or [""])[0]
    return {
        "uid": "doi:" + doi,
        "source": "crossref",
        "arxiv_id": "",
        "doi": doi,
        "title": " ".join((item.get("title") or [""])[0].split()),
        "abstract": strip_jats(item.get("abstract")),
        "authors": [a for a in authors if a],
        "categories": [],
        "published": published,
        "updated": published,
        "journal_ref": venue,
        "queries": [],
        "publisher": item.get("publisher", ""),
        "crossref": {"doi": doi, "cites": item.get("is-referenced-by-count", 0),
                     "venue": venue, "year": y, "type": item.get("type"),
                     "publisher": item.get("publisher", ""),
                     "checked": date.today().isoformat()},
    }


def load_seed_dois(path: Path | None = None) -> list[str]:
    path = path or CONFIG_DIR / "seed_dois.toml"
    if not path.exists():
        return []
    return [d.strip().lower() for d in
            tomllib.loads(path.read_text(encoding="utf-8")).get("dois", []) if d.strip()]


def fetch_doi(doi: str, mailto: str | None = None, timeout: int = 30) -> dict | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    if mailto:
        url += "?mailto=" + urllib.parse.quote(mailto)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)["message"]
    except Exception:
        return None


def add_seeds(corpus: dict[str, dict], log=print) -> int:
    """Pull in DOIs listed by hand in config/seed_dois.toml.

    The keyword queries cannot be exhaustive — a paper whose subject sits far
    from every query string will never appear in any top-100, however relevant
    its one paragraph about PDEs. Seeds bypass the ingest gate entirely, because
    a human put the DOI there on purpose. They are still tiered at build time
    like everything else, so a seed with no PDE content lands in `adjacent`
    rather than silently inflating the core statistics.
    """
    mailto = os.environ.get("CROSSREF_MAILTO") or None
    by_doi, _ = _index(corpus)
    added = 0
    for doi in load_seed_dois():
        if doi in by_doi:
            continue
        item = fetch_doi(doi, mailto)
        if not item or not (item.get("title") or [""])[0]:
            log(f"  ! seed DOI not found in Crossref: {doi}")
            continue
        rec = to_record(item)
        rec["first_seen"] = date.today().isoformat()
        rec["seeded"] = True
        corpus[rec["uid"]] = rec
        added += 1
        time.sleep(POLITE_DELAY)
    if added:
        log(f"  seeds: added {added}")
    return added


def _index(corpus: dict[str, dict]) -> tuple[dict[str, str], dict[str, str]]:
    by_doi, by_title = {}, {}
    for uid, rec in corpus.items():
        for cand in (rec.get("doi"), (rec.get("crossref") or {}).get("doi")):
            if cand:
                by_doi[cand.lower()] = uid
        by_title[normalise(rec.get("title"))] = uid
    return by_doi, by_title


def merge_crossref(corpus: dict[str, dict], found: list[dict], vocab=None,
                   log=print) -> dict[str, int]:
    """Add genuinely new records; fold the rest into their existing match.

    Unlike the arXiv queries, which are themselves quantum-targeted, Crossref's
    query.bibliographic is a fuzzy relevance search that returns its full `rows`
    quota however thin the match — "quantum algorithm finite element method"
    happily returns ordinary FEM papers. Records failing the quantum half of the
    screen are therefore dropped at ingest rather than stored forever and
    re-screened at every build. The PDE half is *not* applied here: that is the
    core/adjacent tier decision, and it stays at build time so a vocabulary edit
    can still move papers between tiers.
    """
    by_doi, by_title = _index(corpus)
    titles = list(by_title)
    stats = {"seen": 0, "new": 0, "off_topic": 0,
             "dup_doi": 0, "dup_title": 0, "dup_fuzzy": 0}
    today = date.today().isoformat()
    for rec in found:
        stats["seen"] += 1
        norm = normalise(rec["title"])
        hit, how = None, None
        if rec["doi"] in by_doi:
            hit, how = by_doi[rec["doi"]], "dup_doi"
        elif norm in by_title:
            hit, how = by_title[norm], "dup_title"
        else:
            close = difflib.get_close_matches(norm, titles, n=1, cutoff=TITLE_MATCH)
            if close:
                hit, how = by_title[close[0]], "dup_fuzzy"
        if hit:
            stats[how] += 1
            existing = corpus[hit]
            # The arXiv record stays canonical — it has the full abstract, the
            # author list and the version history. Take only what it lacks.
            cr = existing.setdefault("crossref", {})
            cr.setdefault("doi", rec["doi"])
            cr.setdefault("venue", rec["crossref"]["venue"])
            if cr.get("cites") is None:
                cr["cites"] = rec["crossref"]["cites"]
            cr.setdefault("checked", today)
            if not (existing.get("abstract") or "").strip() and rec["abstract"]:
                existing["abstract"] = rec["abstract"]
                existing["abstract_source"] = "crossref"
            continue
        # The gate applies only to genuinely new records. A Crossref hit that
        # matches a paper already on file enriches it above regardless of how
        # terse its own title is — the existing record already earned its place.
        if vocab is not None and not vocab.quantum_terms.search(
                f"{rec['title']} {rec['abstract']}"):
            stats["off_topic"] += 1
            continue
        rec["first_seen"] = today
        corpus[rec["uid"]] = rec
        by_doi[rec["doi"]] = rec["uid"]
        by_title[norm] = rec["uid"]
        titles.append(norm)
        stats["new"] += 1
    log(f"  crossref: {stats['seen']} seen, {stats['off_topic']} off-topic dropped, "
        f"{stats['new']} new, {stats['dup_doi']} DOI dups, "
        f"{stats['dup_title']} title dups, {stats['dup_fuzzy']} fuzzy dups")
    return stats


def prune_off_topic(corpus: dict[str, dict], vocab, log=print) -> int:
    """Drop stored Crossref records that fail the quantum screen.

    Only ever removes `source == "crossref"` rows: arXiv records are kept
    whatever they say, because the arXiv queries were targeted in the first place
    and the harvest is the reproducible record of what those queries returned.
    """
    doomed = [uid for uid, rec in corpus.items()
              if rec.get("source") == "crossref"
              and not vocab.quantum_terms.search(
                  f"{rec.get('title','')} {rec.get('abstract','')}")]
    for uid in doomed:
        del corpus[uid]
    if doomed:
        log(f"  pruned {len(doomed)} off-topic Crossref records")
    return len(doomed)


def discover(corpus: dict[str, dict], vocab, queries: list[str] | None = None,
             rows: int = 100, from_date: str = "2015-01-01", log=print) -> dict[str, int]:
    mailto = os.environ.get("CROSSREF_MAILTO") or None
    found: list[dict] = []
    for query in (queries if queries is not None else load_queries()):
        try:
            items = search(query, rows=rows, from_date=from_date, mailto=mailto)
        except Exception as exc:
            log(f"  ! crossref query failed ({type(exc).__name__}): {query[:60]}")
            continue
        found.extend(to_record(it) for it in items if (it.get("title") or [""])[0])
        log(f"  {len(items):>4} hits  {query[:66]}")
        time.sleep(POLITE_DELAY)
    prune_off_topic(corpus, vocab, log=log)
    add_seeds(corpus, log=log)
    return merge_crossref(corpus, found, vocab=vocab, log=log)


def backfill_abstracts(corpus: dict[str, dict], vocab, max_lookups: int = 150,
                       log=print) -> dict[str, int]:
    """Recover missing abstracts from arXiv by title match.

    Each attempt is recorded so a title that has no preprint is not retried every
    week; arXiv's 3 s rate limit makes that the dominant cost of this step.
    """
    from .tag import tier_of
    todo = [r for r in corpus.values()
            if r.get("source") == "crossref"
            and not (r.get("abstract") or "").strip()
            and not r.get("abstract_lookup")
            and tier_of(r, vocab) is not None]
    # Core tier first: those are the rows the statistics are computed over, so
    # a recovered abstract there is worth more than one in the adjacent tier.
    todo.sort(key=lambda r: (tier_of(r, vocab) != "core", r.get("published", "")),
              reverse=False)
    todo.sort(key=lambda r: tier_of(r, vocab) != "core")
    stats = {"tried": 0, "recovered": 0}
    for rec in todo[:max_lookups]:
        title = rec["title"]
        payload = arxiv.fetch_page(f'ti:"{title[:120]}"', page_size=5)
        stats["tried"] += 1
        rec["abstract_lookup"] = date.today().isoformat()
        if payload:
            for cand in arxiv.parse_feed(payload):
                ratio = difflib.SequenceMatcher(
                    None, normalise(cand["title"]), normalise(title)).ratio()
                if ratio > TITLE_MATCH and cand["abstract"]:
                    rec["abstract"] = cand["abstract"]
                    rec["abstract_source"] = "arxiv:" + cand["arxiv_id"]
                    rec["arxiv_id"] = cand["arxiv_id"]
                    stats["recovered"] += 1
                    break
        time.sleep(arxiv.POLITE_DELAY)
    remaining = max(0, len(todo) - max_lookups)
    log(f"  abstracts: tried {stats['tried']}, recovered {stats['recovered']}, "
        f"{remaining} still queued")
    stats["remaining"] = remaining
    return stats


def repair_dates(corpus: dict[str, dict], log=print) -> int:
    """Re-fetch records whose stored date is in the future.

    Only needed for records ingested before best_date() existed; new ones can
    no longer acquire a future date. Cheap: there are a handful, and leaving
    them makes the corpus sort open on papers that have not happened yet.
    """
    mailto = os.environ.get("CROSSREF_MAILTO") or None
    today = date.today().isoformat()
    broken = [r for r in corpus.values()
              if r.get("source") == "crossref" and (r.get("published") or "") > today]
    fixed = 0
    for rec in broken:
        item = fetch_doi(rec.get("doi", ""), mailto)
        new = best_date(item, today) if item else today
        if new and new != rec["published"]:
            rec["published"] = new
            rec["updated"] = new
            fixed += 1
        if item and item.get("publisher"):
            rec["publisher"] = item["publisher"]
            rec.setdefault("crossref", {})["publisher"] = item["publisher"]
        time.sleep(POLITE_DELAY)
    if broken:
        log(f"  repaired {fixed} of {len(broken)} future-dated records")
    return fixed

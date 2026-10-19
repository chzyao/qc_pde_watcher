"""Relevance screening and controlled-vocabulary tagging.

Tags are derived, never stored in corpus.jsonl: every run recomputes them from
the current vocabularies, so editing config/vocabularies.toml re-tags the whole
corpus rather than only the new arrivals.

A tag records what a paper *advertises* in its title and abstract. It is not a
reading of the full text, so per-paper tags are approximate and axis totals are
lower bounds. That is the intended semantics for a gap map: it measures what the
community currently treats as a headline-worthy contribution.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .config import (DATA_DIR, FORWARD_LABEL, PROBLEM_CLASS_ORDER, TAG_FIELDS,
                     Vocabularies)
from .sources import load_rules


def searchable(rec: dict) -> str:
    return f"{rec.get('title', '')} {rec.get('abstract', '')}"


def tier_of(rec: dict, vocab: Vocabularies) -> str | None:
    """'core', 'adjacent', or None (drop).

    core      quantum method AND a differential-equation target — the corpus
              proper, and the only tier the gap-map statistics are computed over.
    adjacent  quantum method but no PDE term: QML-for-chemistry, quantum
              simulation, general quantum-computing surveys. Kept so the
              neighbourhood is browsable, excluded from every statistic.
    """
    text = searchable(rec)
    if vocab.hard_exclude.search(rec.get("title", "")):
        return None
    if not vocab.quantum_terms.search(text):
        return None
    return "core" if vocab.pde_terms.search(text) else "adjacent"


def passes_screen(rec: dict, vocab: Vocabularies) -> bool:
    """Back-compat helper: true for the core tier only."""
    return tier_of(rec, vocab) == "core"


def tag_record(rec: dict, vocab: Vocabularies) -> dict:
    """Return the derived fields for one record."""
    text = searchable(rec)
    tags = {f: [name for name, rx in vocab.vocab(f).items() if rx.search(text)]
            for f in TAG_FIELDS}
    tags["cfd_facing"] = any(t in vocab.cfd_pde_targets for t in tags["pde_targets"])
    tags["is_review"] = "Review / survey" in tags["document_types"]
    # Single-valued convenience field. "Forward (assumed)" is a fallback, not a
    # detection: forward solvers almost never announce themselves as such.
    tags["problem_class"] = next(
        (label for key, label in PROBLEM_CLASS_ORDER if key in tags["problem_settings"]),
        FORWARD_LABEL)
    return tags


def pending_abstract(corpus: dict[str, dict], vocab: Vocabularies) -> list[dict]:
    """Screened-in records still missing an abstract.

    They stay in corpus.jsonl so the weekly backfill keeps retrying them; they
    are simply withheld from the published outputs until the text arrives.
    """
    return [r for r in corpus.values()
            if tier_of(r, vocab) is not None and not (r.get("abstract") or "").strip()]


def build_rows(corpus: dict[str, dict], vocab: Vocabularies,
               source_rules=None, require_abstract: bool = True) -> list[dict]:
    """Screen, tag and flatten the corpus into export-ready rows (newest first)."""
    source_rules = source_rules or load_rules()
    rows = []
    for rec in corpus.values():
        tier = tier_of(rec, vocab)
        if tier is None:
            continue
        # An entry with no abstract cannot be read or judged, and its tags are
        # title-only guesses. Withhold it rather than publish a stub; it stays
        # in the corpus and the weekly backfill keeps trying.
        if require_abstract and not (rec.get("abstract") or "").strip():
            continue
        cr = rec.get("crossref") or {}
        tags = tag_record(rec, vocab)
        authors = rec.get("authors") or []
        abstract = rec.get("abstract", "") or ""
        arxiv_id = rec.get("arxiv_id") or ""
        doi = cr.get("doi") or rec.get("doi") or ""
        rows.append({
            "uid": rec.get("uid") or arxiv_id or ("doi:" + doi.lower()),
            "tier": tier,
            "source": rec.get("source", "arxiv"),
            "source_label": source_rules.label(rec),
            "publisher": rec.get("publisher") or (cr.get("publisher") or ""),
            # An abstract-less record can only be tagged from its title, so it is
            # held out of every coverage statistic rather than counted as a paper
            # that fails to address an axis.
            "has_abstract": bool(abstract.strip()),
            "arxiv_id": arxiv_id,
            "published": rec.get("published", ""),
            "year": int(rec["published"][:4]) if rec.get("published") else None,
            "updated": rec.get("updated", ""),
            "first_seen": rec.get("first_seen", ""),
            "title": rec.get("title", ""),
            "first_author": authors[0] if authors else "",
            "authors": "; ".join(authors),
            "n_authors": len(authors),
            "primary_cat": (rec.get("categories") or [""])[0],
            "cfd_facing": tags["cfd_facing"],
            "is_review": tags["is_review"],
            "problem_class": tags["problem_class"],
            "algorithm_families": "; ".join(tags["algorithm_families"]),
            "pde_targets": "; ".join(tags["pde_targets"]),
            "capability_axes": "; ".join(tags["capability_axes"]),
            "document_types": "; ".join(tags["document_types"]),
            "problem_settings": "; ".join(tags["problem_settings"]),
            "citations_crossref": cr.get("cites"),
            "venue": cr.get("venue"),
            "doi": doi or None,
            "url": (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                    else f"https://doi.org/{doi}" if doi else ""),
            "abstract": abstract,
        })
    rows.sort(key=lambda r: (r["published"], r["uid"]), reverse=True)
    return rows


def write_csv(rows: list[dict], path: Path | None = None) -> Path:
    path = path or DATA_DIR / "corpus.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path

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

from .config import DATA_DIR, TAG_FIELDS, Vocabularies


def searchable(rec: dict) -> str:
    return f"{rec.get('title', '')} {rec.get('abstract', '')}"


def passes_screen(rec: dict, vocab: Vocabularies) -> bool:
    text = searchable(rec)
    return bool(
        vocab.quantum_terms.search(text)
        and vocab.pde_terms.search(text)
        and not vocab.hard_exclude.search(rec.get("title", ""))
    )


def tag_record(rec: dict, vocab: Vocabularies) -> dict:
    """Return the derived fields for one record."""
    text = searchable(rec)
    tags = {f: [name for name, rx in vocab.vocab(f).items() if rx.search(text)]
            for f in TAG_FIELDS}
    tags["cfd_facing"] = any(t in vocab.cfd_pde_targets for t in tags["pde_targets"])
    return tags


def build_rows(corpus: dict[str, dict], vocab: Vocabularies) -> list[dict]:
    """Screen, tag and flatten the corpus into export-ready rows (newest first)."""
    rows = []
    for rec in corpus.values():
        if not passes_screen(rec, vocab):
            continue
        cr = rec.get("crossref") or {}
        tags = tag_record(rec, vocab)
        authors = rec.get("authors") or []
        rows.append({
            "arxiv_id": rec["arxiv_id"],
            "published": rec.get("published", ""),
            "year": int(rec["published"][:4]) if rec.get("published") else None,
            "updated": rec.get("updated", ""),
            "first_seen": rec.get("first_seen", ""),
            "title": rec.get("title", ""),
            "first_author": authors[0] if authors else "",
            "n_authors": len(authors),
            "primary_cat": (rec.get("categories") or [""])[0],
            "cfd_facing": tags["cfd_facing"],
            "algorithm_families": "; ".join(tags["algorithm_families"]),
            "pde_targets": "; ".join(tags["pde_targets"]),
            "capability_axes": "; ".join(tags["capability_axes"]),
            "citations_crossref": cr.get("cites"),
            "venue": cr.get("venue"),
            "doi": cr.get("doi") or rec.get("doi"),
            "url": f"https://arxiv.org/abs/{rec['arxiv_id']}",
            "abstract": rec.get("abstract", ""),
        })
    rows.sort(key=lambda r: (r["published"], r["arxiv_id"]), reverse=True)
    return rows


def write_csv(rows: list[dict], path: Path | None = None) -> Path:
    path = path or DATA_DIR / "corpus.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path

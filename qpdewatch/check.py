"""Integrity checks for the stored corpus.

Run by CI and by `qpdewatch check`. The point is to catch silent corruption
early: this file accumulates for years, is rewritten by an unattended weekly
job, and nothing downstream would complain about a duplicate key or a record
that lost its date — the numbers would just quietly be wrong.
"""
from __future__ import annotations

import re
from collections import Counter

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED = ("uid", "title", "published", "source", "first_seen")


def problems(corpus: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings).

    Errors are structural corruption — a missing date, a key that disagrees with
    its record — and fail the build. Warnings are data-quality observations that
    need a human: two arXiv IDs sharing a title usually means the authors posted
    the same work twice, and which one to keep is a judgement call, not
    something an unattended weekly job should decide.
    """
    out: list[str] = []
    warn: list[str] = []

    for key, rec in corpus.items():
        missing = [f for f in REQUIRED if not rec.get(f)]
        if missing:
            out.append(f"{key}: missing {', '.join(missing)}")
        if rec.get("uid") and rec["uid"] != key:
            out.append(f"{key}: uid field disagrees with its key ({rec['uid']})")
        for field in ("published", "updated", "first_seen"):
            value = rec.get(field)
            if value and not DATE_RE.match(value):
                out.append(f"{key}: {field} is not ISO yyyy-mm-dd ({value!r})")
        if rec.get("source") == "arxiv" and not rec.get("arxiv_id"):
            out.append(f"{key}: arXiv record without an arxiv_id")
        if rec.get("source") == "crossref" and not rec.get("doi"):
            out.append(f"{key}: crossref record without a doi")
        if not isinstance(rec.get("authors", []), list):
            out.append(f"{key}: authors is not a list")

    # A DOI reachable from two *different* records means de-duplication let a
    # pair through, which inflates every count downstream. Count distinct
    # records, not field occurrences: one record normally carries the same DOI
    # in both `doi` and `crossref.doi`, and that is not a duplicate.
    doi_owners: dict[str, set[str]] = {}
    for key, rec in corpus.items():
        for cand in (rec.get("doi"), (rec.get("crossref") or {}).get("doi")):
            if cand:
                doi_owners.setdefault(cand.lower(), set()).add(key)
    for doi, owners in doi_owners.items():
        if len(owners) > 1:
            warn.append(f"DOI {doi} is claimed by {len(owners)} records: {sorted(owners)}")

    title_owners: dict[str, set[str]] = {}
    for key, rec in corpus.items():
        norm = re.sub(r"[^a-z0-9]+", " ", (rec.get("title") or "").lower()).strip()
        if norm:
            title_owners.setdefault(norm, set()).add(key)
    for title, owners in title_owners.items():
        if len(owners) > 1:
            warn.append(f"{len(owners)} records share the title {title[:58]!r}: {sorted(owners)}")

    return out, warn


def summarise(corpus: dict[str, dict]) -> dict[str, int]:
    by_source = Counter(r.get("source", "arxiv") for r in corpus.values())
    return {"records": len(corpus), **{f"source:{k}": v for k, v in sorted(by_source.items())},
            "with_abstract": sum(1 for r in corpus.values() if (r.get("abstract") or "").strip()),
            "with_citations": sum(1 for r in corpus.values()
                                  if (r.get("crossref") or {}).get("cites") is not None)}

"""Crossref citation enrichment.

Most records are preprint-only and will never match; a miss is cached with a
`checked` date so the same hopeless titles are not re-queried every week.
Set CROSSREF_MAILTO to use Crossref's polite pool (faster, more reliable).
"""
from __future__ import annotations

import difflib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

API = "https://api.crossref.org/works?"
TITLE_MATCH_THRESHOLD = 0.90
POLITE_DELAY = 0.6


def _query(title: str, mailto: str | None, timeout: int = 30) -> list[dict]:
    params = {
        "query.bibliographic": title, "rows": 2,
        "select": "title,DOI,is-referenced-by-count,issued,container-title,type",
    }
    if mailto:
        params["mailto"] = mailto
    req = urllib.request.Request(API + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["message"]["items"]


def lookup(title: str, mailto: str | None = None) -> dict | None:
    """Return a citation record, or None when no title match is confident enough."""
    for item in _query(title, mailto):
        candidate = (item.get("title") or [""])[0]
        ratio = difflib.SequenceMatcher(None, candidate.lower(), title.lower()).ratio()
        if ratio > TITLE_MATCH_THRESHOLD:
            issued = item.get("issued", {}).get("date-parts", [[None]])[0]
            return {
                "doi": item.get("DOI"),
                "cites": item.get("is-referenced-by-count", 0),
                "venue": (item.get("container-title") or [""])[0],
                "year": issued[0] if issued else None,
                "type": item.get("type"),
                "match_ratio": round(ratio, 3),
            }
    return None


def needs_lookup(rec: dict, refresh_days: int, today: date) -> bool:
    cr = rec.get("crossref")
    if cr is None or "checked" not in cr:
        return True
    try:
        checked = datetime.fromisoformat(cr["checked"]).date()
    except ValueError:
        return True
    # Matched records are refreshed to keep counts current; misses are retried
    # less eagerly, since an unpublished preprint stays unpublished for a while.
    window = refresh_days if cr.get("cites") is not None else refresh_days * 2
    return today - checked > timedelta(days=window)


def enrich(corpus: dict[str, dict], max_requests: int = 400, refresh_days: int = 90,
           delay: float = POLITE_DELAY, log=print) -> dict[str, int]:
    mailto = os.environ.get("CROSSREF_MAILTO") or None
    today = date.today()
    pending = [r for r in corpus.values() if needs_lookup(r, refresh_days, today)]
    # Newest first: recent papers are the ones most likely to have just appeared
    # in a journal, and the ones a reader is most interested in.
    pending.sort(key=lambda r: r.get("published", ""), reverse=True)
    stats = {"checked": 0, "matched": 0, "errors": 0, "pending_after": 0}
    for rec in pending[:max_requests]:
        try:
            hit = lookup(rec["title"], mailto)
            rec["crossref"] = {**(hit or {}), "checked": today.isoformat()}
            stats["matched"] += hit is not None
        except Exception as exc:
            rec.setdefault("crossref", {})["error"] = str(exc)[:120]
            stats["errors"] += 1
        stats["checked"] += 1
        time.sleep(delay)
    stats["pending_after"] = max(0, len(pending) - max_requests)
    log(f"  crossref: checked {stats['checked']}, matched {stats['matched']}, "
        f"errors {stats['errors']}, still pending {stats['pending_after']}")
    return stats

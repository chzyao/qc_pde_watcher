"""Incremental harvesting from the arXiv API.

Results are requested newest-first, so a weekly run can stop paging as soon as it
reaches papers older than the cutoff instead of re-downloading the whole corpus.
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "http://export.arxiv.org/api/query?"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ID_RE = re.compile(r"arxiv\.org/abs/(?P<id>.+?)(?:v(?P<ver>\d+))?$")

# arXiv asks for one request every 3 seconds; do not lower this.
POLITE_DELAY = 3.0


def fetch_page(query: str, start: int = 0, page_size: int = 200,
               timeout: int = 60, retries: int = 5, log=None) -> bytes | None:
    """Fetch one page, retrying with exponential backoff.

    arXiv throttles aggressively when a client opens several connections in quick
    succession — in practice the first few requests of a cold run are the ones
    that fail — so the backoff starts long rather than short.
    """
    url = API + urllib.parse.urlencode({
        "search_query": query, "start": start, "max_results": page_size,
        "sortBy": "submittedDate", "sortOrder": "descending",
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            if log and attempt == 0:
                log(f"    retrying after {type(exc).__name__}: {str(exc)[:70]}")
            if attempt == retries - 1:
                return None
            time.sleep(10 * 2 ** attempt)  # 10, 20, 40, 80 s
    return None


def parse_feed(payload: bytes) -> list[dict]:
    root = ET.fromstring(payload)
    out = []
    for entry in root.findall("a:entry", NS):
        raw_id = entry.find("a:id", NS).text.strip()
        match = ID_RE.search(raw_id)
        text = lambda tag: (entry.find(tag, NS).text if entry.find(tag, NS) is not None else None)
        out.append({
            "arxiv_id": match.group("id") if match else raw_id,
            "version": int(match.group("ver")) if (match and match.group("ver")) else 1,
            "title": " ".join((text("a:title") or "").split()),
            "abstract": " ".join((text("a:summary") or "").split()),
            "published": (text("a:published") or "")[:10],
            "updated": (text("a:updated") or "")[:10],
            "authors": [a.find("a:name", NS).text for a in entry.findall("a:author", NS)],
            "categories": [c.get("term") for c in entry.findall("a:category", NS)],
            "doi": text("arxiv:doi"),
            "journal_ref": text("arxiv:journal_ref"),
        })
    return out


def harvest(queries: list[str], since: str | None = None, page_size: int = 200,
            max_pages: int = 2, delay: float = POLITE_DELAY, log=print) -> dict[str, dict]:
    """Run every query and return de-duplicated records keyed by arXiv ID.

    `since` is an ISO date. Paging for a query stops once a whole page is older
    than `since`, which is what makes the weekly run cheap. Records older than
    `since` are still returned if they share a page with newer ones — the merge
    step de-duplicates, so this is harmless.
    """
    found: dict[str, dict] = {}
    failed: list[str] = []
    for query in queries:
        pages = n_rows = 0
        for start in range(0, max_pages * page_size, page_size):
            payload = fetch_page(query, start=start, page_size=page_size, log=log)
            if payload is None:
                log(f"  ! FETCH FAILED after retries: {query[:60]} (start={start})")
                failed.append(query)
                break
            rows = parse_feed(payload)
            pages += 1
            n_rows += len(rows)
            for rec in rows:
                if rec["arxiv_id"] in found:
                    found[rec["arxiv_id"]]["queries"].append(query)
                else:
                    rec["queries"] = [query]
                    found[rec["arxiv_id"]] = rec
            exhausted = len(rows) < page_size
            stale = bool(since) and rows and all(r["published"] < since for r in rows)
            if exhausted or stale:
                break
            time.sleep(delay)
        log(f"  {n_rows:>4} rows / {pages} page(s)  {query[:70]}")
        time.sleep(delay)
    for rec in found.values():
        rec["queries"] = sorted(set(rec["queries"]))
    if failed:
        log(f"  WARNING: {len(failed)} of {len(queries)} queries failed; this run is "
            f"incomplete. Re-run `harvest --full` to fill the gap.")
    return found, failed

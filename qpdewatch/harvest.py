"""Incremental harvesting from the arXiv API.

Results are requested newest-first, so a weekly run can stop paging as soon as it
reaches papers older than the cutoff instead of re-downloading the whole corpus.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "http://export.arxiv.org/api/query?"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ID_RE = re.compile(r"arxiv\.org/abs/(?P<id>.+?)(?:v(?P<ver>\d+))?$")

# arXiv asks for one request every 3 seconds; do not lower this.
POLITE_DELAY = 3.0
# Waits after a 429/503, in seconds. Long on purpose: the block lasts minutes,
# and every premature attempt counts against the same quota.
RATE_LIMIT_BACKOFF = (60, 180, 420)
# arXiv asks clients to identify themselves so they can contact you instead of
# silently blocking. Point this at your own fork.
USER_AGENT = "qpdewatch/0.1 (literature tracker; +https://github.com/chzyao/qc_pde_watcher)"


class RateLimited(RuntimeError):
    """arXiv returned 429/503. Retrying inside the same run only digs deeper."""


def fetch_page(query: str, start: int = 0, page_size: int = 200,
               timeout: int = 60, retries: int = 4, log=None) -> bytes | None:
    """Fetch one page, retrying with exponential backoff.

    arXiv answers an over-quota client with `429 Rate exceeded` (sometimes 503).
    That is a sustained block, not a blip: retrying fast makes it worse, because
    every attempt counts against the same quota. So a rate-limit response gets a
    long backoff and then raises RateLimited, which aborts the whole run — far
    better than grinding through thirty queries that will all fail. Ordinary
    network errors keep the short retry.
    """
    url = API + urllib.parse.urlencode({
        "search_query": query, "start": start, "max_results": page_size,
        "sortBy": "submittedDate", "sortOrder": "descending",
    })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503):
                if attempt == retries - 1:
                    raise RateLimited(
                        f"arXiv returned {exc.code} after {retries} attempts. "
                        "Wait for the quota to reset (usually minutes) and re-run; "
                        "state.json has not advanced, so nothing is lost.") from None
                wait = RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)]
                if log:
                    log(f"    rate limited ({exc.code}); waiting {wait}s")
                time.sleep(wait)
            else:
                if attempt == retries - 1:
                    return None
                time.sleep(5 * (attempt + 1))
        except Exception as exc:
            if log and attempt == 0:
                log(f"    retrying after {type(exc).__name__}: {str(exc)[:70]}")
            if attempt == retries - 1:
                return None
            time.sleep(5 * (attempt + 1))
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
    found_queries: set[str] = set()
    for query in queries:
        pages = n_rows = 0
        for start in range(0, max_pages * page_size, page_size):
            try:
                payload = fetch_page(query, start=start, page_size=page_size, log=log)
            except RateLimited as exc:
                log(f"  ! {exc}")
                failed.extend(q for q in queries if q not in found_queries)
                return found, sorted(set(failed))
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
        found_queries.add(query)
        log(f"  {n_rows:>4} rows / {pages} page(s)  {query[:70]}")
        time.sleep(delay)
    for rec in found.values():
        rec["queries"] = sorted(set(rec["queries"]))
    if failed:
        log(f"  WARNING: {len(failed)} of {len(queries)} queries failed; this run is "
            f"incomplete. Re-run `harvest --full` to fill the gap.")
    return found, failed

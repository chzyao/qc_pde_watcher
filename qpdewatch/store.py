"""On-disk corpus: newline-delimited JSON keyed by arXiv ID, plus run state.

JSONL is chosen deliberately over a pickle or a database: it diffs cleanly in git,
so each weekly commit shows exactly which papers arrived.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from .config import DATA_DIR

CORPUS_PATH = DATA_DIR / "corpus.jsonl"
STATE_PATH = DATA_DIR / "state.json"


def load_corpus(path: Path | None = None) -> dict[str, dict]:
    path = path or CORPUS_PATH
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                out[rec["arxiv_id"]] = rec
    return out


def save_corpus(corpus: dict[str, dict], path: Path | None = None) -> None:
    """Atomic write, sorted by submission date so git diffs stay readable."""
    path = path or CORPUS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    rows = sorted(corpus.values(), key=lambda r: (r.get("published", ""), r["arxiv_id"]))
    with tmp.open("w", encoding="utf-8") as fh:
        for rec in rows:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)


def load_state(path: Path | None = None) -> dict:
    path = path or STATE_PATH
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(state: dict, path: Path | None = None) -> None:
    path = path or STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def merge(corpus: dict[str, dict], harvested: dict[str, dict],
          today: str | None = None) -> tuple[int, int]:
    """Merge harvested records in place. Returns (n_new, n_updated).

    Existing records keep their first_seen and crossref block; title/abstract are
    refreshed so that replaced arXiv versions propagate into the tags.
    """
    today = today or date.today().isoformat()
    n_new = n_upd = 0
    for aid, rec in harvested.items():
        if aid not in corpus:
            rec["first_seen"] = today
            corpus[aid] = rec
            n_new += 1
        else:
            old = corpus[aid]
            merged_queries = sorted(set(old.get("queries", [])) | set(rec.get("queries", [])))
            changed = (old.get("updated") != rec.get("updated")
                       or old.get("abstract") != rec.get("abstract")
                       or old.get("queries", []) != merged_queries)
            old.update({k: v for k, v in rec.items()
                        if k not in ("first_seen", "crossref", "queries")})
            old["queries"] = merged_queries
            if changed:
                n_upd += 1
    return n_new, n_upd

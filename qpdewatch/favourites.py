"""Starred papers, kept in a committed plain-text file.

The viewer is a static page, so it has nowhere durable of its own to write. The
split is therefore:

  data/favourites.txt   the source of truth — committed, diffable, portable
  browser localStorage  your working set in this browser, seeded from the file

Starring in the viewer updates localStorage immediately. "Export favourites"
copies a merged file back out; drop it over data/favourites.txt and commit, and
the star is permanent and available on every machine.
"""
from __future__ import annotations

from pathlib import Path

from .config import DATA_DIR

FAVOURITES_PATH = DATA_DIR / "favourites.txt"

HEADER = """\
# Starred papers — one arXiv ID per line, optional note after '#'.
# This file is the durable record; the HTML viewer seeds its stars from it.
# After starring in the browser, use "Export favourites" and replace this file.
"""


def load(path: Path | None = None) -> dict[str, str]:
    """Return {arxiv_id: note}. Missing file is not an error."""
    path = path or FAVOURITES_PATH
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        body, _, note = line.partition("#")
        ident = body.strip()
        if ident:
            out[ident] = note.strip()
    return out


def save(favourites: dict[str, str], path: Path | None = None) -> Path:
    path = path or FAVOURITES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [HEADER]
    for ident in sorted(favourites):
        note = favourites[ident]
        lines.append(f"{ident}  # {note}" if note else ident)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

"""Short, filterable labels for where a paper came from.

Kept in config/sources.toml rather than in code so that adding a publisher is a
one-line config edit — the same rule as the tagging vocabularies, and the reason
both survive being left alone for a year.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG_DIR


@dataclass
class SourceRules:
    rules: list[tuple[str, re.Pattern]]
    preprint_label: str
    fallback: str

    def label(self, rec: dict) -> str:
        cr = rec.get("crossref") or {}
        venue = cr.get("venue") or rec.get("journal_ref") or ""
        publisher = rec.get("publisher") or cr.get("publisher") or ""
        if not (venue or publisher):
            return self.preprint_label
        haystack = f"{publisher} | {venue}"
        for label, pattern in self.rules:
            if pattern.search(haystack):
                return label
        return self.fallback


def load_rules(path: Path | None = None) -> SourceRules:
    path = path or CONFIG_DIR / "sources.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return SourceRules(
        rules=[(r["label"], re.compile(r["match"], re.I)) for r in raw.get("rule", [])],
        preprint_label=raw.get("preprint_label", "Preprint only"),
        fallback=raw.get("fallback", "Other"),
    )

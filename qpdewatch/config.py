"""Configuration loading: queries and controlled vocabularies."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

TAG_FIELDS = ("algorithm_families", "pde_targets", "capability_axes",
              "document_types", "problem_settings")

# Precedence for the derived single-valued `problem_class`. First match wins;
# papers matching none fall through to "Forward (assumed)".
PROBLEM_CLASS_ORDER = (
    ("Inverse problem / data assimilation", "Inverse"),
    ("PDE-constrained optimisation / control", "Optimisation / control"),
    ("Uncertainty quantification / stochastic", "Uncertainty quantification"),
)
FORWARD_LABEL = "Forward (assumed)"


@dataclass
class Vocabularies:
    """Compiled regex vocabularies plus the relevance screen."""

    schema_version: str
    algorithm_families: dict[str, re.Pattern] = field(default_factory=dict)
    pde_targets: dict[str, re.Pattern] = field(default_factory=dict)
    capability_axes: dict[str, re.Pattern] = field(default_factory=dict)
    document_types: dict[str, re.Pattern] = field(default_factory=dict)
    problem_settings: dict[str, re.Pattern] = field(default_factory=dict)
    cfd_pde_targets: tuple[str, ...] = ()
    quantum_terms: re.Pattern | None = None
    pde_terms: re.Pattern | None = None
    hard_exclude: re.Pattern | None = None

    def vocab(self, name: str) -> dict[str, re.Pattern]:
        return getattr(self, name)


def load_vocabularies(path: Path | None = None) -> Vocabularies:
    path = path or CONFIG_DIR / "vocabularies.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    screen = raw["screen"]
    compile_ = lambda d: {k: re.compile(v, re.I) for k, v in d.items()}
    unknown = set(screen["cfd_pde_targets"]) - set(raw["pde_targets"])
    if unknown:
        raise ValueError(f"cfd_pde_targets names absent from [pde_targets]: {sorted(unknown)}")
    return Vocabularies(
        # str() so an unquoted TOML value still works, though quoting is correct:
        # "0.10" must sort after "0.9", which a float cannot represent.
        schema_version=str(raw["schema_version"]),
        algorithm_families=compile_(raw["algorithm_families"]),
        pde_targets=compile_(raw["pde_targets"]),
        capability_axes=compile_(raw["capability_axes"]),
        document_types=compile_(raw.get("document_types", {})),
        problem_settings=compile_(raw.get("problem_settings", {})),
        cfd_pde_targets=tuple(screen["cfd_pde_targets"]),
        quantum_terms=re.compile(screen["quantum_terms"], re.I),
        pde_terms=re.compile(screen["pde_terms"], re.I),
        hard_exclude=re.compile(screen["hard_exclude"], re.I),
    )


def load_queries(path: Path | None = None) -> list[str]:
    path = path or CONFIG_DIR / "queries.toml"
    return list(tomllib.loads(path.read_text(encoding="utf-8"))["queries"])

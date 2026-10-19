"""Tests for the screening, tagging and storage layers.

These are the parts where a quiet mistake is expensive: a regex that stops
matching silently changes every statistic in the gap map, and nothing in the
output looks broken. All offline — no network.
"""
from __future__ import annotations

import json

import pytest

from qpdewatch import favourites, store
from qpdewatch.config import TAG_FIELDS, load_queries, load_vocabularies
from qpdewatch.coverage import statistical_rows
from qpdewatch.tag import build_rows, tag_record, tier_of


@pytest.fixture(scope="module")
def vocab():
    return load_vocabularies()


def rec(title: str, abstract: str = "", **kw):
    base = {"uid": kw.pop("uid", "test.0001"), "arxiv_id": kw.pop("arxiv_id", "test.0001"),
            "title": title, "abstract": abstract, "authors": ["A Author"],
            "categories": ["quant-ph"], "published": "2026-01-01", "updated": "2026-01-01",
            "first_seen": "2026-01-01", "source": "arxiv"}
    base.update(kw)
    return base


# --- configuration -------------------------------------------------------

def test_every_vocabulary_regex_compiles(vocab):
    for field in TAG_FIELDS:
        assert vocab.vocab(field), f"{field} is empty"
    assert vocab.quantum_terms and vocab.pde_terms and vocab.hard_exclude


def test_schema_version_is_a_string(vocab):
    # A float 0.10 would equal 0.1, silently colliding the tenth revision with
    # the first. The TOML value must stay quoted.
    assert isinstance(vocab.schema_version, str)


def test_cfd_targets_all_exist_in_pde_vocabulary(vocab):
    assert set(vocab.cfd_pde_targets) <= set(vocab.pde_targets)


def test_query_files_are_loadable_and_nonempty():
    from qpdewatch.discover import load_queries as load_cr
    assert len(load_queries()) > 10
    assert len(load_cr()) > 10


# --- tiering -------------------------------------------------------------

def test_core_requires_both_quantum_and_pde(vocab):
    assert tier_of(rec("A quantum algorithm for the Navier-Stokes equations"), vocab) == "core"


def test_quantum_without_pde_is_adjacent(vocab):
    r = rec("Quantum machine learning for molecular property prediction",
            "We use variational quantum circuits for drug discovery.")
    assert tier_of(r, vocab) == "adjacent"


def test_non_quantum_is_dropped(vocab):
    assert tier_of(rec("A finite element solver for the heat equation"), vocab) is None


def test_hard_exclude_wins_over_everything(vocab):
    assert tier_of(rec("No Drama Quantum Electrodynamics?", "quantum algorithm PDE"), vocab) is None


# --- review detection: precision is the whole point ----------------------

@pytest.mark.parametrize("title,abstract", [
    ("A Survey of Quantum Linear System Solvers", "We cover algorithms for PDEs."),
    ("Quantum Algorithms for CFD: A Review", "quantum algorithm differential equation"),
    ("Quantum PDE solvers", "In this review we examine quantum algorithms for PDEs."),
])
def test_genuine_reviews_are_detected(vocab, title, abstract):
    assert tag_record(rec(title, abstract), vocab)["is_review"]


@pytest.mark.parametrize("abstract", [
    "We review the basics of Carleman linearization before presenting our quantum solver.",
    "Here we review prior work, then solve the Navier-Stokes equations on a quantum computer.",
])
def test_bare_we_review_does_not_make_a_research_paper_a_review(vocab, abstract):
    # This exact phrasing produced 3 false positives out of 16 before the
    # patterns were anchored on self-description or title position.
    assert not tag_record(rec("A quantum algorithm for Burgers' equation", abstract),
                          vocab)["is_review"]


# --- problem class -------------------------------------------------------

def test_problem_class_precedence_and_fallback(vocab):
    inv = rec("Quantum PDE solver",
              "We solve an inverse problem with data assimilation and "
              "PDE-constrained optimization and uncertainty quantification.")
    assert tag_record(inv, vocab)["problem_class"] == "Inverse"

    opt = rec("Quantum PDE solver", "We study optimal control of the flow.")
    assert tag_record(opt, vocab)["problem_class"] == "Optimisation / control"

    fwd = rec("Quantum algorithm for the heat equation", "We integrate the PDE in time.")
    assert tag_record(fwd, vocab)["problem_class"] == "Forward (assumed)"


# --- statistics guard ----------------------------------------------------

def test_statistics_exclude_adjacent_and_abstractless(vocab):
    corpus = {
        "a": rec("Quantum algorithm for Navier-Stokes flow",
                 "We solve the Navier-Stokes equations.", uid="a", arxiv_id="a"),
        "b": rec("Quantum machine learning for chemistry",
                 "Variational quantum circuits for molecules.", uid="b", arxiv_id="b"),
        "c": rec("Quantum algorithm for the Poisson equation", "", uid="c", arxiv_id="c"),
    }
    rows = build_rows(corpus, vocab)
    assert {r["uid"]: r["tier"] for r in rows} == {"a": "core", "b": "adjacent", "c": "core"}
    assert [r["uid"] for r in statistical_rows(rows)] == ["a"]


# --- storage -------------------------------------------------------------

def test_corpus_round_trips(tmp_path):
    path = tmp_path / "corpus.jsonl"
    store.save_corpus({"x": rec("Title one", "abstract", uid="x", arxiv_id="x")}, path)
    assert store.load_corpus(path)["x"]["title"] == "Title one"


def test_pre_uid_records_are_migrated(tmp_path):
    path = tmp_path / "corpus.jsonl"
    legacy = {"arxiv_id": "2512.03758", "title": "Old record", "abstract": "a",
              "published": "2025-12-03"}
    path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    loaded = store.load_corpus(path)
    assert loaded["2512.03758"]["uid"] == "2512.03758"
    assert loaded["2512.03758"]["source"] == "arxiv"


def test_merge_preserves_first_seen_and_adds_new():
    corpus = {"a": rec("Existing", "x", uid="a", arxiv_id="a", first_seen="2020-01-01")}
    incoming = {"a": rec("Existing revised", "x", uid="a", arxiv_id="a"),
                "b": rec("Brand new", "y", uid="b", arxiv_id="b")}
    n_new, _ = store.merge(corpus, incoming, today="2026-10-19")
    assert n_new == 1
    assert corpus["a"]["first_seen"] == "2020-01-01", "first_seen must never be overwritten"
    assert corpus["b"]["first_seen"] == "2026-10-19"
    assert corpus["a"]["title"] == "Existing revised", "metadata should refresh"


# --- favourites ----------------------------------------------------------

def test_favourites_round_trip_with_notes(tmp_path):
    path = tmp_path / "favourites.txt"
    favourites.save({"2603.12161": "lower bounds", "2512.03758": ""}, path)
    assert favourites.load(path) == {"2603.12161": "lower bounds", "2512.03758": ""}


def test_favourites_missing_file_is_not_an_error(tmp_path):
    assert favourites.load(tmp_path / "nope.txt") == {}

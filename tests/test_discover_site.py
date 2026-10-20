"""Tests for Crossref de-duplication and the generated viewer. Offline."""
from __future__ import annotations

import json
import re

import pytest

from qpdewatch import site
from qpdewatch.config import load_vocabularies
from qpdewatch.discover import merge_crossref, normalise, strip_jats, to_record
from qpdewatch.tag import build_rows


@pytest.fixture(scope="module")
def vocab():
    return load_vocabularies()


def arxiv_rec(uid, title, abstract="We solve the Navier-Stokes equations.", doi=None):
    return {"uid": uid, "arxiv_id": uid, "source": "arxiv", "title": title,
            "abstract": abstract, "authors": ["A Author"], "categories": ["quant-ph"],
            "published": "2026-01-01", "updated": "2026-01-01", "first_seen": "2026-01-01",
            "doi": doi}


def cr_item(title, doi, abstract=None):
    return {"title": [title], "DOI": doi, "abstract": abstract,
            "author": [{"given": "B", "family": "Writer"}],
            "container-title": ["Journal of Tests"], "issued": {"date-parts": [[2026, 5, 2]]},
            "is-referenced-by-count": 7, "type": "journal-article"}


# --- helpers -------------------------------------------------------------

def test_strip_jats_removes_markup_and_heading():
    assert strip_jats("<jats:p>Abstract: We solve <jats:italic>u</jats:italic> fast.</jats:p>") \
        == "We solve u fast."


def test_strip_jats_handles_missing():
    assert strip_jats(None) == ""


def test_normalise_ignores_punctuation_and_case():
    assert normalise("Navier--Stokes: A Quantum Algorithm!") == normalise(
        "navier stokes a quantum algorithm")


def test_to_record_builds_a_doi_keyed_record():
    r = to_record(cr_item("A paper", "10.1234/ABC", "<jats:p>Text</jats:p>"))
    assert r["uid"] == "doi:10.1234/abc" and r["source"] == "crossref"
    assert r["arxiv_id"] == "" and r["published"] == "2026-05-02"
    assert r["authors"] == ["B Writer"] and r["crossref"]["cites"] == 7


# --- de-duplication ------------------------------------------------------

def test_duplicate_by_doi_enriches_instead_of_adding(vocab):
    corpus = {"2512.00001": arxiv_rec("2512.00001", "A quantum solver", doi="10.1234/abc")}
    stats = merge_crossref(corpus, [to_record(cr_item("Totally different title",
                                                      "10.1234/abc"))],
                           vocab=vocab, log=lambda *a: None)
    assert stats["dup_doi"] == 1 and stats["new"] == 0
    assert len(corpus) == 1
    assert corpus["2512.00001"]["crossref"]["venue"] == "Journal of Tests"


def test_duplicate_by_exact_title(vocab):
    corpus = {"2512.00002": arxiv_rec("2512.00002", "Quantum algorithm for Burgers equation")}
    stats = merge_crossref(corpus, [to_record(cr_item(
        "Quantum Algorithm for Burgers Equation!", "10.9/z"))], vocab=vocab, log=lambda *a: None)
    assert stats["dup_title"] == 1 and len(corpus) == 1


def test_near_duplicate_title_is_caught_fuzzily(vocab):
    corpus = {"2512.00003": arxiv_rec(
        "2512.00003", "Quantum algorithms for the incompressible Navier-Stokes equations")}
    stats = merge_crossref(corpus, [to_record(cr_item(
        "Quantum algorithms for the incompressible Navier-Stokes equation", "10.9/y"))],
        vocab=vocab, log=lambda *a: None)
    assert stats["dup_fuzzy"] == 1 and len(corpus) == 1


def test_genuinely_new_paper_is_added(vocab):
    corpus = {"2512.00004": arxiv_rec("2512.00004", "Something else entirely")}
    stats = merge_crossref(corpus, [to_record(cr_item(
        "A quantum lattice Boltzmann solver for turbulent flow", "10.9/new",
        "<jats:p>We simulate the Navier-Stokes equations.</jats:p>"))],
        vocab=vocab, log=lambda *a: None)
    assert stats["new"] == 1 and "doi:10.9/new" in corpus


def test_off_topic_crossref_hit_is_dropped_at_ingest(vocab):
    # query.bibliographic returns its full quota however thin the match.
    corpus = {}
    stats = merge_crossref(corpus, [to_record(cr_item(
        "A finite element method for elasticity", "10.9/fem",
        "<jats:p>Classical FEM, no quantum content.</jats:p>"))],
        vocab=vocab, log=lambda *a: None)
    assert stats["off_topic"] == 1 and corpus == {}


# --- generated site ------------------------------------------------------

def test_site_builds_parseable_payload(tmp_path, vocab):
    corpus = {"a": arxiv_rec("a", "Quantum algorithm for the heat equation",
                             r"Values of $3.7\times10^{-12}$ were found."),
              "b": arxiv_rec("b", "Quantum machine learning for chemistry",
                             "Variational circuits for molecules.")}
    out = site.build(build_rows(corpus, vocab), vocab, outdir=tmp_path, starred={"a": "note"})
    html = out.read_text(encoding="utf-8")
    assert "__PAYLOAD__" not in html and "__TITLE__" not in html
    blob = re.search(r'<script id="payload" type="application/json">(.*?)</script>',
                     html, re.S).group(1)
    payload = json.loads(blob.replace("<\\/", "</"))
    assert payload["meta"]["n_total"] == 2
    assert payload["meta"]["n_core"] == 1 and payload["meta"]["n_adjacent"] == 1
    assert payload["seed"] == {"a": "note"}
    assert all(row["u"] for row in payload["rows"]), "every row needs a resolvable link"


def test_viewer_resyncs_stars_when_the_committed_file_changes(tmp_path, vocab):
    """data/favourites.txt must stay authoritative after the first visit.

    Seeding localStorage only when it was empty made the file write-only ever
    after: emptying it changed nothing for a browser that had already loaded the
    page. The page now records which seed it adopted and replaces its working
    copy when the committed file differs, so editing the file actually works.
    """
    corpus = {"a": arxiv_rec("a", "Quantum algorithm for the heat equation")}
    rows = build_rows(corpus, vocab)

    out = site.build(rows, vocab, outdir=tmp_path, starred={"a": "keep"})
    html = out.read_text(encoding="utf-8")
    assert "qpdewatch:favourites-seed" in html, "no record of which seed was adopted"
    assert "SEED_SIG" in html and "seedChanged" in html, "no resync guard"

    payload = json.loads(
        re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
        .group(1).replace("<\\/", "</"))
    assert payload["seed"] == {"a": "keep"}

    cleared = site.build(rows, vocab, outdir=tmp_path, starred={})
    payload2 = json.loads(
        re.search(r'<script id="payload" type="application/json">(.*?)</script>',
                  cleared.read_text(encoding="utf-8"), re.S).group(1).replace("<\\/", "</"))
    assert payload2["seed"] == {}, "an emptied favourites file must publish an empty seed"


def test_site_payload_cannot_break_out_of_the_script_tag(tmp_path, vocab):
    corpus = {"a": arxiv_rec("a", "Quantum PDE solver </script><script>alert(1)</script>",
                             "We solve the Navier-Stokes equations.")}
    out = site.build(build_rows(corpus, vocab), vocab, outdir=tmp_path, starred={})
    html = out.read_text(encoding="utf-8")
    payload_block = re.search(r'<script id="payload".*?</script>', html, re.S).group(0)
    assert payload_block.count("</script>") == 1

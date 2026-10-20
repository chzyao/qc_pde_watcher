"""Every arXiv call site must degrade under a 429, never abort the run.

A throttled arXiv crashed `qpdewatch update` in production: harvest() caught
RateLimited for its own loop, but backfill_abstracts() called fetch_page
directly with no handler. The run died after the harvest and the Crossref pass
had done their work and before the build, the commit and the deploy — so a
whole run's gathering was discarded by an upstream rate limit.

The rule these tests encode: anything placed before the commit step must be
unable to throw the run's work away.
"""
from __future__ import annotations

import pytest

from qpdewatch import discover, harvest
from qpdewatch.config import load_vocabularies


@pytest.fixture(scope="module")
def vocab():
    return load_vocabularies()


def queued_record(uid="doi:10.1/x"):
    return {uid: {"uid": uid, "source": "crossref", "doi": "10.1/x",
                  "title": "A quantum algorithm for the Navier-Stokes equations",
                  "abstract": "", "authors": [], "categories": [],
                  "published": "2026-01-01", "updated": "2026-01-01",
                  "first_seen": "2026-01-01"}}


def test_backfill_survives_a_rate_limit(monkeypatch, vocab):
    def refuse(*a, **k):
        raise harvest.RateLimited("arXiv returned 429 after 4 attempts.")
    monkeypatch.setattr(discover.arxiv, "fetch_page", refuse)
    monkeypatch.setattr(discover.time, "sleep", lambda *_: None)

    corpus = queued_record()
    stats = discover.backfill_abstracts(corpus, vocab, max_lookups=10, log=lambda *_: None)

    assert stats["rate_limited"] is True
    assert stats["tried"] == 0


def test_an_unreached_record_stays_queued(monkeypatch, vocab):
    """A record we never actually asked about must not be marked tried."""
    def refuse(*a, **k):
        raise harvest.RateLimited("429")
    monkeypatch.setattr(discover.arxiv, "fetch_page", refuse)
    monkeypatch.setattr(discover.time, "sleep", lambda *_: None)

    corpus = queued_record()
    discover.backfill_abstracts(corpus, vocab, max_lookups=10, log=lambda *_: None)
    rec = next(iter(corpus.values()))
    assert "abstract_lookup" not in rec, "unreached record was marked as tried-and-failed"


def test_backfill_still_works_when_arxiv_answers(monkeypatch, vocab):
    sample = {"arxiv_id": "2601.00001",
              "title": "A quantum algorithm for the Navier-Stokes equations",
              "abstract": "We solve the incompressible Navier-Stokes equations."}
    monkeypatch.setattr(discover.arxiv, "fetch_page", lambda *a, **k: b"<feed/>")
    monkeypatch.setattr(discover.arxiv, "parse_feed", lambda _p: [sample])
    monkeypatch.setattr(discover.time, "sleep", lambda *_: None)

    corpus = queued_record()
    stats = discover.backfill_abstracts(corpus, vocab, max_lookups=10, log=lambda *_: None)

    assert stats["recovered"] == 1 and stats["rate_limited"] is False
    rec = next(iter(corpus.values()))
    assert rec["abstract"].startswith("We solve")
    assert rec["abstract_source"] == "arxiv:2601.00001"
    assert rec["abstract_lookup"], "a record we did reach should be marked"


def test_harvest_aborts_cleanly_rather_than_raising(monkeypatch):
    """harvest() returns partial results plus the unfinished queries."""
    def refuse(*a, **k):
        raise harvest.RateLimited("429")
    monkeypatch.setattr(harvest, "fetch_page", refuse)
    monkeypatch.setattr(harvest.time, "sleep", lambda *_: None)

    found, failed = harvest.harvest(["q1", "q2"], log=lambda *_: None)
    assert found == {}
    assert set(failed) == {"q1", "q2"}, "unfinished queries must be reported for retry"

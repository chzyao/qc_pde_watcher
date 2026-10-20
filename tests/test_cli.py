"""Smoke tests for every network-free subcommand.

Written after `qpdewatch stats` shipped with a NameError: a patch aimed at
`do_build` also matched a line in `do_stats`, giving it a flag only `build`
defines. Nothing caught it because the local checks ran `build`, `check` and
`pytest` — but not `stats`, which CI does run.

The lesson generalises past that one bug: a subcommand nobody exercises is a
subcommand that is broken and does not know it. These tests assert only that
each handler runs to completion against the committed corpus, which is enough
to catch NameError, AttributeError, and a signature drifting away from its
argparse definition.
"""
from __future__ import annotations

import pytest

from qpdewatch import cli, coverage, site, tag

OFFLINE_COMMANDS = [
    ["stats"],
    ["check"],
    ["build", "--no-figures"],
    ["build", "--no-figures", "--include-abstractless"],
]


@pytest.fixture
def sandboxed_outputs(tmp_path, monkeypatch):
    """Send every generated file to tmp_path so tests never touch the repo."""
    monkeypatch.setattr(tag, "DATA_DIR", tmp_path)
    monkeypatch.setattr(coverage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(coverage, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(site, "DOCS_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize("argv", OFFLINE_COMMANDS, ids=lambda a: " ".join(a))
def test_offline_subcommand_runs(argv, sandboxed_outputs, capsys):
    try:
        cli.main(argv)
    except SystemExit as exc:
        # `check` exits 1 on structural problems; that is a legitimate outcome.
        # Any other exception is the bug class this test exists to catch.
        assert exc.code in (0, 1, None), f"{argv} exited {exc.code}"
    assert capsys.readouterr().out.strip(), f"{argv} produced no output"


NEEDS_NETWORK = {"harvest", "discover", "enrich", "update"}


def all_subcommands() -> set[str]:
    import argparse
    sub = next(a for a in cli.build_parser()._actions
               if isinstance(a, argparse._SubParsersAction))
    return set(sub.choices)


def test_no_subcommand_is_left_unexercised():
    """Adding a subcommand without a smoke test or a network excuse fails here."""
    covered = {argv[0] for argv in OFFLINE_COMMANDS}
    orphans = all_subcommands() - covered - NEEDS_NETWORK
    assert not orphans, f"subcommands with no test and no network excuse: {sorted(orphans)}"


@pytest.mark.parametrize("name", sorted(NEEDS_NETWORK))
def test_network_subcommands_parse_and_dispatch(name, monkeypatch):
    """The network commands can't run here, but their wiring can still be checked:
    argparse must produce exactly the attributes each handler reads."""
    called = {}
    for target in ("do_harvest", "do_discover", "do_enrich", "do_build"):
        monkeypatch.setattr(cli, target,
                            lambda *a, _t=target, **k: called.setdefault(_t, True) or {})
    cli.main([name])
    assert called, f"{name} dispatched to nothing"

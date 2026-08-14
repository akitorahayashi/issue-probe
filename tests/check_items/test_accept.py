"""An investigation that holds is accepted, and the totals a reader needs come back with it."""

from __future__ import annotations

import json
import os

from conftest import SAMPLE_FRONT_MATTER


def test_a_consistent_investigation_is_accepted(workspace, run_check_items):
    result = run_check_items(workspace.path)

    assert result.returncode == 0, result.stdout
    document = json.loads(result.stdout)
    assert document["ok"] is True
    assert document["items"] == 3
    assert "problems" not in document


def test_the_effort_total_is_reported_so_nobody_adds_it_up_by_hand(workspace, run_check_items):
    result = run_check_items(workspace.path)

    info = " ".join(json.loads(result.stdout)["info"])
    assert "10.5h" in info


def test_the_risk_distribution_is_reported_for_every_declared_value(workspace, run_check_items):
    result = run_check_items(workspace.path)

    info = " ".join(json.loads(result.stdout)["info"])
    assert "高 1" in info
    assert "中 1" in info
    assert "低 1" in info


def test_a_heading_inside_a_fence_is_not_an_item(workspace, run_check_items):
    """The sample evidence quotes `### 99` inside a fence; it must not become an item."""
    result = run_check_items(workspace.path)

    assert json.loads(result.stdout)["items"] == 3


def test_counts_measured_at_another_commit_are_reported_as_stale(workspace, run_check_items):
    workspace.write_coverage({"scope": ["app"], "searches": [], "codeSha": "0" * 40})

    result = run_check_items(workspace.path)

    assert result.returncode == 0, result.stdout
    assert any("件数の計測時のコミット" in line for line in json.loads(result.stdout)["info"])


def test_an_export_older_than_the_findings_is_reported_as_stale(workspace, run_check_items):
    """Nothing about an outdated paste.tsv looks outdated to the person about to paste it."""
    paste = workspace.path / "paste.tsv"
    paste.write_text("No.\n1\n", encoding="utf-8")
    written = (workspace.path / "findings.md").stat().st_mtime
    os.utime(paste, (written - 10, written - 10))

    result = run_check_items(workspace.path)

    assert result.returncode == 0, result.stdout
    assert any("paste.tsv" in line for line in json.loads(result.stdout)["info"])


def test_an_investigation_with_no_item_is_accepted_with_a_hint(workspace, run_check_items):
    """Re-verification can retire every item, and the workspace still has to be readable."""
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="1"), items="")

    result = run_check_items(workspace.path)

    assert result.returncode == 0, result.stdout
    document = json.loads(result.stdout)
    assert document["items"] == 0
    assert document["hint"]

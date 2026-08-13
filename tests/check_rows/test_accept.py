"""A workspace that holds is accepted, and the totals a reader needs come back with it."""

from __future__ import annotations

import json


def test_a_consistent_workspace_is_accepted(workspace, run_check_rows):
    result = run_check_rows(workspace.path)

    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["ok"] is True
    assert document["items"] == 3
    assert "problems" not in document


def test_the_effort_total_is_reported_so_nobody_adds_it_up_by_hand(workspace, run_check_rows):
    result = run_check_rows(workspace.path)

    info = " ".join(json.loads(result.stdout)["info"])
    assert "10.5h" in info


def test_the_enum_distribution_is_reported_for_every_declared_value(workspace, run_check_rows):
    result = run_check_rows(workspace.path)

    info = " ".join(json.loads(result.stdout)["info"])
    assert "高 1" in info
    assert "中 1" in info
    assert "低 1" in info


def test_a_heading_inside_a_fence_does_not_count_as_evidence(workspace, run_check_rows):
    """The sample evidence quotes `### 99` inside a fence; it must not become an item."""
    result = run_check_rows(workspace.path)

    assert result.returncode == 0, result.stdout

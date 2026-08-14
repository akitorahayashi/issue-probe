"""A pasted row keeps its position, so the numbers behind it cannot move or vanish."""

from __future__ import annotations

import json

from conftest import SAMPLE_FRONT_MATTER, item

ROUND = "554d505b4c6eccc9597dcdf1c133d80f0e34cbe1"


def problems(result, check: str) -> list[dict]:
    return [entry for entry in json.loads(result.stdout)["problems"] if entry["check"] == check]


def test_a_duplicated_item_number_is_refused(workspace, run_check_items):
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="3"), item(number="1") + item(number="1"))

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in problems(result, "numbering")] == [1]


def test_items_out_of_ascending_order_are_refused(workspace, run_check_items):
    """The export follows the document, so an unsorted document is an unsorted paste."""
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="3"), item(number="2") + item(number="1"))

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in problems(result, "numbering")] == [1]


def test_an_item_number_at_or_past_the_allocator_names_the_value_to_restore(workspace, run_check_items):
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item(number="1") + item(number="2"))

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    entries = problems(result, "numbering")
    assert [entry["item"] for entry in entries] == [2]
    assert "nextItem を 3" in entries[0]["detail"]


def test_a_number_reserved_only_by_a_verdict_must_stay_below_the_allocator(workspace, run_check_items):
    """A retired item still holds its number, so the allocator has to clear it too."""
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item(number="1"))
    workspace.write_verdicts(f"# 記録\n\n## {ROUND}\n\n### 7 delete\n\n- 変更: 削除\n")

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in problems(result, "numbering")] == [7]


def test_a_gap_without_a_delete_verdict_is_refused(workspace, run_check_items):
    """A number that consumed no claim, or a claim that vanished without a reason."""
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="4"), item(number="1") + item(number="3"))

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in problems(result, "retired")] == [2]


def test_a_gap_explained_by_a_delete_verdict_is_accepted(workspace, run_check_items):
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="4"), item(number="1") + item(number="3"))
    workspace.write_verdicts(
        f"# 記録\n\n## {ROUND}\n\n### 2 delete\n\n- 変更: 削除\n\n主張は…だったが、到達経路が無かった。\n"
    )

    result = run_check_items(workspace.path)

    assert result.returncode == 0, result.stdout


def test_the_latest_round_decides_whether_a_gap_is_explained(workspace, run_check_items):
    """Rounds are appended, so an item confirmed after a delete belongs back in the list."""
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="4"), item(number="1") + item(number="3"))
    workspace.write_verdicts(
        f"# 記録\n\n## aaaaaaa\n\n### 2 delete\n\n- 変更: 削除\n\n## {ROUND}\n\n### 2 confirmed\n\n- 変更: なし\n"
    )

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in problems(result, "retired")] == [2]

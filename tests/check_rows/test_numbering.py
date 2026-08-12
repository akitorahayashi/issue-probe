"""Item numbers are what a pasted spreadsheet row is addressed by, so they are held still."""

from __future__ import annotations

import json

from conftest import SAMPLE_FRONT_MATTER, SAMPLE_ROWS


def numbering_details(result) -> list[str]:
    return [entry["detail"] for entry in json.loads(result.stdout)["problems"] if entry["check"] == "numbering"]


def test_a_duplicated_item_number_is_refused(workspace, run_check_rows):
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[2][0] = "1"
    workspace.write_rows(rows)
    workspace.write_evidence(
        "### 1 一つ目\n\n- 根拠: ...\n\n### 3 三つ目\n\n- 根拠: ...\n",
    )

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert any("重複" in detail for detail in numbering_details(result))


def test_items_out_of_ascending_order_are_refused(workspace, run_check_rows):
    """The list is read against the sheet top to bottom; a jumbled order hides a lost row."""
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1], rows[3] = rows[3], rows[1]
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert any("昇順" in detail for detail in numbering_details(result))


def test_an_item_number_at_or_past_the_allocator_is_refused(workspace, run_check_rows):
    """nextItem is what guarantees a retired number is never handed out again."""
    front_matter = dict(SAMPLE_FRONT_MATTER)
    front_matter["nextItem"] = "3"
    workspace.write_findings(front_matter)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert any("nextItem" in detail for detail in numbering_details(result))


def test_a_non_numeric_item_number_is_refused(workspace, run_check_rows):
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1][0] = "F1"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert any(entry["check"] == "id" for entry in json.loads(result.stdout)["problems"])

"""The checks that stand between a malformed cell and a shifted spreadsheet column."""

from __future__ import annotations

import json

import pytest
from conftest import SAMPLE_ROWS, SAMPLE_SCHEMA


def checks(result) -> list[str]:
    return [entry["check"] for entry in json.loads(result.stdout)["problems"]]


def test_a_cell_that_swallowed_a_tab_is_refused(workspace, run_check_rows):
    """A tab inside a cell is a column break in the sheet, so the row arrives one column wide."""
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1][1] = "PlayerViewController.swift\tL3378"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert "width" in checks(result)


def test_a_cell_that_swallowed_a_newline_is_refused(workspace, run_check_rows):
    """A newline inside a cell becomes a new row, leaving two rows of the wrong width."""
    text = "\n".join("\t".join(row) for row in SAMPLE_ROWS).replace("L3378", "L3378\n続き") + "\n"
    workspace.write_report_text(text)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert "width" in checks(result)


def test_a_bare_carriage_return_is_refused_as_a_row_break(workspace, run_check_rows):
    """The sheet ends a row on CR as readily as on LF, so it lands as a width problem."""
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1][1] = "PlayerViewController.swift\rL3378"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert "width" in checks(result)


@pytest.mark.parametrize("character", ["\v", "\f", " ", " "])
def test_a_character_that_ruins_a_cell_from_inside_a_line_is_named(workspace, run_check_rows, character):
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1][1] = f"PlayerViewController.swift{character}L3378"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    problems = json.loads(result.stdout)["problems"]
    assert any(entry["check"] == "cell" and entry["row"] == 2 for entry in problems)


def test_a_missing_column_is_refused(workspace, run_check_rows):
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[2] = rows[2][:-1]
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert "width" in checks(result)


def test_a_header_that_drifted_from_the_sheet_is_refused(workspace, run_check_rows):
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[0][2] = "リスク度"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    problems = json.loads(result.stdout)["problems"]
    assert any(entry["check"] == "header" and "3列目" in entry["detail"] for entry in problems)


def test_a_value_outside_the_closed_vocabulary_is_refused(workspace, run_check_rows):
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1][2] = "中程度"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert "enum" in checks(result)


def test_an_effort_cell_without_a_leading_total_is_refused(workspace, run_check_rows):
    """Without a leading total the column cannot be summed, and the plan silently loses hours."""
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1][3] = "設計 3h / 実装 3h"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert "effort" in checks(result)


def test_an_effort_cell_in_the_declared_unit_is_accepted(workspace, run_check_rows):
    """One ticket counted hours and another person-days, so the unit comes from the schema."""
    schema = json.loads(json.dumps(SAMPLE_SCHEMA))
    schema["columns"][3]["unit"] = "人日"
    workspace.write_schema(schema)
    rows = [list(row) for row in SAMPLE_ROWS]
    for row in rows[1:]:
        row[3] = "1人日（実装0.5＋実機確認0.5）"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert result.returncode == 0, result.stdout
    assert "3人日" in " ".join(json.loads(result.stdout)["info"])


def test_every_problem_comes_back_in_one_pass(workspace, run_check_rows):
    """Fixing one problem at a time would mean re-running the check for each."""
    rows = [list(row) for row in SAMPLE_ROWS]
    rows[1][2] = "中程度"
    rows[2][3] = "見積もりなし"
    workspace.write_rows(rows)

    result = run_check_rows(workspace.path)

    assert {"enum", "effort"} <= set(checks(result))

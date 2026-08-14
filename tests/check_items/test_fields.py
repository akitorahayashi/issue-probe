"""A field the sheet cannot take is refused before anyone exports it."""

from __future__ import annotations

import json

import pytest
from conftest import SAMPLE_FRONT_MATTER, item


def write_one(workspace, **overrides) -> None:
    """Put exactly one item in the workspace, so a problem list has one source."""
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item(**overrides))


def problems(result, check: str) -> list[dict]:
    return [entry for entry in json.loads(result.stdout)["problems"] if entry["check"] == check]


def test_a_missing_field_is_refused(workspace, run_check_items):
    text = item()
    workspace.write_findings(
        dict(SAMPLE_FRONT_MATTER, nextItem="2"),
        "\n".join(line for line in text.splitlines() if not line.startswith("- 本来の経路:")),
    )

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert any("本来の経路" in entry["detail"] for entry in problems(result, "field"))


def test_an_empty_field_is_refused(workspace, run_check_items):
    """An empty value cannot be told apart from a value nobody wrote."""
    write_one(workspace, 備考="")

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert any("備考" in entry["detail"] for entry in problems(result, "field"))


def test_an_unknown_label_is_refused(workspace, run_check_items):
    text = item().replace("- 備考: なし", "- 備考: なし\n- 所感: 直したほうがよい")
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), text)

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert any("所感" in entry["detail"] for entry in problems(result, "field"))


def test_a_field_written_twice_is_refused(workspace, run_check_items):
    text = item().replace("- 備考: なし", "- 備考: なし\n- 備考: もうひとつ")
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), text)

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert any("備考" in entry["detail"] for entry in problems(result, "field"))


def test_a_field_with_both_a_value_and_a_nested_list_is_refused(workspace, run_check_items):
    """Two ways of writing the same cell means two answers for what the cell holds."""
    text = item(影響範囲="置換する").replace("- 影響範囲: 置換する", "- 影響範囲: 置換する\n  - 確認する")
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), text)

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert any("影響範囲" in entry["detail"] for entry in problems(result, "field"))


def test_a_risk_outside_the_vocabulary_is_refused(workspace, run_check_items):
    write_one(workspace, risk="やばい")

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert problems(result, "enum")


def test_an_effort_without_a_leading_total_is_refused(workspace, run_check_items):
    write_one(workspace, 工数="設計 3h と実装 3h")

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert problems(result, "effort")


@pytest.mark.parametrize("effort", ["6h", "6h（設計: 3h/ 実装: 3h）", "0.5h（実装: 0.5h）", " 12h"])
def test_an_effort_in_the_declared_unit_is_accepted(workspace, run_check_items, effort):
    write_one(workspace, 工数=effort)

    result = run_check_items(workspace.path)

    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize(
    ("character", "name"),
    [("\t", "タブ"), ("\v", "垂直タブ"), ("\f", "改ページ"), ("\u2028", "行区切り"), ("\u2029", "段落区切り")],
)
def test_a_value_carrying_a_character_that_breaks_the_paste_is_refused(workspace, run_check_items, character, name):
    write_one(workspace, 現状=f"非公開キーを{character}参照している")

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert any(name in entry["detail"] for entry in problems(result, "cell"))


def test_an_item_without_evidence_is_refused(workspace, run_check_items):
    write_one(workspace, evidence="")

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert problems(result, "evidence")


def test_a_malformed_heading_is_refused_rather_than_ignored(workspace, run_check_items):
    """Dropping the item would take it off the sheet without anyone noticing."""
    text = item().replace("### 1 [中] ", "### 1 ")
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), text)

    result = run_check_items(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in problems(result, "heading")] == [1]


def test_every_problem_comes_back_in_one_pass(workspace, run_check_items):
    write_one(workspace, risk="やばい", 工数="いっぱい", 備考="")

    result = run_check_items(workspace.path)

    checks = {entry["check"] for entry in json.loads(result.stdout)["problems"]}
    assert {"enum", "effort", "field"} <= checks

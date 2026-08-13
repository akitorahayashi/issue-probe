"""Every claim in the sheet stays traceable to the evidence that supports it."""

from __future__ import annotations

import json


def evidence_problems(result) -> list[dict]:
    return [entry for entry in json.loads(result.stdout)["problems"] if entry["check"] == "evidence"]


def test_a_listed_item_without_evidence_is_refused(workspace, run_check_rows):
    workspace.write_evidence("### 1 一つ目\n\n- 根拠: ...\n\n### 2 二つ目\n\n- 根拠: ...\n")

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in evidence_problems(result)] == [3]


def test_evidence_split_across_axis_files_is_accepted(workspace, run_check_rows):
    """Investigators work one axis per file, so an item may be documented in any of them."""
    workspace.write_evidence("### 1 一つ目\n\n- 根拠: ...\n\n### 2 二つ目\n\n- 根拠: ...\n", name="axis-a.md")
    workspace.write_evidence("### 3 三つ目\n\n- 根拠: ...\n", name="axis-b.md")

    result = run_check_rows(workspace.path)

    assert result.returncode == 0, result.stdout


def test_an_item_that_left_the_list_without_a_verdict_is_refused(workspace, run_check_rows):
    """A row that vanished from the sheet needs a written reason, or the retraction is invisible."""
    workspace.write_evidence(
        "### 1 一つ目\n\n- 根拠: ...\n\n### 2 二つ目\n\n- 根拠: ...\n\n### 3 三つ目\n\n- 根拠: ...\n\n"
        "### 4 取り下げたもの\n\n- 根拠: ...\n"
    )

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in evidence_problems(result)] == [4]


def test_an_item_retired_by_a_delete_verdict_is_accepted(workspace, run_check_rows):
    workspace.write_evidence(
        "### 1 一つ目\n\n- 根拠: ...\n\n### 2 二つ目\n\n- 根拠: ...\n\n### 3 三つ目\n\n- 根拠: ...\n\n"
        "### 4 取り下げたもの\n\n- 根拠: ...\n"
    )
    workspace.write_verdicts(
        "# 再検証の記録\n\n## 554d505b4c6eccc9597dcdf1c133d80f0e34cbe1\n\n### 4 delete\n\n- 変更: 削除\n"
    )

    result = run_check_rows(workspace.path)

    assert result.returncode == 0, result.stdout


def test_the_latest_round_decides_whether_an_item_is_retired(workspace, run_check_rows):
    """Rounds are appended, so an item confirmed after a delete is back in the list."""
    workspace.write_evidence(
        "### 1 一つ目\n\n- 根拠: ...\n\n### 2 二つ目\n\n- 根拠: ...\n\n### 3 三つ目\n\n- 根拠: ...\n\n"
        "### 4 復活したもの\n\n- 根拠: ...\n"
    )
    workspace.write_verdicts(
        "# 再検証の記録\n\n## aaaaaaa\n\n### 4 delete\n\n- 変更: 削除\n\n## bbbbbbb\n\n### 4 confirmed\n\n- 変更: なし\n"
    )

    result = run_check_rows(workspace.path)

    assert result.returncode == 1
    assert [entry["item"] for entry in evidence_problems(result)] == [4]

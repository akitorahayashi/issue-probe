"""The sheet paste is derived from findings.md, and never written half-broken."""

from __future__ import annotations

import json
import subprocess
import sys

from conftest import EXPORT_ITEMS_CLI, SAMPLE_FRONT_MATTER, item

# Written out by hand: this is the sheet's header row, not whatever the code produces.
EXPECTED_HEADERS = [
    "No.",
    "該当処理（概要）",
    "該当箇所（ファイル名/メソッド名/行数など）",
    "本来経由すべき共通処理（Util・共通クラス）",
    "現状の実装内容",
    "リスク度（高/中/低）",
    "想定される事象",
    "修正時の影響範囲（ファイルと機能名）",
    "修正時の工数",
    "備考",
]


def test_the_header_row_is_the_sheet_header(workspace, run_export_items):
    result = run_export_items(workspace.path)

    assert result.returncode == 0, result.stderr
    assert workspace.read_paste()[0] == EXPECTED_HEADERS


def test_one_row_per_item_in_document_order(workspace, run_export_items):
    result = run_export_items(workspace.path)

    rows = workspace.read_paste()
    assert len(rows) == 4
    assert [row[0] for row in rows[1:]] == ["1", "2", "3"]
    document = json.loads(result.stdout)
    assert document["rows"] == 3
    assert document["columns"] == len(EXPECTED_HEADERS)


def test_the_heading_supplies_the_number_the_name_and_the_risk(workspace, run_export_items):
    run_export_items(workspace.path)

    row = workspace.read_paste()[2]
    assert row[0] == "2"
    assert row[1] == "番組表のチャンネルID取得"
    assert row[5] == "高"


def test_a_nested_list_is_folded_into_one_cell(workspace, run_export_items):
    """The writer keeps a list a person can read; the numbering is this script's work."""
    run_export_items(workspace.path)

    assert workspace.read_paste()[2][7] == (
        "1. RealTimeGuideViewController.swift チャンネルID取得（L318,329） → nil考慮の共通取得へ置換する"
        " 2. 番組表画面 → チャンネル一覧と日付切替の横断確認を行う"
    )


def test_an_inline_value_is_taken_as_written(workspace, run_export_items):
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item(影響範囲="1箇所だけ置換する"))

    run_export_items(workspace.path)

    assert workspace.read_paste()[1][7] == "1箇所だけ置換する"


def test_a_value_that_breaks_the_paste_is_refused_and_nothing_is_written(workspace, run_export_items):
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item(現状="キーを\t参照している"))

    result = run_export_items(workspace.path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["problems"]
    assert not (workspace.path / "paste.tsv").exists()


def test_a_value_the_column_refuses_is_refused_here_too(workspace, run_export_items):
    """The export asks the columns the same question the check asks, so neither lets it through."""
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item(risk="やばい"))

    result = run_export_items(workspace.path)

    assert result.returncode == 1
    assert [entry["check"] for entry in json.loads(result.stdout)["problems"]] == ["enum"]
    assert not (workspace.path / "paste.tsv").exists()


def test_a_failed_export_removes_the_previous_one(workspace, run_export_items):
    """A leftover export reads as current, and it is the file a person actually pastes."""
    run_export_items(workspace.path)
    assert (workspace.path / "paste.tsv").exists()
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item(risk="やばい"))

    result = run_export_items(workspace.path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["removed"].endswith("paste.tsv")
    assert not (workspace.path / "paste.tsv").exists()


def test_a_missing_field_is_refused_and_nothing_is_written(workspace, run_export_items):
    text = "\n".join(line for line in item().splitlines() if not line.startswith("- 備考:"))
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), text)

    result = run_export_items(workspace.path)

    assert result.returncode == 1
    assert json.loads(result.stdout)["hint"]
    assert not (workspace.path / "paste.tsv").exists()


def test_the_summary_carries_what_an_overview_needs(workspace, run_export_items):
    result = run_export_items(workspace.path)

    summary = json.loads(result.stdout)["items"]
    assert summary[1] == {
        "number": 2,
        "risk": "高",
        "title": "番組表のチャンネルID取得",
        "effort": "4h",
    }


def test_rerunning_replaces_the_file(workspace, run_export_items):
    run_export_items(workspace.path)
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="2"), item())

    run_export_items(workspace.path)

    assert len(workspace.read_paste()) == 2


def test_a_missing_workspace_reports_an_action(tmp_path, run_export_items):
    result = run_export_items(tmp_path / "absent")

    assert result.returncode == 2
    assert json.loads(result.stderr)["action"]


def test_help_succeeds():
    argv = [sys.executable, str(EXPORT_ITEMS_CLI), "--help"]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0

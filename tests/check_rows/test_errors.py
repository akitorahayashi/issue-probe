"""A workspace that cannot be read stops the caller with something it can act on."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from conftest import CHECK_ROWS_CLI, SAMPLE_FRONT_MATTER, SAMPLE_SCHEMA


def action(result) -> str:
    return json.loads(result.stderr)["action"]


def test_a_missing_workspace_reports_an_action(tmp_path, run_check_rows):
    result = run_check_rows(tmp_path / "absent")

    assert result.returncode == 2
    assert action(result)


@pytest.mark.parametrize("name", ["schema.json", "report.tsv", "findings.md"])
def test_a_missing_canonical_file_reports_an_action(workspace, run_check_rows, name):
    (workspace.path / name).unlink()

    result = run_check_rows(workspace.path)

    assert result.returncode == 2
    assert name in json.loads(result.stderr)["error"]
    assert action(result)


def test_a_schema_without_an_id_column_reports_an_action(workspace, run_check_rows):
    """Without an id column there is nothing to address a spreadsheet row by."""
    schema = json.loads(json.dumps(SAMPLE_SCHEMA))
    schema["columns"][0]["role"] = "text"
    workspace.write_schema(schema)

    result = run_check_rows(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_an_enum_column_without_values_reports_an_action(workspace, run_check_rows):
    schema = json.loads(json.dumps(SAMPLE_SCHEMA))
    del schema["columns"][2]["values"]
    workspace.write_schema(schema)

    result = run_check_rows(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_findings_without_front_matter_reports_an_action(workspace, run_check_rows):
    (workspace.path / "findings.md").write_text("# 調査証跡\n", encoding="utf-8")

    result = run_check_rows(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_findings_missing_a_front_matter_key_names_the_key(workspace, run_check_rows):
    front_matter = dict(SAMPLE_FRONT_MATTER)
    del front_matter["codeSha"]
    workspace.write_findings(front_matter)

    result = run_check_rows(workspace.path)

    assert result.returncode == 2
    assert "codeSha" in json.loads(result.stderr)["error"]


def test_a_non_integer_allocator_reports_an_action(workspace, run_check_rows):
    front_matter = dict(SAMPLE_FRONT_MATTER)
    front_matter["nextItem"] = "たくさん"
    workspace.write_findings(front_matter)

    result = run_check_rows(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_an_empty_report_reports_an_action(workspace, run_check_rows):
    workspace.write_report_text("\n")

    result = run_check_rows(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_help_succeeds():
    result = subprocess.run([sys.executable, str(CHECK_ROWS_CLI), "--help"], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0

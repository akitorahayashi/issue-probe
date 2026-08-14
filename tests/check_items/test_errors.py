"""A workspace that cannot be read stops the caller with something it can act on."""

from __future__ import annotations

import json
import subprocess
import sys

from conftest import CHECK_ITEMS_CLI, SAMPLE_FRONT_MATTER


def action(result) -> str:
    return json.loads(result.stderr)["action"]


def test_a_missing_workspace_reports_an_action(tmp_path, run_check_items):
    result = run_check_items(tmp_path / "absent")

    assert result.returncode == 2
    assert action(result)


def test_a_missing_findings_reports_an_action(workspace, run_check_items):
    (workspace.path / "findings.md").unlink()

    result = run_check_items(workspace.path)

    assert result.returncode == 2
    assert "findings.md" in json.loads(result.stderr)["error"]
    assert action(result)


def test_findings_without_front_matter_reports_an_action(workspace, run_check_items):
    workspace.write_findings_text("# 320 調査\n")

    result = run_check_items(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_findings_with_unterminated_front_matter_reports_an_action(workspace, run_check_items):
    workspace.write_findings_text("---\nissue: 320\n\n# 320 調査\n")

    result = run_check_items(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_findings_missing_a_front_matter_key_names_the_key(workspace, run_check_items):
    front_matter = dict(SAMPLE_FRONT_MATTER)
    del front_matter["codeSha"]
    workspace.write_findings(front_matter)

    result = run_check_items(workspace.path)

    assert result.returncode == 2
    assert "codeSha" in json.loads(result.stderr)["error"]


def test_a_non_integer_allocator_reports_an_action(workspace, run_check_items):
    workspace.write_findings(dict(SAMPLE_FRONT_MATTER, nextItem="たくさん"))

    result = run_check_items(workspace.path)

    assert result.returncode == 2
    assert action(result)


def test_help_succeeds():
    argv = [sys.executable, str(CHECK_ITEMS_CLI), "--help"]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0

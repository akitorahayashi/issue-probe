"""Counts come from the tool, and a count that moved since the last run is reported."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest
from conftest import COUNT_HITS_CLI

pytestmark = pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep is not installed")


def run_count_hits(directory) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COUNT_HITS_CLI), str(directory)], capture_output=True, text=True, timeout=60
    )


def build_repository(tmp_path, coverage: dict) -> object:
    repository = tmp_path / "app"
    (repository / "src").mkdir(parents=True)
    (repository / "src" / "a.swift").write_text(
        'UserDefaults.standard.set(1, forKey: "a")\nUserDefaults.standard.bool(forKey: "a")\n',
        encoding="utf-8",
    )
    (repository / "src" / "b.swift").write_text('UserDefaults.standard.object(forKey: "b")\n', encoding="utf-8")
    (repository / "src" / "c.swift").write_text("let value = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=repository,
        check=True,
    )
    directory = repository / ".tmp" / "issue-probes" / "321"
    directory.mkdir(parents=True)
    (directory / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False), encoding="utf-8")
    return directory


def test_matches_and_files_are_measured_and_recorded(tmp_path):
    directory = build_repository(
        tmp_path,
        {"scope": ["src"], "searches": [{"id": "S1", "pattern": r"UserDefaults\.standard\b"}]},
    )

    result = run_count_hits(directory)

    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["searches"][0]["count"] == 3
    assert document["searches"][0]["files"] == 2
    recorded = json.loads((directory / "coverage.json").read_text(encoding="utf-8"))
    assert recorded["searches"][0]["count"] == 3
    assert recorded["codeSha"]


def test_a_search_with_no_match_records_zero_rather_than_failing(tmp_path):
    """ripgrep exits 1 on no match; that is an answer, and 該当なし is worth recording."""
    directory = build_repository(tmp_path, {"scope": ["src"], "searches": [{"pattern": "object_getIvar"}]})

    result = run_count_hits(directory)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["searches"][0]["count"] == 0


def test_a_count_that_moved_since_the_last_run_is_reported(tmp_path):
    directory = build_repository(
        tmp_path,
        {"scope": ["src"], "searches": [{"id": "S1", "pattern": r"UserDefaults\.standard\b", "count": 10}]},
    )

    result = run_count_hits(directory)

    document = json.loads(result.stdout)
    assert document["searches"][0]["previous"] == 10
    assert document["searches"][0]["delta"] == -7
    assert document["changed"] == ["S1"]


def test_coverage_without_a_scope_reports_an_action(tmp_path):
    directory = build_repository(tmp_path, {"searches": [{"pattern": "a"}]})

    result = run_count_hits(directory)

    assert result.returncode == 2
    assert json.loads(result.stderr)["action"]


def test_help_succeeds():
    result = subprocess.run([sys.executable, str(COUNT_HITS_CLI), "--help"], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0

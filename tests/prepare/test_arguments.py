"""A request the CLI cannot act on stops with something the caller can fix."""

from __future__ import annotations

import json
import subprocess
import sys

from conftest import PREPARE_CLI


def run_prepare(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(PREPARE_CLI), *args], capture_output=True, text=True, timeout=30)


def test_a_non_positive_issue_number_reports_an_action():
    result = run_prepare("0")

    assert result.returncode == 2
    assert json.loads(result.stderr)["action"]


def test_a_non_numeric_issue_number_is_refused_by_the_parser():
    result = run_prepare("three-two-one")

    assert result.returncode == 2


def test_help_succeeds():
    result = run_prepare("--help")

    assert result.returncode == 0

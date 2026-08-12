"""
Shared fixtures for the shared CLI tests.

The sample workspace is written by hand rather than produced by the code under
test, so a check that drifts fails instead of agreeing with itself. It is the
smallest layout that still exercises every column role: an id, free text, a
closed vocabulary, and an effort total.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugin/scripts"
CHECK_ROWS_CLI = SCRIPTS / "check_rows.py"
COUNT_HITS_CLI = SCRIPTS / "count_hits.py"
PREPARE_CLI = SCRIPTS / "prepare.py"

# The scripts are flat modules, not a package, so a pure-function test imports them directly.
sys.path.insert(0, str(SCRIPTS))

SAMPLE_SCHEMA = {
    "sheet": {
        "url": "https://docs.google.com/spreadsheets/d/sample/edit",
        "table": "tvOS",
        "firstDataCell": "A2",
    },
    "columns": [
        {"header": "No.", "role": "id"},
        {"header": "該当箇所", "role": "text"},
        {"header": "リスク度（高/中/低）", "role": "enum", "values": ["高", "中", "低"]},
        {"header": "修正時の工数", "role": "effort", "unit": "h"},
    ],
}

SAMPLE_ROWS = [
    ["No.", "該当箇所", "リスク度（高/中/低）", "修正時の工数"],
    ["1", "PlayerViewController.swift L3378", "中", "6h（設計: 3h/ 実装: 3h）"],
    ["2", "RealTimeGuideViewController.swift L318", "高", "4h（設計: 2h/ 実装: 2h）"],
    ["3", "GlobalFunction.swift L9", "低", "0.5h（実装: 0.5h）"],
]

SAMPLE_FRONT_MATTER = {
    "issue": "321",
    "issueRepo": "owner/documents",
    "codeRepo": "owner/app",
    "codeSha": "554d505b4c6eccc9597dcdf1c133d80f0e34cbe1",
    "probedAt": "2026-08-12",
    "nextItem": "4",
}

SAMPLE_EVIDENCE = """# 観点A の証跡

### 1 音声・字幕トラック名の取得

- 根拠: PlayerViewController.swift L3378 で非公開キーを参照している

### 2 番組表のチャンネルID取得

- 根拠: RealTimeGuideViewController.swift L318 の強制キャスト

```text
### 99 これはフェンス内なので節ではない
```

### 3 未使用のエラー生成関数の残存

- 根拠: Utilities.swift L397 の呼び出し元が0件
"""


@dataclass
class Workspace:
    """A workspace on disk that a test can bend one way at a time."""

    path: Path

    def write_schema(self, schema: object) -> None:
        (self.path / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_rows(self, rows: list[list[str]]) -> None:
        text = "\n".join("\t".join(row) for row in rows) + "\n"
        (self.path / "report.tsv").write_text(text, encoding="utf-8")

    def write_report_text(self, text: str) -> None:
        (self.path / "report.tsv").write_text(text, encoding="utf-8")

    def write_findings(self, front_matter: dict[str, str], body: str = "# 調査証跡\n") -> None:
        lines = ["---", *[f"{key}: {value}" for key, value in front_matter.items()], "---", "", body]
        (self.path / "findings.md").write_text("\n".join(lines), encoding="utf-8")

    def write_evidence(self, text: str, name: str = "axis-a.md") -> None:
        directory = self.path / "findings"
        directory.mkdir(exist_ok=True)
        (directory / name).write_text(text, encoding="utf-8")

    def write_verdicts(self, text: str) -> None:
        (self.path / "verdicts.md").write_text(text, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """A workspace that passes every check, for a test to break in exactly one place."""
    directory = tmp_path / "issue-probes" / "321"
    directory.mkdir(parents=True)
    space = Workspace(directory)
    space.write_schema(SAMPLE_SCHEMA)
    space.write_rows(SAMPLE_ROWS)
    space.write_findings(dict(SAMPLE_FRONT_MATTER))
    space.write_evidence(SAMPLE_EVIDENCE)
    return space


@pytest.fixture
def run_check_rows():
    """Run check_rows.py as a subprocess against the given directory."""

    def _run(directory: Path | str, *extra: str) -> subprocess.CompletedProcess[str]:
        argv = [sys.executable, str(CHECK_ROWS_CLI), str(directory), *extra]
        return subprocess.run(argv, capture_output=True, text=True, timeout=30)

    return _run

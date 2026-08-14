"""
Shared fixtures for the shared CLI tests.

The sample workspace is written by hand rather than produced by the code under
test, so a check that drifts fails instead of agreeing with itself. Its field
labels are spelled out here for the same reason: if the layout in columns.py
changes, these tests have to be changed too, deliberately.

It is the smallest findings.md that still exercises every part of the contract:
three items across the whole risk vocabulary, an effort total worth summing, an
inline field and a nested one, and a heading quoted inside a fence.
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
CHECK_ITEMS_CLI = SCRIPTS / "check_items.py"
EXPORT_ITEMS_CLI = SCRIPTS / "export_items.py"
COUNT_HITS_CLI = SCRIPTS / "count_hits.py"
PREPARE_CLI = SCRIPTS / "prepare.py"
FINDINGS_TEMPLATE = ROOT / "plugin/skills/probe-issue/assets/findings.md"

# The scripts are flat modules, not a package, so a pure-function test imports them directly.
sys.path.insert(0, str(SCRIPTS))

FIELD_ORDER = (
    "該当箇所",
    "本来の経路",
    "現状",
    "想定される事象",
    "影響範囲",
    "工数",
    "備考",
)

DEFAULT_FIELDS: dict[str, str | list[str]] = {
    "該当箇所": "PlayerViewController.swift L3378",
    "本来の経路": "AVFoundation の公開API",
    "現状": "非公開キーを文字列で参照している",
    "想定される事象": "OS更新でトラック名が取れなくなり再生画面が落ちる",
    "影響範囲": ["PlayerViewController.swift トラック一覧（L3378） → 公開APIへ置換する"],
    "工数": "6h（設計: 3h/ 実装: 3h）",
    "備考": "なし",
}

SAMPLE_FRONT_MATTER = {
    "issue": "320",
    "issueRepo": "owner/documents",
    "codeRepo": "owner/app",
    "codeSha": "554d505b4c6eccc9597dcdf1c133d80f0e34cbe1",
    "probedAt": "2026-08-12",
    "nextItem": "4",
}


def item(
    number: str = "1",
    risk: str = "中",
    title: str = "音声・字幕トラック名の取得",
    evidence: str = "L3378 を読んで非公開キーの参照を確認した。",
    **overrides: str | list[str],
) -> str:
    """Build one item section. A field value may be a string or a nested bullet list."""
    fields = {**DEFAULT_FIELDS, **overrides}
    lines = [f"### {number} [{risk}] {title}", ""]
    for label in FIELD_ORDER:
        value = fields[label]
        if isinstance(value, list):
            lines.append(f"- {label}:")
            lines.extend(f"  - {child}" for child in value)
        else:
            lines.append(f"- {label}: {value}")
    lines += ["", "#### 根拠", "", evidence, ""]
    return "\n".join(lines)


SAMPLE_ITEMS = "\n".join(
    [
        item(
            number="1",
            risk="中",
            evidence="```text\n### 99 フェンス内なので節ではない\n```\n\nL3378 を読んで確認した。",
        ),
        item(
            number="2",
            risk="高",
            title="番組表のチャンネルID取得",
            該当箇所="RealTimeGuideViewController.swift L318,329（2箇所）",
            想定される事象="APIがidをnullで返すと番組表表示時に即クラッシュする",
            影響範囲=[
                "RealTimeGuideViewController.swift チャンネルID取得（L318,329） → nil考慮の共通取得へ置換する",
                "番組表画面 → チャンネル一覧と日付切替の横断確認を行う",
            ],
            工数="4h（設計: 2h/ 実装: 2h）",
        ),
        item(
            number="3",
            risk="低",
            title="未使用のエラー生成関数の残存",
            該当箇所="Utilities.swift L397-407",
            工数="0.5h（実装: 0.5h）",
        ),
    ]
)


def document(front_matter: dict[str, str], items: str) -> str:
    """Assemble a findings.md the way the template lays it out."""
    lines = ["---", *[f"{key}: {value}" for key, value in front_matter.items()], "---", ""]
    lines += ["# 320 調査", "", "工数は設計と実装の合計で、QA工程を含まない。", ""]
    lines += ["## スコープと除外", "", "- 対象: app/", "- 除外: 削除予定コード", ""]
    lines += ["## 項目", "", items]
    lines += ["## 該当なしと確認した観点", "", "- 動的なクラス生成は0件だった", ""]
    lines += ["## 確定できなかったこと", "", "1. 本番の配信設定 — 運用チームの確認が要る", ""]
    return "\n".join(lines)


@dataclass
class Workspace:
    """A workspace on disk that a test can bend one way at a time."""

    path: Path

    def write_findings(self, front_matter: dict[str, str] | None = None, items: str | None = None) -> None:
        text = document(front_matter or dict(SAMPLE_FRONT_MATTER), SAMPLE_ITEMS if items is None else items)
        (self.path / "findings.md").write_text(text, encoding="utf-8")

    def write_findings_text(self, text: str) -> None:
        (self.path / "findings.md").write_text(text, encoding="utf-8")

    def write_verdicts(self, text: str) -> None:
        (self.path / "verdicts.md").write_text(text, encoding="utf-8")

    def write_coverage(self, coverage: object) -> None:
        (self.path / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_paste(self) -> list[list[str]]:
        text = (self.path / "paste.tsv").read_text(encoding="utf-8")
        return [line.split("\t") for line in text.splitlines()]


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """A workspace that passes every check, for a test to break in exactly one place."""
    directory = tmp_path / "issue-probes" / "320"
    directory.mkdir(parents=True)
    space = Workspace(directory)
    space.write_findings()
    space.write_coverage(
        {
            "scope": ["app"],
            "searches": [{"id": "S1", "pattern": "value\\(forKey", "count": 3, "files": 2}],
            "codeSha": SAMPLE_FRONT_MATTER["codeSha"],
        }
    )
    return space


def _runner(cli: Path):
    def _run(directory: Path | str, *extra: str) -> subprocess.CompletedProcess[str]:
        argv = [sys.executable, str(cli), str(directory), *extra]
        return subprocess.run(argv, capture_output=True, text=True, timeout=30)

    return _run


@pytest.fixture
def run_check_items():
    """Run check_items.py as a subprocess against the given directory."""
    return _runner(CHECK_ITEMS_CLI)


@pytest.fixture
def run_export_items():
    """Run export_items.py as a subprocess against the given directory."""
    return _runner(EXPORT_ITEMS_CLI)

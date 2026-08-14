#!/usr/bin/env python3
"""
Accept or refuse the investigation before anyone exports it to the sheet.

findings.md leaves this repository as a spreadsheet paste, and the sheet fails
quietly: a value that swallowed a tab, a missing field, or a risk outside the
vocabulary shifts a column or empties a cell without complaining. This check is
the last place that can see it, and it runs against the document a person wrote
rather than against the export, so a problem is reported where it can be fixed.

It also holds the item numbers to what an already-pasted row depends on. A number
is never reused, so a gap in the allocated range has to be accounted for: the item
was retired, and verdicts.md is the only place that says what it claimed.

Nothing is written; findings.md stays the source of truth.

Exit codes:
- 0: the investigation holds. Totals and drift are reported for the caller to relay
- 1: at least one check failed; stdout carries every problem found in one pass
- 2: findings.md cannot be read; stderr carries JSON with an "action"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from columns import COLUMNS, parse_effort
from items import Item, ItemsError, next_item, read_items, verdicts
from paste import cell_problem


class CLIError(Exception):
    """An input error carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


def problem(check: str, detail: str, item: int | None = None) -> dict[str, Any]:
    return {"item": item, "check": check, "detail": detail}


def check_items(items: list[Item]) -> list[dict[str, Any]]:
    """Check every item for a readable heading, the declared fields, and its evidence."""
    problems: list[dict[str, Any]] = []
    for item in items:
        if item.malformed_heading:
            problems.append(
                problem(
                    "heading",
                    "見出しが `### <番号> [<リスク度>] <項目名>` の形ではありません。",
                    item=item.number,
                )
            )
        elif not item.title:
            problems.append(problem("heading", "見出しに項目名がありません。", item=item.number))
        problems.extend(_column_problems(item))
        for line in item.unknown:
            problems.append(problem("field", f"知らないラベルの箇条があります: {line}", item=item.number))
        for label in item.duplicated:
            problems.append(problem("field", f"{label} が2回以上あります。", item=item.number))
        for label in item.conflicting:
            problems.append(
                problem(
                    "field",
                    f"{label} にコロンの後の値とネストした箇条の両方があります。どちらか一方にしてください。",
                    item=item.number,
                )
            )
        if not item.has_evidence:
            problems.append(problem("evidence", "`#### 根拠` の節がありません。根拠を辿れません。", item=item.number))
    return problems


def _column_problems(item: Item) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for column in COLUMNS:
        # A malformed heading is already reported once. Reading the risk and the name out of
        # it and complaining about each would name the same mistake three times.
        if column.origin == "heading" and item.malformed_heading:
            continue
        value = item.cell(column)
        if value is None:
            problems.append(problem("field", f"{column.source} の箇条がありません。", item=item.number))
            continue
        if column.origin == "field" and not value:
            problems.append(
                problem(
                    "field",
                    f"{column.source} が空です。書くことが無い欄は「なし」と書いてください。",
                    item=item.number,
                )
            )
            continue
        if column.values and value not in column.values:
            allowed = " / ".join(column.values)
            problems.append(
                problem(
                    "enum", f"{column.source} が {value!r} です。{allowed} のいずれかにしてください。", item=item.number
                )
            )
        if column.unit and parse_effort(value, column.unit) is None:
            problems.append(
                problem(
                    "effort",
                    f"{column.source} から工数を読み取れません: {value!r}。"
                    f"先頭を「数値{column.unit}」で始めてください。",
                    item=item.number,
                )
            )
        broken = cell_problem(value)
        if broken is not None:
            problems.append(problem("cell", f"{column.source} に{broken}が入っています。", item=item.number))
    return problems


def check_numbering(items: list[Item], allocator: int, resolved: dict[int, str]) -> list[dict[str, Any]]:
    """Hold the item numbers to what an already-pasted sheet row depends on."""
    problems: list[dict[str, Any]] = []
    listed: list[int] = []
    for item in items:
        number = item.number
        if number in listed:
            problems.append(problem("numbering", f"項目番号 {number} が重複しています。", item=number))
        elif listed and number < listed[-1]:
            problems.append(
                problem(
                    "numbering",
                    f"項目番号 {number} が直前の {listed[-1]} より小さいです。昇順に並べてください。",
                    item=number,
                )
            )
        listed.append(number)

    reserved = set(listed) | set(resolved)
    beyond = sorted(number for number in reserved if number >= allocator)
    for number in beyond:
        problems.append(
            problem(
                "numbering",
                f"項目番号 {number} が nextItem ({allocator}) 以上です。"
                f"nextItem を {max(reserved) + 1} にしてください。",
                item=number,
            )
        )

    for number in range(1, allocator):
        if number not in listed and resolved.get(number) != "delete":
            problems.append(
                problem(
                    "retired",
                    f"項目番号 {number} が欠番ですが、verdicts.md に delete の評決がありません。"
                    "取り下げたなら、その項目が何を主張していたかを評決に残してください。",
                    item=number,
                )
            )
    return problems


def collect_info(items: list[Item], directory: Path, code_sha: str) -> list[str]:
    """Report the totals a reader would otherwise recompute by hand, plus any drift."""
    info: list[str] = []
    for column in COLUMNS:
        if not column.unit:
            continue
        known = [
            effort
            for effort in (parse_effort(item.cell(column) or "", column.unit) for item in items)
            if effort is not None
        ]
        if known:
            info.append(f"{column.source} の合計は {sum(known):g}{column.unit}（{len(known)}件）")
    for column in COLUMNS:
        if not column.values:
            continue
        counts = Counter(item.cell(column) for item in items)
        breakdown = " / ".join(f"{value} {counts.get(value, 0)}" for value in column.values)
        info.append(f"{column.source} の分布は {breakdown}")

    head = _head_sha(directory)
    if head is None:
        info.append("現在のコミットを取得できなかったため、調査時点との差は確認できていません")
    elif head != code_sha:
        info.append(f"調査時点の codeSha ({code_sha[:7]}) と現在の HEAD ({head[:7]}) が違います")
    info.extend(_coverage_info(directory / "coverage.json", code_sha))
    return info


def _coverage_info(path: Path, code_sha: str) -> list[str]:
    """Say whether the recorded counts still describe the commit under investigation."""
    if not path.is_file():
        return ["coverage.json がないため、件数の裏付けは記録されていません"]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["coverage.json を JSON として読めないため、件数の鮮度は確認できていません"]
    measured = document.get("codeSha")
    if not measured:
        return ["coverage.json に計測時のコミットがないため、件数の鮮度は確認できていません"]
    if measured != code_sha:
        return [f"件数の計測時のコミット ({measured[:7]}) が調査時点 ({code_sha[:7]}) と違います"]
    return []


def _head_sha(directory: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def run(directory: Path) -> tuple[int, dict[str, Any]]:
    if not directory.is_dir():
        raise CLIError(f"{directory} がありません。", "probe-issue の準備を先に実行してください。")

    findings = directory / "findings.md"
    front_matter, items = read_items(findings)
    allocator = next_item(front_matter, findings)

    verdicts_path = directory / "verdicts.md"
    resolved = verdicts(verdicts_path.read_text(encoding="utf-8")) if verdicts_path.is_file() else {}

    problems = check_items(items)
    problems += check_numbering(items, allocator, resolved)

    document: dict[str, Any] = {"ok": not problems, "items": len(items)}
    if problems:
        document["problems"] = problems
    info = collect_info(items, directory, front_matter["codeSha"])
    if info:
        document["info"] = info
    if not problems and not items:
        document["hint"] = "findings.md に項目がないため、シートへ貼るものはありません。"
    return (1 if problems else 0), document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check the investigation before it is exported to the sheet.")
    parser.add_argument("directory", help="Workspace directory, for example .tmp/issue-probes/320")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        code, document = run(Path(args.directory))
    except (CLIError, ItemsError) as error:
        json.dump({"error": error.message, "action": error.action}, sys.stderr, ensure_ascii=False, indent=2)
        sys.stderr.write("\n")
        return 2
    json.dump(document, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

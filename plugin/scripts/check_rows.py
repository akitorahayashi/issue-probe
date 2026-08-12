#!/usr/bin/env python3
"""
Accept or refuse the investigation workspace before anyone pastes it into the sheet.

The list in report.tsv leaves this repository by being pasted into a spreadsheet
that other platform teams read. A cell that swallowed a tab, a row with one column
too few, or a header that drifted from the sheet does not fail loudly there — it
shifts the columns and the mistake ships. This check is the last place that can
see it.

It also holds the link between a claim and its evidence: every item in the list
must have a section under findings/, and an item that disappeared from the list
must carry a delete verdict explaining where it went.

Nothing is written; report.tsv and the findings stay the source of truth.

Exit codes:
- 0: the workspace holds. Counts and totals are reported for the caller to relay
- 1: at least one check failed; stdout carries every problem found in one pass
- 2: the workspace cannot be read; stderr carries JSON with an "action"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from rows import RowsError, cell_problem, read_rows
from schema import Schema, SchemaError, load_schema, parse_effort
from sections import SectionError, documented_items, next_item, split_front_matter, verdicts


class CLIError(Exception):
    """An input error carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


def problem(check: str, detail: str, item: int | None = None, row: int | None = None) -> dict[str, Any]:
    return {"item": item, "row": row, "check": check, "detail": detail}


def check_header(rows: list[list[str]], schema: Schema) -> list[dict[str, Any]]:
    """Compare the header row against the declared sheet columns, position by position."""
    header = rows[0]
    expected = schema.headers
    if header == expected:
        return []
    if len(header) != len(expected):
        return [
            problem(
                "header",
                f"ヘッダの列数が {len(header)} で、schema.json の {len(expected)} と違います。",
                row=1,
            )
        ]
    return [
        problem("header", f"{index + 1}列目のヘッダが {actual!r} で、schema.json の {want!r} と違います。", row=1)
        for index, (actual, want) in enumerate(zip(header, expected))
        if actual != want
    ]


def check_cells(rows: list[list[str]], schema: Schema) -> list[dict[str, Any]]:
    """Check every data row for width, unsafe characters, and per-role values."""
    problems: list[dict[str, Any]] = []
    width = len(schema.headers)
    id_index = schema.id_index
    for offset, row in enumerate(rows[1:]):
        number = offset + 2
        if len(row) != width:
            problems.append(
                problem(
                    "width",
                    f"列数が {len(row)} で、宣言された {width} と違います。"
                    "セルにタブか改行（CR・LF）が入っている可能性があります。",
                    row=number,
                )
            )
            continue
        item = row[id_index].strip()
        item_number = int(item) if item.isdigit() else None
        for index, value in enumerate(row):
            broken = cell_problem(value)
            if broken is not None:
                problems.append(
                    problem(
                        "cell",
                        f"{index + 1}列目 ({schema.headers[index]}) に{broken}が入っています。",
                        item=item_number,
                        row=number,
                    )
                )
        problems.extend(_role_problems(row, schema, item_number, number))
    return problems


def _role_problems(row: list[str], schema: Schema, item: int | None, row_number: int) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    for index, column in enumerate(schema.columns):
        value = row[index].strip()
        if column.role == "id" and not value.isdigit():
            problems.append(problem("id", f"項目番号が {value!r} で、正の整数ではありません。", row=row_number))
        elif column.role == "enum" and value not in column.values:
            allowed = " / ".join(column.values)
            problems.append(
                problem(
                    "enum",
                    f"{column.header} が {value!r} です。{allowed} のいずれかにしてください。",
                    item=item,
                    row=row_number,
                )
            )
        elif column.role == "effort" and parse_effort(value, column.unit) is None:
            problems.append(
                problem(
                    "effort",
                    f"{column.header} から工数を読み取れません: {value!r}。"
                    f"先頭を「数値{column.unit}」で始めてください。",
                    item=item,
                    row=row_number,
                )
            )
    return problems


def check_numbering(rows: list[list[str]], schema: Schema, allocator: int) -> list[dict[str, Any]]:
    """Hold the item number to what an already-pasted sheet row depends on."""
    problems: list[dict[str, Any]] = []
    id_index = schema.id_index
    seen: list[int] = []
    for offset, row in enumerate(rows[1:]):
        if len(row) != len(schema.headers):
            continue
        value = row[id_index].strip()
        if not value.isdigit():
            continue
        number = int(value)
        if number in seen:
            problems.append(problem("numbering", f"項目番号 {number} が重複しています。", item=number, row=offset + 2))
        elif seen and number < seen[-1]:
            problems.append(
                problem(
                    "numbering",
                    f"項目番号 {number} が直前の {seen[-1]} より小さいです。昇順に並べてください。",
                    item=number,
                    row=offset + 2,
                )
            )
        if number >= allocator:
            problems.append(
                problem(
                    "numbering",
                    f"項目番号 {number} が nextItem ({allocator}) 以上です。",
                    item=number,
                    row=offset + 2,
                )
            )
        seen.append(number)
    return problems


def check_evidence(
    listed: list[int], documented: dict[int, list[str]], resolved: dict[int, str]
) -> list[dict[str, Any]]:
    """Keep every listed item traceable, and every retired item accounted for."""
    problems: list[dict[str, Any]] = []
    for number in listed:
        if number not in documented:
            problems.append(
                problem(
                    "evidence",
                    f"findings/ に `### {number}` の節がありません。根拠を辿れません。",
                    item=number,
                )
            )
    for number in sorted(documented):
        if number not in listed and resolved.get(number) != "delete":
            problems.append(
                problem(
                    "evidence",
                    "findings/ にありますが report.tsv にありません。"
                    "取り下げたなら verdicts.md に delete の評決を残してください。",
                    item=number,
                )
            )
    return problems


def collect_info(rows: list[list[str]], schema: Schema, directory: Path, code_sha: str) -> list[str]:
    """Report the totals a reader would otherwise recompute by hand, plus any drift."""
    info: list[str] = []
    body = [row for row in rows[1:] if len(row) == len(schema.headers)]
    for index in schema.indexes_with_role("effort"):
        column = schema.columns[index]
        values = [parse_effort(row[index].strip(), column.unit) for row in body]
        known = [value for value in values if value is not None]
        if known:
            total = sum(known)
            rendered = f"{total:g}{column.unit}"
            info.append(f"{column.header} の合計は {rendered}（{len(known)}件）")
    for index in schema.indexes_with_role("enum"):
        column = schema.columns[index]
        counts = Counter(row[index].strip() for row in body)
        breakdown = " / ".join(f"{value} {counts.get(value, 0)}" for value in column.values)
        info.append(f"{column.header} の分布は {breakdown}")

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

    schema = load_schema(directory / "schema.json")
    rows = read_rows(directory / "report.tsv")
    findings = directory / "findings.md"
    if not findings.is_file():
        raise CLIError(
            f"{findings} がありません。",
            "front matter と調査のスコープを findings.md に書いてください。",
        )
    front_matter, _ = split_front_matter(findings.read_text(encoding="utf-8"), findings)
    allocator = next_item(front_matter, findings)

    verdicts_path = directory / "verdicts.md"
    resolved = verdicts(verdicts_path.read_text(encoding="utf-8")) if verdicts_path.is_file() else {}
    documented = documented_items(directory / "findings")

    problems = check_header(rows, schema)
    problems += check_cells(rows, schema)
    problems += check_numbering(rows, schema, allocator)

    id_index = schema.id_index
    listed = [
        int(row[id_index].strip())
        for row in rows[1:]
        if len(row) == len(schema.headers) and row[id_index].strip().isdigit()
    ]
    problems += check_evidence(listed, documented, resolved)

    document: dict[str, Any] = {"ok": not problems, "items": len(listed)}
    if problems:
        document["problems"] = problems
    info = collect_info(rows, schema, directory, front_matter["codeSha"])
    if info:
        document["info"] = info
    return (1 if problems else 0), document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check the investigation workspace before it is pasted into the sheet."
    )
    parser.add_argument("directory", help="Workspace directory, for example .tmp/issue-probes/321")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        code, document = run(Path(args.directory))
    except (CLIError, RowsError, SchemaError, SectionError) as error:
        json.dump({"error": error.message, "action": error.action}, sys.stderr, ensure_ascii=False, indent=2)
        sys.stderr.write("\n")
        return 2
    json.dump(document, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

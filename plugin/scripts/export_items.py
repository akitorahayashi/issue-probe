#!/usr/bin/env python3
"""
Write the one file a person pastes into the shared sheet.

findings.md is the canonical list, and it is written to be read: one section per
item, one labelled field per column, and long enumerations kept as nested bullets.
The sheet needs the opposite shape — one line per item, one tab per column, no line
breaks anywhere — so the shape the sheet needs is derived here rather than
maintained by hand. Folding the nested bullets into `1. … 2. …` is this script's
work, not the writer's.

paste.tsv is a derivative and is rewritten on every run. Editing it changes nothing
about the investigation; findings.md is the file to edit. A run that cannot write it
removes the previous one, because a leftover export looks exactly like a current one
to the person about to paste it.

Exit codes:
- 0: paste.tsv was written; the returned fields are what the caller relays
- 1: findings.md carries a value the sheet refuses. Any earlier paste.tsv is removed
- 2: findings.md cannot be read; stderr carries JSON with an "action"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from columns import COLUMNS, HEADERS, parse_effort, value_problem
from items import Item, ItemsError, read_items
from paste import PasteError, render


class CLIError(Exception):
    """An input error carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


def build_rows(items: list[Item]) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """Turn every item into a sheet row, reporting each value its column refuses.

    The columns decide what they accept, so this asks the same question the check asks.
    Reading the rule from anywhere else would let the export write a value the check
    would have rejected.
    """
    rows: list[list[str]] = [list(HEADERS)]
    problems: list[dict[str, Any]] = []
    for item in items:
        row: list[str] = []
        for column in COLUMNS:
            value = item.cell(column)
            found = value_problem(column, value)
            if found is not None:
                check, detail = found
                problems.append({"item": item.number, "check": check, "detail": detail})
            row.append(value or "")
        rows.append(row)
    return rows, problems


def summarise(items: list[Item]) -> list[dict[str, Any]]:
    """List each item as the overview a reader scans before pasting."""
    effort = next((column for column in COLUMNS if column.unit), None)
    summary: list[dict[str, Any]] = []
    for item in items:
        entry: dict[str, Any] = {"number": item.number, "risk": item.risk, "title": item.title}
        if effort is not None:
            total = parse_effort(item.cell(effort) or "", effort.unit)
            if total is not None:
                entry["effort"] = f"{total:g}{effort.unit}"
        summary.append(entry)
    return summary


def run(directory: Path) -> tuple[int, dict[str, Any]]:
    if not directory.is_dir():
        raise CLIError(f"{directory} がありません。", "probe-issue の準備を先に実行してください。")

    _, items = read_items(directory / "findings.md")
    rows, problems = build_rows(items)
    path = directory / "paste.tsv"
    if problems:
        document: dict[str, Any] = {
            "ok": False,
            "items": len(items),
            "problems": problems,
            "hint": "check_items.py を実行して、findings.md の問題を全件確認してください。",
        }
        if path.is_file():
            path.unlink()
            document["removed"] = str(path)
        return 1, document

    path.write_text(render(rows), encoding="utf-8")
    return 0, {
        "ok": True,
        "path": str(path),
        "rows": len(items),
        "columns": len(HEADERS),
        "items": summarise(items),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Derive the sheet paste from findings.md.")
    parser.add_argument("directory", help="Workspace directory, for example .tmp/issue-probes/320")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        code, document = run(Path(args.directory))
    except (CLIError, ItemsError, PasteError) as error:
        json.dump({"error": error.message, "action": error.action}, sys.stderr, ensure_ascii=False, indent=2)
        sys.stderr.write("\n")
        return 2
    json.dump(document, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

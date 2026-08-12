"""
Read the report TSV the way a spreadsheet reads a paste.

Google Sheets splits pasted text on tabs and newlines and honours no quoting, so
this module reads with QUOTE_NONE: every physical line is one row and every tab
is one column break. That is deliberate. It means a cell that swallowed a tab or
a newline cannot hide as a quoted field — it surfaces as a row whose column count
is wrong, which is exactly what would happen in the sheet.

A carriage return is a row break too — the sheet ends a row on CR, LF, or CRLF
alike — so it is caught by the same column count rather than as a cell problem.

What a column count cannot catch is a character that stays inside the line and
still ruins the cell: a form feed, a vertical tab, or the Unicode line and
paragraph separators. Those are detected per cell.

This module is a library: it parses and raises, and never exits or writes.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

# Characters that ruin a cell without ending its row, so no column count reveals them.
BREAKING_CHARACTERS = {
    "\v": "垂直タブ (VT)",
    "\f": "改ページ (FF)",
    " ": "行区切り (LS)",
    " ": "段落区切り (PS)",
}


class RowsError(Exception):
    """A report.tsv that cannot be read, carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


def read_rows(path: Path) -> list[list[str]]:
    """Split report.tsv into rows exactly as a paste into the sheet would."""
    if not path.is_file():
        raise RowsError(
            f"{path} がありません。",
            "調査結果の一覧を report.tsv に書いてください。",
        )
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise RowsError(
            f"{path} が空です。",
            "ヘッダ行と1件以上の項目行を書いてください。",
        )
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="\t", quoting=csv.QUOTE_NONE)
    return [row for row in reader if row]


def cell_problem(value: str) -> str | None:
    """Name the character that would break a paste, or None when the cell is safe."""
    for character, label in BREAKING_CHARACTERS.items():
        if character in value:
            return label
    return None


def render_rows(rows: list[list[str]]) -> str:
    """Join rows back into TSV text, refusing any cell that would break the paste."""
    lines = []
    for index, row in enumerate(rows):
        for column, value in enumerate(row):
            if "\t" in value or "\n" in value or cell_problem(value) is not None:
                raise RowsError(
                    f"{index + 1}行目 {column + 1}列目のセルに、貼り付けを壊す文字が入っています。",
                    "セルからタブ・改行・復帰を取り除いてください。",
                )
        lines.append("\t".join(row))
    return "\n".join(lines) + "\n"

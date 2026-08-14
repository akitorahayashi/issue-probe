"""
Render the item list the way a spreadsheet reads a paste.

Google Sheets splits pasted text on tabs and newlines and honours no quoting, so a
single stray character inside a value does not fail loudly there — it shifts the
columns and the mistake ships. A tab or a line break ends a cell or a row outright;
a form feed, a vertical tab, or the Unicode line and paragraph separators ruin the
cell while staying inside its line. All of them are named before anything is written.

This module is a library: it validates and renders, and never exits or writes.
"""

from __future__ import annotations

# The separators are written as escapes rather than as themselves: str.splitlines ends a
# line on U+2028 and U+2029, so a literal one here would make this very file unreadable
# to any tool that splits it into lines.
BREAKING_CHARACTERS = {
    "\t": "タブ",
    "\n": "改行 (LF)",
    "\r": "復帰 (CR)",
    "\v": "垂直タブ (VT)",
    "\f": "改ページ (FF)",
    "\u2028": "行区切り (LS)",
    "\u2029": "段落区切り (PS)",
}


class PasteError(Exception):
    """A value that would break the paste, carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


def cell_problem(value: str) -> str | None:
    """Name the character that would break a paste, or None when the value is safe."""
    for character, label in BREAKING_CHARACTERS.items():
        if character in value:
            return label
    return None


def render(rows: list[list[str]]) -> str:
    """Join rows into TSV text, refusing any cell that would break the paste."""
    lines = []
    for index, row in enumerate(rows):
        for position, value in enumerate(row):
            broken = cell_problem(value)
            if broken is not None:
                raise PasteError(
                    f"{index + 1}行目 {position + 1}列目の値に{broken}が入っています。",
                    "貼り付けを壊す文字を取り除いてください。",
                )
        lines.append("\t".join(row))
    return "\n".join(lines) + "\n"

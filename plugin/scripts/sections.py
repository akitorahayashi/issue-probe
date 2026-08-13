"""
Read the front matter of findings.md and the per-item sections under findings/.

Evidence is split by investigation axis so that parallel investigators each own
one file. The link back to the list is the item number: every row of report.tsv
must have a `### <番号>` section somewhere under findings/, and that is what makes
a claim in the sheet traceable to the code that supports it.

Headings inside fenced code blocks are not sections. Evidence quotes command
output that can begin with `###`, and reading those as sections would invent
items that nobody wrote.

This module is a library: it parses and raises, and never exits or writes.
"""

from __future__ import annotations

import re
from pathlib import Path

FRONT_MATTER_KEYS = ("issue", "issueRepo", "codeRepo", "codeSha", "probedAt", "nextItem")

FENCE = re.compile(r"^\s*(```|~~~)")
ITEM_HEADING = re.compile(r"^###\s+(\d+)(?:\s|$)")


class SectionError(Exception):
    """Findings that cannot be read, carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


def split_front_matter(text: str, source: Path) -> tuple[dict[str, str], str]:
    """Separate the YAML front matter from the body, requiring every key the checks use."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SectionError(
            f"{source} に front matter がありません。",
            f"先頭を --- で開き、{' / '.join(FRONT_MATTER_KEYS)} を書いてください。",
        )
    try:
        closing = lines.index("---", 1)
    except ValueError as error:
        raise SectionError(
            f"{source} の front matter が閉じていません。",
            "--- で閉じてください。",
        ) from error

    values: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise SectionError(
                f"{source} の front matter に `キー: 値` でない行があります: {line}",
                "`キー: 値` の形に直してください。",
            )
        values[key.strip()] = value.strip()

    missing = [key for key in FRONT_MATTER_KEYS if key not in values]
    if missing:
        raise SectionError(
            f"{source} の front matter に {', '.join(missing)} がありません。",
            "不足しているキーを追加してください。",
        )
    return values, "\n".join(lines[closing + 1 :])


def next_item(front_matter: dict[str, str], source: Path) -> int:
    """Read nextItem as the positive integer the allocator needs it to be."""
    raw = front_matter["nextItem"]
    try:
        value = int(raw)
    except ValueError as error:
        raise SectionError(
            f"{source} の nextItem が整数ではありません: {raw!r}",
            "次に割り当てる項目番号を整数で書いてください。",
        ) from error
    if value < 1:
        raise SectionError(
            f"{source} の nextItem が {value} です。",
            "1以上の整数にしてください。",
        )
    return value


def item_numbers(text: str) -> list[int]:
    """List the item numbers this evidence file documents, ignoring fenced blocks."""
    numbers: list[int] = []
    inside_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        match = ITEM_HEADING.match(line)
        if match is not None:
            numbers.append(int(match.group(1)))
    return numbers


VERDICT_HEADING = re.compile(r"^###\s+(\d+)\s+(confirmed|revise|delete|unresolved)\b")


def verdicts(text: str) -> dict[int, str]:
    """Map each item number to its most recent verdict.

    Rounds are appended, so a later round overwrites an earlier one for the same
    item. Reading in file order and letting the last write win reproduces that.
    """
    latest: dict[int, str] = {}
    inside_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        match = VERDICT_HEADING.match(line)
        if match is not None:
            latest[int(match.group(1))] = match.group(2)
    return latest


def documented_items(directory: Path) -> dict[int, list[str]]:
    """Map each item number to the evidence files that document it."""
    documented: dict[int, list[str]] = {}
    if not directory.is_dir():
        return documented
    for path in sorted(directory.glob("*.md")):
        for number in item_numbers(path.read_text(encoding="utf-8")):
            documented.setdefault(number, []).append(path.name)
    return documented

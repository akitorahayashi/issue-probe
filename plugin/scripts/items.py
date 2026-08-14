"""
Read findings.md as the investigation it records: its front matter and its items.

findings.md is the only canonical file. One item is one
`### <番号> [<リスク度>] <項目名>` section: its labelled fields are what a sheet row
carries, and its `#### 根拠` subsection is the evidence that never leaves the
repository. Holding the list and the evidence apart meant writing the same claim
twice in two registers, and every revision had to reach both copies.

A field's value is either inline after the colon or a nested bullet list. The nested
form exists because a sheet cell cannot hold a line break: the writer keeps a list a
person can read, and this module folds it into `1. … 2. …` so nobody folds by hand.

Headings inside fenced blocks are not sections. Evidence quotes command output that
can begin with `###`, and reading those as sections would invent items nobody wrote.

This module is a library: it parses and raises, and never exits or writes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import columns
from columns import NUMBER, RISK, TITLE, Column

FRONT_MATTER_KEYS = ("issue", "issueRepo", "codeRepo", "codeSha", "probedAt", "nextItem")

FENCE = re.compile(r"^\s*(?P<ticks>`{3,}|~{3,})(?P<info>.*)$")
# A `### <数字>` heading opens an item even when the rest of it is malformed. Ignoring a
# heading the writer meant as an item would drop that item from the sheet in silence.
ITEM_CANDIDATE = re.compile(r"^###\s+(?P<number>\d+)(?P<rest>.*)$")
ITEM_HEADING = re.compile(r"^###\s+(?P<number>\d+)\s+\[(?P<risk>[^\]]*)\]\s*(?P<title>.*?)\s*$")
# Levels 1 to 3 close the item in hand; `####` does not, so `#### 根拠` stays inside it.
SECTION = re.compile(r"^#{1,3}\s+")
EVIDENCE_HEADING = re.compile(r"^####\s+根拠\s*$")
BULLET = re.compile(r"^-\s+")
FIELD = re.compile(r"^-\s+(?P<label>[^:：]+?)\s*[:：]\s*(?P<value>.*?)\s*$")
NESTED = re.compile(r"^\s+-\s+(?P<value>.+?)\s*$")

VERDICT_HEADING = re.compile(r"^###\s+(\d+)\s+(confirmed|revise|delete|unresolved)\b")


class ItemsError(Exception):
    """findings.md cannot be read, carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


@dataclass
class Item:
    """One `### <番号> [<リスク度>] <項目名>` section of findings.md."""

    number: int
    risk: str
    title: str
    malformed_heading: bool
    fields: dict[str, str]
    unknown: tuple[str, ...]
    duplicated: tuple[str, ...]
    conflicting: tuple[str, ...]
    has_evidence: bool

    def cell(self, column: Column) -> str | None:
        """The value this item puts in one sheet column, or None when it has none."""
        if column.origin == "field":
            return self.fields.get(column.source)
        if column.source == NUMBER:
            return str(self.number)
        if column.source == TITLE:
            return self.title
        if column.source == RISK:
            return self.risk
        raise AssertionError(f"column {column.source!r} names no part of an item heading")


def split_lines(text: str) -> list[str]:
    """Split on LF alone, keeping every other character inside the line that holds it.

    str.splitlines also ends a line on a vertical tab, a form feed, and the Unicode line
    and paragraph separators. Those are exactly the characters the paste check looks for,
    so splitting on them would hide the problem: the value would be quietly cut in half
    and the check would find nothing wrong with what remained.
    """
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def fenced(lines: Iterable[str]) -> Iterator[tuple[str, bool]]:
    """Pair each line with whether a fenced block holds it.

    A delimiter counts as held along with the block it opens or closes, so nothing a
    fence contains is read as document structure. Only a delimiter of the same
    character, at least as long as the one that opened the block, and carrying no info
    string closes it — otherwise a fence quoted inside a longer fence would end the
    block early.
    """
    opened: str | None = None
    for line in lines:
        match = FENCE.match(line)
        if match is None:
            yield line, opened is not None
            continue
        ticks = match.group("ticks")
        if opened is None:
            opened = ticks
        elif ticks[0] == opened[0] and len(ticks) >= len(opened) and not match.group("info").strip():
            opened = None
        yield line, True


def flatten(children: list[str]) -> str:
    """Fold a nested bullet list into the one line a sheet cell can hold."""
    return " ".join(f"{index}. {value}" for index, value in enumerate(children, start=1))


@dataclass
class _Draft:
    """An item being read, before its nested lists are folded."""

    number: int
    risk: str
    title: str
    malformed_heading: bool
    inline: dict[str, str] = field(default_factory=dict)
    nested: dict[str, list[str]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    duplicated: list[str] = field(default_factory=list)
    last_label: str | None = None
    reading_evidence: bool = False
    has_evidence: bool = False

    @classmethod
    def open(cls, line: str) -> _Draft:
        full = ITEM_HEADING.match(line)
        if full is not None:
            return cls(
                number=int(full.group("number")),
                risk=full.group("risk").strip(),
                title=full.group("title"),
                malformed_heading=False,
            )
        candidate = ITEM_CANDIDATE.match(line)
        assert candidate is not None
        return cls(
            number=int(candidate.group("number")),
            risk="",
            title=candidate.group("rest").strip(),
            malformed_heading=True,
        )

    def consume(self, line: str) -> None:
        if EVIDENCE_HEADING.match(line) is not None:
            self.reading_evidence = True
            self.last_label = None
            return
        if self.reading_evidence:
            if line.strip():
                self.has_evidence = True
            return
        nested = NESTED.match(line)
        if nested is not None and self.last_label is not None:
            self.nested.setdefault(self.last_label, []).append(nested.group("value"))
            return
        if BULLET.match(line) is None:
            return
        match = FIELD.match(line)
        label = match.group("label") if match is not None else None
        if label is None or label not in columns.FIELD_LABELS:
            self.unknown.append(line.strip())
            self.last_label = None
            return
        assert match is not None
        if label in self.inline:
            self.duplicated.append(label)
        else:
            self.order.append(label)
        self.inline[label] = match.group("value")
        self.last_label = label

    def build(self) -> Item:
        values: dict[str, str] = {}
        conflicting: list[str] = []
        for label in self.order:
            inline = self.inline[label]
            children = self.nested.get(label, [])
            if children and inline:
                conflicting.append(label)
                values[label] = inline
            elif children:
                values[label] = flatten(children)
            else:
                values[label] = inline
        return Item(
            number=self.number,
            risk=self.risk,
            title=self.title,
            malformed_heading=self.malformed_heading,
            fields=values,
            unknown=tuple(self.unknown),
            duplicated=tuple(self.duplicated),
            conflicting=tuple(conflicting),
            has_evidence=self.has_evidence,
        )


def parse_items(lines: list[str]) -> list[Item]:
    """Collect every item section, in the order findings.md lists them."""
    items: list[Item] = []
    draft: _Draft | None = None
    for line, held in fenced(lines):
        if held:
            continue
        if ITEM_CANDIDATE.match(line) is not None:
            if draft is not None:
                items.append(draft.build())
            draft = _Draft.open(line)
            continue
        if SECTION.match(line) is not None:
            if draft is not None:
                items.append(draft.build())
                draft = None
            continue
        if draft is not None:
            draft.consume(line)
    if draft is not None:
        items.append(draft.build())
    return items


def split_front_matter(text: str, source: Path) -> tuple[dict[str, str], list[str]]:
    """Separate the YAML front matter from the body, requiring every key the checks use."""
    lines = split_lines(text)
    if not lines or lines[0].strip() != "---":
        raise ItemsError(
            f"{source} に front matter がありません。",
            f"先頭を --- で開き、{' / '.join(FRONT_MATTER_KEYS)} を書いてください。",
        )
    try:
        closing = lines.index("---", 1)
    except ValueError as error:
        raise ItemsError(
            f"{source} の front matter が閉じていません。",
            "--- で閉じてください。",
        ) from error

    values: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ItemsError(
                f"{source} の front matter に `キー: 値` でない行があります: {line}",
                "`キー: 値` の形に直してください。",
            )
        values[key.strip()] = value.strip()

    missing = [key for key in FRONT_MATTER_KEYS if key not in values]
    if missing:
        raise ItemsError(
            f"{source} の front matter に {', '.join(missing)} がありません。",
            "不足しているキーを追加してください。",
        )
    return values, lines[closing + 1 :]


def next_item(front_matter: dict[str, str], source: Path) -> int:
    """Read nextItem as the positive integer the allocator needs it to be."""
    raw = front_matter["nextItem"]
    try:
        value = int(raw)
    except ValueError as error:
        raise ItemsError(
            f"{source} の nextItem が整数ではありません: {raw!r}",
            "次に割り当てる項目番号を整数で書いてください。",
        ) from error
    if value < 1:
        raise ItemsError(
            f"{source} の nextItem が {value} です。",
            "1以上の整数にしてください。",
        )
    return value


def read_items(path: Path) -> tuple[dict[str, str], list[Item]]:
    """Read findings.md into its front matter and its items."""
    if not path.is_file():
        raise ItemsError(
            f"{path} がありません。",
            "front matter と調査の項目を findings.md に書いてください。",
        )
    front_matter, body = split_front_matter(path.read_text(encoding="utf-8"), path)
    return front_matter, parse_items(body)


def verdicts(text: str) -> dict[int, str]:
    """Map each item number to its most recent verdict.

    Rounds are appended, so a later round overwrites an earlier one for the same
    item. Reading in file order and letting the last write win reproduces that.
    """
    latest: dict[int, str] = {}
    for line, held in fenced(split_lines(text)):
        if held:
            continue
        match = VERDICT_HEADING.match(line)
        if match is not None:
            latest[int(match.group(1))] = match.group(2)
    return latest

"""
The columns of the shared spreadsheet, and where each one is read from.

Every investigation fills the same table, so the layout is declared here once
rather than in each workspace. A workspace that declared its own layout also had
to be asked for it, and the answer never differed.

Three columns come from an item's heading and the rest from its labelled fields.
Keeping the number, the name, and the risk in the heading makes an editor's
outline the list itself: `### 2 [高] 番組表のチャンネルID取得` already says which
item it is, how bad it is, and what it concerns, without opening the section.

A column carrying `values` holds a closed vocabulary; a column carrying `unit`
holds a duration whose leading number is summed. No other role is needed, so
none is declared.

This module is a library: it declares and parses, and never exits or writes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The three parts of an item heading. Parsers key their heading values by these names,
# so a heading column below is resolved without a second mapping.
NUMBER = "番号"
TITLE = "項目名"
RISK = "リスク度"
HEADING_SOURCES = (NUMBER, TITLE, RISK)


@dataclass(frozen=True)
class Column:
    """One column of the sheet.

    `source` names the heading part or the field label the value comes from, and
    `header` is the string the sheet's header row carries. They are separate so the
    sheet can rename a header without touching a single workspace.
    """

    source: str
    header: str
    origin: str
    values: tuple[str, ...] = ()
    unit: str = ""


COLUMNS: tuple[Column, ...] = (
    Column(NUMBER, "No.", "heading"),
    Column(TITLE, "該当処理（概要）", "heading"),
    Column("該当箇所", "該当箇所（ファイル名/メソッド名/行数など）", "field"),
    Column("本来の経路", "本来経由すべき共通処理（Util・共通クラス）", "field"),
    Column("現状", "現状の実装内容", "field"),
    Column(RISK, "リスク度（高/中/低）", "heading", values=("高", "中", "低")),
    Column("想定される事象", "想定される事象", "field"),
    Column("影響範囲", "修正時の影響範囲（ファイルと機能名）", "field"),
    Column("工数", "修正時の工数", "field", unit="h"),
    Column("備考", "備考", "field"),
)

HEADERS: tuple[str, ...] = tuple(column.header for column in COLUMNS)
FIELD_LABELS: tuple[str, ...] = tuple(column.source for column in COLUMNS if column.origin == "field")


def parse_effort(value: str, unit: str) -> float | None:
    """Take the leading duration out of an effort value, or None when there is none.

    The value carries a breakdown after the total ("6h（設計: 3h/ 実装: 3h）"), so only
    the leading number is summed. Reading the whole value would double-count.
    """
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)\s*" + re.escape(unit), value)
    if match is None:
        return None
    return float(match.group(1))

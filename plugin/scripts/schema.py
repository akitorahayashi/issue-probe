"""
Read the spreadsheet column contract and interpret what each column means.

The shared sheet differs per investigation: one ticket tracked seven columns,
another ten, and the effort column has been written in hours in one and in
person-days in another. Rather than hard-coding a layout, every workspace
declares its own schema.json and the checks read the layout from there.

Column roles carry the checks that a bare header cannot:

- id     the immutable item number. Exactly one column has this role
- text   free prose. Only the cell-safety rules apply
- enum   a closed vocabulary such as 高 / 中 / 低
- effort a duration whose leading number can be totalled

This module is a library: it parses and raises, and never exits or writes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROLES = ("id", "text", "enum", "effort")
DEFAULT_EFFORT_UNIT = "h"


class SchemaError(Exception):
    """A schema.json that cannot be used, carrying an action for the user to fix."""

    def __init__(self, message: str, action: str) -> None:
        super().__init__(message)
        self.message = message
        self.action = action


@dataclass(frozen=True)
class Column:
    header: str
    role: str
    values: tuple[str, ...] = ()
    unit: str = DEFAULT_EFFORT_UNIT


@dataclass(frozen=True)
class Schema:
    columns: tuple[Column, ...]
    sheet: dict[str, Any]

    @property
    def headers(self) -> list[str]:
        return [column.header for column in self.columns]

    @property
    def id_index(self) -> int:
        for index, column in enumerate(self.columns):
            if column.role == "id":
                return index
        raise SchemaError(
            "schema.json に role が id の列がありません。",
            '項目番号を持つ列に "role": "id" を付けてください。',
        )

    def indexes_with_role(self, role: str) -> list[int]:
        return [index for index, column in enumerate(self.columns) if column.role == role]


def load_schema(path: Path) -> Schema:
    """Read schema.json and reject a layout the checks could not act on."""
    if not path.is_file():
        raise SchemaError(
            f"{path} がありません。",
            "シートの列構成を schema.json に宣言してください。",
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SchemaError(f"{path} を JSON として読めません: {error}", "JSON の構文を直してください。") from error
    if not isinstance(document, dict):
        raise SchemaError(f"{path} の最上位がオブジェクトではありません。", "オブジェクトに直してください。")

    raw_columns = document.get("columns")
    if not isinstance(raw_columns, list) or not raw_columns:
        raise SchemaError(
            f"{path} に columns がありません。",
            "シートのヘッダ行と同じ順序で columns を並べてください。",
        )

    columns = tuple(_column(entry, index, path) for index, entry in enumerate(raw_columns))
    id_columns = [column for column in columns if column.role == "id"]
    if len(id_columns) != 1:
        raise SchemaError(
            f"role が id の列が {len(id_columns)} 個あります。ちょうど1個にしてください。",
            '項目番号を持つ列だけに "role": "id" を付けてください。',
        )

    headers = [column.header for column in columns]
    duplicates = sorted({header for header in headers if headers.count(header) > 1})
    if duplicates:
        raise SchemaError(
            f"重複したヘッダがあります: {', '.join(duplicates)}",
            "シートのヘッダ行と同じになるよう、重複を解消してください。",
        )

    sheet = document.get("sheet", {})
    if not isinstance(sheet, dict):
        raise SchemaError(f"{path} の sheet がオブジェクトではありません。", "sheet をオブジェクトに直してください。")
    return Schema(columns=columns, sheet=sheet)


def _column(entry: Any, index: int, path: Path) -> Column:
    position = index + 1
    if not isinstance(entry, dict):
        raise SchemaError(
            f"{path} の columns[{index}] がオブジェクトではありません。",
            '各列を {"header": ..., "role": ...} の形にしてください。',
        )
    header = entry.get("header")
    if not isinstance(header, str) or not header:
        raise SchemaError(
            f"{position}列目に header がありません。",
            "シートのヘッダ文字列をそのまま header に入れてください。",
        )
    role = entry.get("role", "text")
    if role not in ROLES:
        raise SchemaError(
            f"{position}列目の role が不正です: {role!r}",
            f"role は {' / '.join(ROLES)} のいずれかにしてください。",
        )

    values: tuple[str, ...] = ()
    if role == "enum":
        raw_values = entry.get("values")
        if not isinstance(raw_values, list) or not raw_values or not all(isinstance(v, str) for v in raw_values):
            raise SchemaError(
                f"{position}列目 ({header}) は role が enum ですが values がありません。",
                "許容する値を values に文字列の配列で並べてください。",
            )
        values = tuple(raw_values)

    unit = entry.get("unit", DEFAULT_EFFORT_UNIT)
    if not isinstance(unit, str) or not unit:
        raise SchemaError(
            f"{position}列目 ({header}) の unit が文字列ではありません。",
            'unit は "h" や "人日" のような文字列にしてください。',
        )
    return Column(header=header, role=role, values=values, unit=unit)


def parse_effort(value: str, unit: str = DEFAULT_EFFORT_UNIT) -> float | None:
    """Take the leading duration out of an effort cell, or None when there is none.

    The cell carries a breakdown after the total ("6h（設計: 3h/ 実装: 3h）"), so only
    the leading number is summed. Reading the whole cell would double-count.
    """
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)\s*" + re.escape(unit), value)
    if match is None:
        return None
    return float(match.group(1))

"""
The document a person writes and the layout the code reads describe one contract.

The template tells the writer which fields an item carries; columns.py tells the
checks and the export which fields to look for. Nothing at runtime compares them,
so this is where a drift between the two has to fail.
"""

from __future__ import annotations

from columns import COLUMNS
from conftest import FIELD_ORDER, FINDINGS_TEMPLATE
from items import parse_items, split_front_matter


def filled_template() -> str:
    """The template with its heading placeholders resolved, as a writer would fill them."""
    text = FINDINGS_TEMPLATE.read_text(encoding="utf-8")
    return text.replace("<番号>", "2").replace("<高 | 中 | 低>", "高")


def test_the_sheet_layout_declares_the_fields_these_tests_spell_out():
    assert [column.source for column in COLUMNS if column.origin == "field"] == list(FIELD_ORDER)


def test_the_filled_in_template_parses_into_one_complete_item():
    front_matter, body = split_front_matter(filled_template(), FINDINGS_TEMPLATE)

    assert front_matter["nextItem"]
    items = parse_items(body)
    assert len(items) == 1
    item = items[0]
    assert not item.malformed_heading
    assert item.risk == "高"
    assert item.has_evidence
    assert not item.unknown
    assert list(item.fields) == list(FIELD_ORDER)


def test_the_template_writes_a_nested_list_where_one_is_expected():
    """The folding rule only exists because the template teaches the nested form."""
    _, body = split_front_matter(filled_template(), FINDINGS_TEMPLATE)

    item = parse_items(body)[0]
    assert item.fields["影響範囲"].startswith("1. ")
    assert " 2. " in item.fields["影響範囲"]

from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


def test_def_block_as_payload_supports_multiline_continuation() -> None:
    text = """Define topic
/DEF topic
/THEN Write summary
/FROM @topic
/DEF summary
/AS first line for @topic
second line of details
third line
"""
    steps = parse_dsl(text)
    as_text = steps[1].defs[0].as_text
    assert as_text == "first line for @topic\nsecond line of details\nthird line"


def test_inline_def_as_payload_supports_multiline_continuation() -> None:
    text = """Define topic
/DEF topic
/THEN Write summary
/FROM @topic
/DEF summary /AS first line for @topic
second line
"""
    steps = parse_dsl(text)
    assert steps[1].defs[0].as_text == "first line for @topic\nsecond line"


def test_multiline_as_continuation_stops_at_next_command() -> None:
    text = """Define topic
/DEF topic
/THEN Write summary
/FROM @topic
/DEF summary
/AS first line
second line
/TYPE str
"""
    steps = parse_dsl(text)
    spec = steps[1].defs[0]
    assert spec.as_text == "first line\nsecond line"
    assert spec.value_type == "str"


def test_empty_as_payload_after_continuation_resolution_is_parse_error() -> None:
    text = """Define topic
/DEF topic
/THEN Write summary
/FROM @topic
/DEF summary
/AS
"""
    with pytest.raises(ParseError, match="/AS requires description text"):
        parse_dsl(text)


def test_from_restrictions_still_apply_to_multiline_as_payload() -> None:
    text = """Define vars
/DEF a
/DEF b
/THEN Write output
/FROM @a
/DEF result
/AS use @a
and also @b
"""
    with pytest.raises(ParseError, match="not allowed by /FROM"):
        parse_dsl(text)

from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


def test_invalid_embedded_reference_name_in_instruction_fails_parse() -> None:
    with pytest.raises(ParseError, match="invalid variable name @1x"):
        parse_dsl("Write output for @1x")


def test_invalid_embedded_reference_name_in_as_payload_fails_parse() -> None:
    text = """Define vars
/DEF a
/THEN Write output
/FROM @a
/DEF result /AS combine @a with @bad-name
"""
    with pytest.raises(ParseError, match="invalid variable name @bad-name"):
        parse_dsl(text)


def test_email_like_text_is_not_parsed_as_variable_reference() -> None:
    steps = parse_dsl("Send note to person a@b.com\n/OUT done")
    assert len(steps) == 1

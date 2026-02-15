from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


def test_from_allows_embedded_references_in_text_and_as_payload() -> None:
    text = """Define inputs
/DEF topic
/THEN Write summary for @topic
/FROM @topic
/DEF summary /AS concise summary of @topic
"""
    steps = parse_dsl(text)
    assert len(steps) == 2
    assert steps[1].from_vars == ["topic"]
    assert steps[1].defs[0].as_text == "concise summary of @topic"


def test_from_rejects_instruction_reference_not_listed() -> None:
    text = """Define inputs
/DEF a
/DEF b
/THEN Compare @a with @b
/FROM @a
/OUT result
"""
    with pytest.raises(ParseError, match="not allowed by /FROM"):
        parse_dsl(text)


def test_from_rejects_as_payload_reference_not_listed() -> None:
    text = """Define inputs
/DEF a
/DEF b
/THEN Write output
/FROM @a
/DEF result /AS combine @a with @b
"""
    with pytest.raises(ParseError, match="not allowed by /FROM"):
        parse_dsl(text)


def test_references_are_unrestricted_when_from_is_omitted() -> None:
    text = """Define topic
/DEF topic
/THEN Write summary for @topic
/OUT concise output
"""
    steps = parse_dsl(text)
    assert len(steps) == 2
    assert steps[1].from_vars is None

from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


def test_def_defaults_to_nat_and_varname_as_text() -> None:
    steps = parse_dsl("Write output\n/DEF result")
    spec = steps[0].defs[0]
    assert spec.var_name == "result"
    assert spec.value_type == "nat"
    assert spec.as_text == "result"


def test_def_allows_inline_as_then_type_order() -> None:
    steps = parse_dsl("Write output\n/DEF score /AS confidence score /TYPE float")
    spec = steps[0].defs[0]
    assert spec.var_name == "score"
    assert spec.value_type == "float"
    assert spec.as_text == "confidence score"


def test_def_allows_multiline_block_type_and_as() -> None:
    text = """Write output
/DEF score
  /TYPE float
  /AS confidence score
"""
    steps = parse_dsl(text)
    spec = steps[0].defs[0]
    assert spec.var_name == "score"
    assert spec.value_type == "float"
    assert spec.as_text == "confidence score"


def test_def_allows_mixed_inline_and_multiline_commands() -> None:
    text = """Write output
/DEF answer /AS readable result
/TYPE str
"""
    steps = parse_dsl(text)
    spec = steps[0].defs[0]
    assert spec.value_type == "str"
    assert spec.as_text == "readable result"


@pytest.mark.parametrize(
    "dsl,err_substr",
    [
        ("Write output\n/DEF x /TYPE int /TYPE float", "duplicate /TYPE"),
        ("Write output\n/DEF x /AS first /AS second", "duplicate /AS"),
        ("Write output\n/DEF x /TYPE int\n/TYPE float", "duplicate /TYPE"),
        ("Write output\n/DEF x /AS first\n/AS second", "duplicate /AS"),
        ("Write output\n/DEF x /TYPE number", "invalid /TYPE value"),
        ("Write output\n/DEF x /TYPE", "/TYPE requires a value"),
        ("Write output\n/DEF x /AS", "/AS requires description text"),
        ("Write output\n/DEF", "/DEF requires a variable name"),
        (
            "Write output\n/DEF x unexpected",
            "invalid /DEF payload after variable name",
        ),
        ("Write output\n/TYPE int", "/TYPE is only valid inside a /DEF block"),
        ("Write output\n/AS desc", "/AS is only valid inside a /DEF block"),
    ],
)
def test_def_block_validation_errors(dsl: str, err_substr: str) -> None:
    with pytest.raises(ParseError, match=err_substr):
        parse_dsl(dsl)

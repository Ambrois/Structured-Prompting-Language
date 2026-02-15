from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


@pytest.mark.parametrize("name", ["x", "_x", "x1", "x_1"])
def test_valid_def_variable_names(name: str) -> None:
    steps = parse_dsl(f"Write output\n/DEF {name}")
    assert steps[0].defs[0].var_name == name


@pytest.mark.parametrize("name", ["1x", "x-y", "x.y"])
def test_invalid_def_variable_names(name: str) -> None:
    with pytest.raises(ParseError, match="invalid variable name"):
        parse_dsl(f"Write output\n/DEF {name}")


@pytest.mark.parametrize("from_item", ["@x", "@_x", "@x1", "@x_1"])
def test_valid_from_variable_references(from_item: str) -> None:
    name = from_item[1:]
    steps = parse_dsl(f"Define value\n/DEF {name}\n/THEN Use value\n/FROM {from_item}")
    assert steps[1].from_vars == [name]


@pytest.mark.parametrize(
    "dsl,err_substr",
    [
        ("Write output\n/FROM x", "/FROM expects variable references"),
        ("Write output\n/FROM @", "invalid variable name"),
        ("Write output\n/FROM @1x", "invalid variable name"),
        ("Write output\n/FROM @x-y", "invalid variable name"),
        ("Write output\n/FROM @x, y", "/FROM expects variable references"),
    ],
)
def test_invalid_from_variable_references(dsl: str, err_substr: str) -> None:
    with pytest.raises(ParseError, match=err_substr):
        parse_dsl(dsl)

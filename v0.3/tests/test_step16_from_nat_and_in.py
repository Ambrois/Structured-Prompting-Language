from __future__ import annotations

import sys
from pathlib import Path

import pytest


V03_DIR = Path(__file__).resolve().parents[1]
if str(V03_DIR) not in sys.path:
    sys.path.insert(0, str(V03_DIR))

from parser_v02 import ParseError, parse_dsl


def test_from_accepts_mixed_variable_and_nat_items() -> None:
    text = """Seed vars
/DEF notes
/THEN Use mixed inputs
/FROM @notes, key constraints, open tasks /IN @notes
/OUT done
"""
    steps = parse_dsl(text)
    step = steps[1]
    assert step.from_vars == ["notes"]
    assert step.from_items is not None
    assert [item.kind for item in step.from_items] == ["var", "nat", "nat"]
    assert step.from_items[1].value == "key constraints"
    assert step.from_items[1].scope_var == "ALL"
    assert step.from_items[2].value == "open tasks"
    assert step.from_items[2].scope_var == "notes"


@pytest.mark.parametrize(
    "dsl, err",
    [
        ("Seed\n/DEF notes\n/THEN x\n/FROM /IN @notes", "preceding natural-language description"),
        ("Seed\n/DEF notes\n/THEN x\n/FROM desc /IN", "exactly one variable reference"),
        ("Seed\n/DEF notes\n/THEN x\n/FROM desc /IN notes", "exactly one variable reference"),
        ("Seed\n/DEF notes\n/THEN x\n/FROM @notes /IN @notes", "cannot be applied to variable references"),
        ("Seed\n/DEF notes\n/THEN x\n/FROM desc /IN @missing", "undefined variable @missing"),
    ],
)
def test_from_in_errors(dsl: str, err: str) -> None:
    with pytest.raises(ParseError, match=err):
        parse_dsl(dsl)


@pytest.mark.parametrize(
    "dsl",
    [
        "Write\n/DEF ALL",
        "Write\n/DEF CHAT",
    ],
)
def test_reserved_builtins_are_read_only(dsl: str) -> None:
    with pytest.raises(ParseError, match="reserved read-only variable"):
        parse_dsl(dsl)

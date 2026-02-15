from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


def test_from_accepts_previously_defined_variable() -> None:
    text = """Create seed
/DEF seed
/THEN use seed
/FROM @seed
/OUT done
"""
    steps = parse_dsl(text)
    assert len(steps) == 2
    assert steps[1].from_vars == ["seed"]


@pytest.mark.parametrize(
    "dsl",
    [
        "Use missing\n/FROM @missing",
        "Use future\n/FROM @future\n/THEN define future\n/DEF future",
        "Use and define in same step\n/FROM @x\n/DEF x",
    ],
)
def test_from_rejects_undefined_or_forward_references(dsl: str) -> None:
    with pytest.raises(ParseError, match="/FROM references undefined variable"):
        parse_dsl(dsl)


def test_from_allows_redefined_variable_in_later_steps() -> None:
    text = """Create x
/DEF x
/THEN overwrite x
/DEF x
/THEN use x
/FROM @x
/OUT done
"""
    steps = parse_dsl(text)
    assert len(steps) == 3
    assert steps[2].from_vars == ["x"]

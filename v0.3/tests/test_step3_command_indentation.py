from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


def _normalized(steps: list) -> list:
    out = []
    for st in steps:
        out.append(
            {
                "index": st.index,
                "text": st.text,
                "from_vars": st.from_vars,
                "defs": [(d.var_name, d.value_type, d.as_text) for d in st.defs],
                "out_text": st.out_text,
                "commands": [(c.name, c.payload) for c in st.commands],
            }
        )
    return out


def test_indented_and_non_indented_commands_parse_equally() -> None:
    plain = """Seed variables.
/DEF topic
/DEF audience
/THEN Plan the response.
/FROM @topic, @audience
/DEF score /TYPE float /AS confidence score
/OUT concise summary
/THEN second step
/OUT include one caveat
"""
    indented = """Seed variables.
   /DEF topic
 /DEF audience
    /THEN Plan the response.
    /FROM @topic, @audience
  /DEF score /TYPE float /AS confidence score
     /OUT concise summary
    /THEN second step
      /OUT include one caveat
"""
    assert _normalized(parse_dsl(plain)) == _normalized(parse_dsl(indented))


def test_then_prefix_is_not_then_split_and_is_unknown_command_error() -> None:
    with pytest.raises(ParseError, match="unknown command /THENX"):
        parse_dsl("single step\n/THENX not-a-split")

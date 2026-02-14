from __future__ import annotations

import sys
from pathlib import Path


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import parse_dsl


def test_populates_from_defs_and_multiline_out() -> None:
    text = """Plan the response.
/FROM @topic, @audience
/DEF score /TYPE float /AS confidence score
/DEF rationale
/OUT concise summary
/OUT include one caveat
"""
    steps = parse_dsl(text)
    assert len(steps) == 1

    step = steps[0]
    assert step.from_vars == ["topic", "audience"]
    assert [d.var_name for d in step.defs] == ["score", "rationale"]
    assert [d.value_type for d in step.defs] == ["float", "nat"]
    assert [d.as_text for d in step.defs] == ["confidence score", None]
    assert step.out_text == "concise summary\ninclude one caveat"


def test_single_def_ast_shape() -> None:
    text = "Write result\n/DEF result /AS final answer /TYPE nat"
    steps = parse_dsl(text)
    assert len(steps) == 1
    assert len(steps[0].defs) == 1

    spec = steps[0].defs[0]
    assert spec.var_name == "result"
    assert spec.as_text == "final answer"
    assert spec.value_type == "nat"

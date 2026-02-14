from __future__ import annotations

import json
import sys
from pathlib import Path


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from runtime_v02 import run_dsl_text


def test_run_dsl_text_success() -> None:
    res = run_dsl_text(
        "Create x\n/DEF x /TYPE int",
        context={},
        call_model=lambda _: json.dumps({"error": 0, "out": "ok", "vars": {"x": 3}}),
    )
    assert res.ok is True
    assert res.outputs == ["ok"]
    assert res.vars_after == {"x": 3}
    assert res.error is None
    assert len(res.parsed_steps) == 1


def test_run_dsl_text_parse_error() -> None:
    res = run_dsl_text("/OUT only output", context={})
    assert res.ok is False
    assert res.error is not None
    assert "Parse error:" in res.error
    assert res.outputs == []


def test_run_dsl_text_execution_error() -> None:
    res = run_dsl_text(
        "Create x\n/DEF x /TYPE int",
        context={},
        call_model=lambda _: "not-json",
    )
    assert res.ok is False
    assert res.error is not None
    assert "Execution error:" in res.error
    assert len(res.parsed_steps) == 1

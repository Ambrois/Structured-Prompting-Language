from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from executor_v02 import execute_steps
from parser_v02 import parse_dsl


def test_runtime_contract_accepts_valid_response_without_defs() -> None:
    steps = parse_dsl("Write output\n/OUT concise")
    ctx, logs, outputs = execute_steps(
        steps,
        context={},
        call_model=lambda _: json.dumps({"error": 0, "out": "done"}),
    )
    assert ctx == {}
    assert outputs == ["done"]
    assert logs[0]["parsed_json"]["out"] == "done"


def test_runtime_contract_accepts_valid_response_with_defs() -> None:
    steps = parse_dsl("Create value\n/DEF x /TYPE int")
    ctx, _, outputs = execute_steps(
        steps,
        context={},
        call_model=lambda _: json.dumps({"error": 0, "out": "ok", "vars": {"x": 3}}),
    )
    assert ctx["x"] == 3
    assert outputs == ["ok"]


@pytest.mark.parametrize(
    "response,err_substr",
    [
        ("not json", "not valid JSON"),
        (json.dumps([]), "must be a JSON object"),
        (json.dumps({"out": "ok"}), "missing required keys"),
        (json.dumps({"error": 2, "out": "ok"}), "must be 0 or 1"),
        (json.dumps({"error": 0, "out": 123}), "'out' must be a JSON string"),
    ],
)
def test_runtime_contract_rejects_invalid_base_responses(
    response: str, err_substr: str
) -> None:
    steps = parse_dsl("Write output")
    with pytest.raises(ValueError, match=err_substr):
        execute_steps(steps, context={}, call_model=lambda _: response)


@pytest.mark.parametrize(
    "response,err_substr",
    [
        (json.dumps({"error": 0, "out": "ok"}), "include object key 'vars'"),
        (
            json.dumps({"error": 0, "out": "ok", "vars": {"y": 1}}),
            "missing /DEF values in vars",
        ),
    ],
)
def test_runtime_contract_rejects_invalid_def_payloads(
    response: str, err_substr: str
) -> None:
    steps = parse_dsl("Create value\n/DEF x")
    with pytest.raises(ValueError, match=err_substr):
        execute_steps(steps, context={}, call_model=lambda _: response)


def test_runtime_contract_rejects_error_equals_one_and_stops() -> None:
    steps = parse_dsl("Create value\n/DEF x")
    ctx: dict = {}
    with pytest.raises(RuntimeError, match="error=1"):
        execute_steps(
            steps,
            context=ctx,
            call_model=lambda _: json.dumps({"error": 1, "out": "failed", "vars": {"x": 1}}),
        )
    assert ctx == {}


def test_runtime_contract_parse_error_includes_raw_snippet() -> None:
    steps = parse_dsl("Write output")
    with pytest.raises(ValueError, match="Raw response starts with:"):
        execute_steps(steps, context={}, call_model=lambda _: "not-json")

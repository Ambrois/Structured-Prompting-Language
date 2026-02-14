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


def test_failed_step_does_not_partially_commit_its_vars() -> None:
    steps = parse_dsl("Create vars\n/DEF a /TYPE int\n/DEF b /TYPE int")
    ctx: dict = {}

    with pytest.raises(ValueError, match="expected int"):
        execute_steps(
            steps,
            context=ctx,
            call_model=lambda *_: json.dumps(
                {"error": 0, "out": "bad", "vars": {"a": 1, "b": "wrong"}}
            ),
        )

    assert ctx == {}


def test_execution_stops_after_runtime_failure_and_keeps_previous_step_vars() -> None:
    steps = parse_dsl(
        """Step one
/DEF a /TYPE int
/THEN Step two
/DEF b /TYPE int
/THEN Step three
/DEF c /TYPE int
"""
    )
    ctx: dict = {}
    responses = iter(
        [
            json.dumps({"error": 0, "out": "s1", "vars": {"a": 10}}),
            json.dumps({"error": 0, "out": "s2", "vars": {"b": "bad"}}),
            json.dumps({"error": 0, "out": "s3", "vars": {"c": 30}}),
        ]
    )
    calls = {"count": 0}

    def fake_model(*_: object) -> str:
        calls["count"] += 1
        return next(responses)

    with pytest.raises(ValueError, match="expected int"):
        execute_steps(steps, context=ctx, call_model=fake_model)

    assert calls["count"] == 2
    assert ctx == {"a": 10}


def test_execution_stops_on_error_equals_one_without_committing_failing_step() -> None:
    steps = parse_dsl(
        """Step one
/DEF a /TYPE int
/THEN Step two
/DEF b /TYPE int
/THEN Step three
/DEF c /TYPE int
"""
    )
    ctx: dict = {}
    responses = iter(
        [
            json.dumps({"error": 0, "out": "s1", "vars": {"a": 11}}),
            json.dumps({"error": 1, "out": "failed", "vars": {"b": 22}}),
            json.dumps({"error": 0, "out": "s3", "vars": {"c": 33}}),
        ]
    )
    calls = {"count": 0}

    def fake_model(*_: object) -> str:
        calls["count"] += 1
        return next(responses)

    with pytest.raises(RuntimeError, match="error=1"):
        execute_steps(steps, context=ctx, call_model=fake_model)

    assert calls["count"] == 2
    assert ctx == {"a": 11}

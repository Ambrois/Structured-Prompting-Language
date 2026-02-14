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


def test_end_to_end_successful_multistep_flow() -> None:
    dsl = """Choose topic
/DEF topic /TYPE str
/THEN Draft summary for @topic
/FROM @topic
/DEF summary /TYPE str /AS concise summary of @topic
/OUT readable output
"""
    steps = parse_dsl(dsl)
    prompts: list[str] = []
    responses = iter(
        [
            json.dumps({"error": 0, "out": "topic chosen", "vars": {"topic": "AI safety"}}),
            json.dumps(
                {
                    "error": 0,
                    "out": "summary ready",
                    "vars": {"summary": "AI safety is the practice of reducing model harms."},
                }
            ),
        ]
    )

    def fake_model(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    ctx, logs, outputs = execute_steps(steps, context={}, call_model=fake_model)
    assert outputs == ["topic chosen", "summary ready"]
    assert ctx["topic"] == "AI safety"
    assert "reducing model harms" in ctx["summary"]
    assert len(logs) == 2
    assert len(prompts) == 2
    assert "Draft summary for AI safety" in prompts[1]
    assert "- summary (str): concise summary of AI safety" in prompts[1]


def test_end_to_end_stops_after_runtime_error() -> None:
    dsl = """Step one
/DEF a /TYPE int
/THEN Step two
/DEF b /TYPE int
/THEN Step three
/DEF c /TYPE int
"""
    steps = parse_dsl(dsl)
    ctx: dict = {}
    responses = iter(
        [
            json.dumps({"error": 0, "out": "ok1", "vars": {"a": 1}}),
            "not json",
            json.dumps({"error": 0, "out": "ok3", "vars": {"c": 3}}),
        ]
    )
    calls = {"count": 0}

    def fake_model(_: str) -> str:
        calls["count"] += 1
        return next(responses)

    with pytest.raises(ValueError, match="not valid JSON"):
        execute_steps(steps, context=ctx, call_model=fake_model)

    assert calls["count"] == 2
    assert ctx == {"a": 1}

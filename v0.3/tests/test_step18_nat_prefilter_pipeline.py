from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


V03_DIR = Path(__file__).resolve().parents[1]
if str(V03_DIR) not in sys.path:
    sys.path.insert(0, str(V03_DIR))

from executor_v02 import execute_steps
from parser_v02 import parse_dsl


def test_nat_from_items_use_independent_prefilter_calls() -> None:
    dsl = """Seed notes
/DEF notes
/THEN Build answer
/FROM key tasks /IN @notes, user goals
/DEF answer
"""
    steps = parse_dsl(dsl)
    cheap_prompts: list[str] = []
    main_prompts: list[str] = []
    cheap_outputs = iter(["TASKS ONLY", "GOALS ONLY"])

    def fake_cheap(prompt: str) -> str:
        cheap_prompts.append(prompt)
        return next(cheap_outputs)

    responses = iter(
        [
            json.dumps({"error": 0, "out": "ok1", "vars": {"notes": "A\nB\nC"}}),
            json.dumps({"error": 0, "out": "ok2", "vars": {"answer": "done"}}),
        ]
    )

    def fake_main(prompt: str, _: dict) -> str:
        main_prompts.append(prompt)
        return next(responses)

    execute_steps(
        steps,
        context={},
        call_model=fake_main,
        chat_history=["hello"],
        cheap_model_call=fake_cheap,
    )

    assert len(cheap_prompts) == 2
    assert "Description:\nkey tasks" in cheap_prompts[0]
    assert "Scope (@notes):\nA\nB\nC" in cheap_prompts[0]
    assert "Description:\nuser goals" in cheap_prompts[1]
    assert "Scope (@ALL):\nChat history:" in cheap_prompts[1]

    assert "Inputs:\n- key tasks (from @notes): TASKS ONLY" in main_prompts[1]
    assert "- user goals (from @ALL): GOALS ONLY" in main_prompts[1]


def test_prefilter_failure_stops_execution() -> None:
    steps = parse_dsl("Seed\n/DEF notes\n/THEN Use\n/FROM x /IN @notes\n/OUT done")

    def fake_main(prompt: str, _: dict) -> str:
        if "Required variables:" in prompt:
            return json.dumps({"error": 0, "out": "ok", "vars": {"notes": "n"}})
        return json.dumps({"error": 0, "out": "ok"})

    def broken_cheap(_: str) -> str:
        raise RuntimeError("cheap failed")

    with pytest.raises(RuntimeError, match="cheap failed"):
        execute_steps(steps, context={}, call_model=fake_main, cheap_model_call=broken_cheap)

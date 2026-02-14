from __future__ import annotations

import json
import sys
from pathlib import Path


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from executor_v02 import build_step_prompt, execute_steps
from parser_v02 import parse_dsl


def test_prompt_interpolates_embedded_refs_and_appends_non_embedded_inputs() -> None:
    text = """Define inputs
/DEF topic
/DEF audience
/THEN Draft summary for @topic
/FROM @topic, @audience
/DEF summary /AS concise summary for @topic
/OUT readable language
"""
    steps = parse_dsl(text)
    step = steps[1]
    prompt = build_step_prompt(step, context={"topic": "AI safety", "audience": "engineers"})

    assert "Draft summary for AI safety" in prompt
    assert "Inputs:" in prompt
    assert "- audience: engineers" in prompt
    assert "- topic:" not in prompt
    assert "- summary (nat): concise summary for AI safety" in prompt
    assert "Output intent:\nreadable language" in prompt
    assert "Return JSON with keys:" in prompt


def test_prompt_without_from_uses_all_context_and_excludes_embedded_values() -> None:
    step = parse_dsl("Write answer for @topic\n/OUT short answer")[0]
    prompt = build_step_prompt(step, context={"topic": "pricing", "tone": "direct"})

    assert "Write answer for pricing" in prompt
    assert "Inputs:" in prompt
    assert "- tone: direct" in prompt
    assert "- topic:" not in prompt


def test_execute_steps_uses_built_prompts() -> None:
    steps = parse_dsl("One\n/THEN Two")
    seen_prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        seen_prompts.append(prompt)
        return json.dumps({"error": 0, "out": "ok"})

    _, logs, outputs = execute_steps(steps, context={}, call_model=fake_model)
    assert len(seen_prompts) == 2
    assert len(logs) == 2
    assert outputs == ["ok", "ok"]

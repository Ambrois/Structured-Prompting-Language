from __future__ import annotations

import sys
from pathlib import Path


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

import model_adapters_v02


def test_make_gemini_caller_forwards_model_and_timeout(monkeypatch) -> None:
    captured: dict = {}
    schema = {
        "type": "object",
        "properties": {"error": {"type": "integer"}, "out": {"type": "string"}},
        "required": ["error", "out"],
    }

    def fake_call_gemini(
        prompt: str, model: str, timeout_s: float, response_schema: dict
    ) -> str:
        captured["prompt"] = prompt
        captured["model"] = model
        captured["timeout_s"] = timeout_s
        captured["response_schema"] = response_schema
        return '{"error":0,"out":"ok"}'

    monkeypatch.setattr(model_adapters_v02, "call_gemini", fake_call_gemini)
    caller = model_adapters_v02.make_gemini_caller("gemini-2.5-flash", timeout_s=42)

    out = caller("hello", schema)
    assert out == '{"error":0,"out":"ok"}'
    assert captured == {
        "prompt": "hello",
        "model": "gemini-2.5-flash",
        "timeout_s": 42,
        "response_schema": schema,
    }

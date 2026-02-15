from __future__ import annotations

import sys
from pathlib import Path


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from executor_v02 import execute_steps
from parser_v02 import parse_dsl


def test_import_and_parse_smoke() -> None:
    steps = parse_dsl("Write a one-line greeting.")
    assert len(steps) == 1
    assert steps[0].index == 0
    assert steps[0].text == "Write a one-line greeting."


def test_then_splits_steps_smoke() -> None:
    text = "First step\n  /THEN second step"
    steps = parse_dsl(text)
    assert len(steps) == 2
    assert steps[0].text == "First step"
    assert steps[1].text == "second step"


def test_executor_stub_smoke() -> None:
    steps = parse_dsl("Only step")
    ctx, logs, outputs = execute_steps(steps, context={})
    assert ctx == {}
    assert len(logs) == 1
    assert outputs == ["stub output for step 0"]

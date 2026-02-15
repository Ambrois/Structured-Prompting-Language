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


def _run_single_def(type_name: str, value: object) -> dict:
    steps = parse_dsl(f"Create value\n/DEF x /TYPE {type_name}")
    ctx: dict = {}
    execute_steps(
        steps,
        context=ctx,
        call_model=lambda *_: json.dumps({"error": 0, "out": "ok", "vars": {"x": value}}),
    )
    return ctx


@pytest.mark.parametrize("value", [0, -1, 7])
def test_int_accepts_json_integers(value: int) -> None:
    ctx = _run_single_def("int", value)
    assert ctx["x"] == value


@pytest.mark.parametrize("value", [1.0, 1.2, "1", True, None])
def test_int_rejects_non_integer_values(value: object) -> None:
    with pytest.raises(ValueError, match="expected int|cannot be null"):
        _run_single_def("int", value)


@pytest.mark.parametrize("value", [1, 1.2, -4.5])
def test_float_accepts_json_numbers(value: float) -> None:
    ctx = _run_single_def("float", value)
    assert ctx["x"] == value


@pytest.mark.parametrize("value", ["1.2", True, None])
def test_float_rejects_non_number_values(value: object) -> None:
    with pytest.raises(ValueError, match="expected float|cannot be null"):
        _run_single_def("float", value)


@pytest.mark.parametrize("value", [True, False])
def test_bool_accepts_json_booleans(value: bool) -> None:
    ctx = _run_single_def("bool", value)
    assert ctx["x"] is value


@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_bool_rejects_non_boolean_values(value: object) -> None:
    with pytest.raises(ValueError, match="expected bool|cannot be null"):
        _run_single_def("bool", value)


@pytest.mark.parametrize("type_name", ["nat", "str"])
def test_nat_and_str_accept_strings(type_name: str) -> None:
    ctx = _run_single_def(type_name, "text")
    assert ctx["x"] == "text"


@pytest.mark.parametrize("type_name", ["nat", "str"])
@pytest.mark.parametrize("value", [4, False, None])
def test_nat_and_str_reject_non_string_values(type_name: str, value: object) -> None:
    with pytest.raises(ValueError, match="expected .*string|cannot be null"):
        _run_single_def(type_name, value)

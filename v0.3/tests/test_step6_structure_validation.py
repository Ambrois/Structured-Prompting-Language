from __future__ import annotations

import sys
from pathlib import Path

import pytest


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

from parser_v02 import ParseError, parse_dsl


def test_instruction_before_commands_is_valid() -> None:
    steps = parse_dsl("Draft output\n/OUT short answer")
    assert len(steps) == 1
    assert steps[0].text == "Draft output"


def test_non_command_text_after_commands_is_parse_error() -> None:
    with pytest.raises(ParseError, match="instruction text must appear before commands"):
        parse_dsl("Draft output\n/DEF x\nAdd another sentence")


def test_step_with_only_commands_is_parse_error() -> None:
    with pytest.raises(ParseError, match="instruction text is required before commands"):
        parse_dsl("/OUT short answer")


def test_blank_lines_after_commands_are_allowed() -> None:
    steps = parse_dsl("Draft output\n/OUT short answer\n\n   ")
    assert len(steps) == 1
    assert steps[0].out_text == "short answer\n\n   "


def test_then_step_without_instruction_is_parse_error() -> None:
    with pytest.raises(ParseError, match="instruction text is required before commands"):
        parse_dsl("First step\n/THEN\n/OUT short answer")


def test_out_supports_multiline_payload_continuation() -> None:
    steps = parse_dsl("Draft output\n/OUT short answer\nadd one caveat")
    assert len(steps) == 1
    assert steps[0].out_text == "short answer\nadd one caveat"


def test_out_continuation_stops_when_new_command_begins() -> None:
    steps = parse_dsl("Draft output\n/OUT short answer\nmore detail\n/DEF x")
    assert len(steps) == 1
    assert steps[0].out_text == "short answer\nmore detail"
    assert [d.var_name for d in steps[0].defs] == ["x"]

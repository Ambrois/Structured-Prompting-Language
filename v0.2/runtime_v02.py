from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from executor_v02 import ModelCall, execute_steps
from parser_v02 import ParseError, steps_to_dicts, parse_dsl


@dataclass
class RunResult:
    ok: bool
    outputs: List[str]
    logs: List[Dict[str, Any]]
    vars_after: Dict[str, Any]
    parsed_steps: List[Dict[str, Any]]
    error: Optional[str] = None


def run_dsl_text(
    text: str,
    context: Dict[str, Any],
    call_model: Optional[ModelCall] = None,
) -> RunResult:
    """
    App-facing helper for parse + execute.
    Returns structured success/error output without raising into the UI loop.
    """
    try:
        steps = parse_dsl(text)
    except ParseError as exc:
        return RunResult(
            ok=False,
            outputs=[],
            logs=[],
            vars_after=dict(context),
            parsed_steps=[],
            error=f"Parse error: {exc}",
        )

    ctx = dict(context)
    try:
        ctx, logs, outputs = execute_steps(steps, context=ctx, call_model=call_model)
    except Exception as exc:  # runtime/model errors are surfaced to UI
        return RunResult(
            ok=False,
            outputs=[],
            logs=[],
            vars_after=dict(context),
            parsed_steps=steps_to_dicts(steps),
            error=f"Execution error: {exc}",
        )

    return RunResult(
        ok=True,
        outputs=outputs,
        logs=logs,
        vars_after=ctx,
        parsed_steps=steps_to_dicts(steps),
        error=None,
    )

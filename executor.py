from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from example_parser import Step
from gemini_client import call_gemini


IGNORED_FROM_NOTE = (
    "NOTE: Non-variable /FROM items ignored (future: functions + NL retrieval)."
)


def _is_variable_ref(token: str) -> bool:
    if not token.startswith("@"):
        return False
    name = token[1:].strip()
    if name == "":
        return False
    if "(" in name or ")" in name:
        return False
    return True


def _format_value(val: Any) -> str:
    if isinstance(val, str):
        return val
    return json.dumps(val, indent=2, ensure_ascii=False)


def _format_history(history: List[Dict[str, Any]]) -> str:
    if not history:
        return ""
    lines: List[str] = []
    for msg in history:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_required_outputs_section(st: Step) -> str:
    output_lines: List[str] = []
    if st.as_vars:
        if st.out_items and len(st.out_items) == len(st.as_vars):
            for var, desc in zip(st.as_vars, st.out_items):
                output_lines.append(f"- {var}: {desc}")
        elif st.out_items:
            for var in st.as_vars:
                output_lines.append(f"- {var}")
            for desc in st.out_items:
                output_lines.append(f"- (description) {desc}")
        else:
            for var in st.as_vars:
                output_lines.append(f"- {var}")
    return "\n".join(output_lines) if output_lines else "None"


def _build_prompt(
    st: Step, resolved_inputs: Dict[str, Any], history: List[Dict[str, Any]] | None
) -> str:
    has_inputs = bool(resolved_inputs)
    has_history = bool(history)
    has_out = st.out_items is not None
    has_as = bool(st.as_vars)

    blocks: List[str] = []
    instruction = st.text.strip()
    has_other_blocks = has_inputs or has_history or has_out or has_as
    if instruction:
        if has_other_blocks:
            blocks.append(f"Instruction:\n{instruction}")
        else:
            blocks.append(instruction)

    if has_history:
        history_section = _format_history(history or [])
        if history_section:
            blocks.append(f"Chat history:\n{history_section}")

    if has_inputs:
        inputs_section = "\n".join(
            [f"- {k}: {_format_value(v)}" for k, v in resolved_inputs.items()]
        )
        blocks.append(f"Inputs:\n{inputs_section}")

    if has_as:
        outputs_section = _build_required_outputs_section(st)
        blocks.append(f"Required outputs:\n{outputs_section}")
        blocks.append("Return JSON only.")
    elif has_out:
        desc = st.out_items[0] if st.out_items else ""
        blocks.append(f"Output:\n{desc}" if desc else "Output:")

    return "\n\n".join(blocks).strip()


def _coerce_output_text(parsed_json: Any) -> str:
    if isinstance(parsed_json, dict) and "output" in parsed_json:
        out_val = parsed_json["output"]
        if isinstance(out_val, str):
            return out_val
        return json.dumps(out_val, indent=2, ensure_ascii=False)
    return json.dumps(parsed_json, indent=2, ensure_ascii=False)


def _resolve_from_items(
    st: Step, context: Dict[str, Any]
) -> tuple[Dict[str, Any], List[str]]:
    notes: List[str] = []
    resolved_inputs: Dict[str, Any] = {}

    if st.from_items:
        ignored_non_vars = []
        for item in st.from_items:
            t = item.strip()
            if _is_variable_ref(t):
                name = t[1:].strip()
                if name not in context:
                    raise ValueError(
                        f"Step {st.index} (line {st.start_line_no}): missing variable {t!r}"
                    )
                resolved_inputs[name] = context[name]
            else:
                if t != "":
                    ignored_non_vars.append(t)
        if ignored_non_vars:
            notes.append(IGNORED_FROM_NOTE)

    return resolved_inputs, notes


def execute_steps_stub(
    steps: List[Step],
    context: Dict[str, Any],
    timeout_s: float | None = None,
    chat_history: List[Dict[str, Any]] | None = None,
    model: str | None = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """
    Stub executor.

    Returns:
      - updated context
      - per-step logs
      - list of outputs from steps without /AS (for UI concatenation)
    """
    logs: List[Dict[str, Any]] = []
    non_var_outputs: List[str] = []

    for st in steps:
        resolved_inputs, notes = _resolve_from_items(st, context)

        if st.as_vars:
            output = {var: f"stub value for {var}" for var in st.as_vars}
            raw_response = json.dumps(output)
            for var, val in output.items():
                context[var] = val
        else:
            output = f"stub output for step {st.index}"
            raw_response = output
            non_var_outputs.append(output)

        logs.append(
            {
                "step_index": st.index,
                "start_line_no": st.start_line_no,
                "text": st.text,
                "from_items": st.from_items,
                "resolved_inputs": resolved_inputs,
                "out_items": st.out_items,
                "as_vars": st.as_vars,
                "notes": notes,
                "raw_response": raw_response,
                "parsed_json": output,
            }
        )

    return context, logs, non_var_outputs


def execute_steps(
    steps: List[Step],
    context: Dict[str, Any],
    timeout_s: float | None = None,
    chat_history: List[Dict[str, Any]] | None = None,
    model: str | None = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """
    Gemini-backed executor.

    Returns:
      - updated context
      - per-step logs
      - list of outputs from steps without /AS (for UI concatenation)
    """
    logs: List[Dict[str, Any]] = []
    non_var_outputs: List[str] = []

    for st in steps:
        resolved_inputs, notes = _resolve_from_items(st, context)

        history_ctx = chat_history if st.from_items is None else None
        prompt = _build_prompt(st, resolved_inputs, history_ctx)
        raw_response = call_gemini(prompt, model=model, timeout_s=timeout_s)

        if st.as_vars:
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Step {st.index} (line {st.start_line_no}): invalid JSON response: {raw_response}"
                ) from e

            if not isinstance(parsed, dict):
                raise ValueError(
                    f"Step {st.index} (line {st.start_line_no}): expected JSON object, got {type(parsed).__name__}"
                )

            missing = [v for v in st.as_vars if v not in parsed]
            if missing:
                raise ValueError(
                    f"Step {st.index} (line {st.start_line_no}): missing keys in response: {missing}"
                )
            for var in st.as_vars:
                context[var] = parsed[var]
            parsed_json: Any = parsed
        else:
            parsed_json = raw_response
            non_var_outputs.append(raw_response)

        logs.append(
            {
                "step_index": st.index,
                "start_line_no": st.start_line_no,
                "text": st.text,
                "from_items": st.from_items,
                "resolved_inputs": resolved_inputs,
                "out_items": st.out_items,
                "as_vars": st.as_vars,
                "notes": notes,
                "prompt": prompt,
                "history_included": history_ctx is not None,
                "raw_response": raw_response,
                "parsed_json": parsed_json,
            }
        )

    return context, logs, non_var_outputs

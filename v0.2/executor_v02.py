from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from parser_v02 import Step


ModelCall = Callable[[str], str]
_REF_PATTERN = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")


def _render_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _extract_refs(text: str) -> set[str]:
    return set(_REF_PATTERN.findall(text or ""))


def _interpolate(text: str, values: Dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in values:
            return _render_value(values[name])
        return match.group(0)

    return _REF_PATTERN.sub(repl, text or "")


def _resolve_accessible_inputs(step: Step, context: Dict[str, Any]) -> Dict[str, Any]:
    if step.from_vars is None:
        return dict(context)
    return {name: context[name] for name in step.from_vars if name in context}


def build_step_prompt(step: Step, context: Dict[str, Any]) -> str:
    accessible = _resolve_accessible_inputs(step, context)
    embedded: set[str] = set()
    embedded.update(_extract_refs(step.text))
    for spec in step.defs:
        embedded.update(_extract_refs(spec.as_text or ""))

    instruction = _interpolate(step.text, accessible).strip()
    blocks: List[str] = [f"Instruction:\n{instruction}" if instruction else "Instruction:"]

    extra_inputs = [name for name in accessible if name not in embedded]
    if extra_inputs:
        inputs_lines = "\n".join(
            f"- {name}: {_render_value(accessible[name])}" for name in extra_inputs
        )
        blocks.append(f"Inputs:\n{inputs_lines}")

    if step.defs:
        required_lines: List[str] = []
        for spec in step.defs:
            desc = _interpolate(spec.as_text or spec.var_name, accessible)
            required_lines.append(f"- {spec.var_name} ({spec.value_type}): {desc}")
        blocks.append("Required variables:\n" + "\n".join(required_lines))

    if step.out_text is not None:
        blocks.append(f"Output intent:\n{step.out_text}")

    blocks.append(
        "Output format requirements:\n"
        "- Respond with ONLY a JSON object.\n"
        "- Do not wrap JSON in markdown/code fences.\n"
        "- Keys required in every response: error, out.\n"
        "- error must be 0 or 1.\n"
        "- out must be a natural-language JSON string."
    )
    if step.defs:
        blocks.append(
            "Also include:\n"
            "- vars: JSON object containing every required variable by exact name."
        )
        sample_vars = ", ".join([f'"{spec.var_name}": <{spec.value_type}>' for spec in step.defs])
        blocks.append(
            "Example JSON shape:\n"
            f'{{"error": 0, "out": "done", "vars": {{{sample_vars}}}}}'
        )
    else:
        blocks.append('Example JSON shape:\n{"error": 0, "out": "done"}')

    return "\n\n".join(blocks).strip()


def _default_stub_response(step: Step) -> str:
    payload: Dict[str, Any] = {
        "error": 0,
        "out": f"stub output for step {step.index}",
    }
    if step.defs:
        payload["vars"] = {spec.var_name: f"stub value for {spec.var_name}" for spec in step.defs}
    return json.dumps(payload)


def _parse_runtime_response(raw_response: str, step: Step) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        snippet = raw_response.strip().replace("\n", "\\n")
        if len(snippet) > 220:
            snippet = snippet[:220] + "..."
        raise ValueError(
            f"Step {step.index} (line {step.start_line_no}): model response is not valid JSON. Raw response starts with: {snippet!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            f"Step {step.index} (line {step.start_line_no}): model response must be a JSON object"
        )

    if "error" not in parsed or "out" not in parsed:
        raise ValueError(
            f"Step {step.index} (line {step.start_line_no}): response missing required keys 'error' and/or 'out'"
        )

    error_val = parsed["error"]
    if error_val not in (0, 1):
        raise ValueError(
            f"Step {step.index} (line {step.start_line_no}): 'error' must be 0 or 1"
        )

    out_val = parsed["out"]
    if not isinstance(out_val, str):
        raise ValueError(
            f"Step {step.index} (line {step.start_line_no}): 'out' must be a JSON string"
        )

    if step.defs:
        vars_val = parsed.get("vars")
        if not isinstance(vars_val, dict):
            raise ValueError(
                f"Step {step.index} (line {step.start_line_no}): response must include object key 'vars'"
            )
        missing = [spec.var_name for spec in step.defs if spec.var_name not in vars_val]
        if missing:
            raise ValueError(
                f"Step {step.index} (line {step.start_line_no}): missing /DEF values in vars: {missing}"
            )

    if error_val == 1:
        raise RuntimeError(
            f"Step {step.index} (line {step.start_line_no}): model returned error=1"
        )

    return parsed


def _validate_def_value(step: Step, var_name: str, type_name: str, value: Any) -> None:
    if value is None:
        raise ValueError(
            f"Step {step.index} (line {step.start_line_no}): /DEF value for '{var_name}' cannot be null"
        )

    t = type_name.lower()
    if t in {"nat", "str"}:
        if not isinstance(value, str):
            raise ValueError(
                f"Step {step.index} (line {step.start_line_no}): '{var_name}' expected {t} (string)"
            )
        return

    if t == "int":
        if type(value) is not int:
            raise ValueError(
                f"Step {step.index} (line {step.start_line_no}): '{var_name}' expected int"
            )
        return

    if t == "float":
        if type(value) not in {int, float}:
            raise ValueError(
                f"Step {step.index} (line {step.start_line_no}): '{var_name}' expected float"
            )
        return

    if t == "bool":
        if type(value) is not bool:
            raise ValueError(
                f"Step {step.index} (line {step.start_line_no}): '{var_name}' expected bool"
            )
        return

    raise ValueError(
        f"Step {step.index} (line {step.start_line_no}): unsupported /TYPE '{type_name}'"
    )


def execute_steps(
    steps: List[Step],
    context: Dict[str, Any],
    call_model: Optional[ModelCall] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """Execute steps with prompt construction and model-call injection support."""
    logs: List[Dict[str, Any]] = []
    visible_outputs: List[str] = []

    for st in steps:
        prompt = build_step_prompt(st, context)
        if call_model is None:
            response = _default_stub_response(st)
        else:
            response = call_model(prompt)

        parsed = _parse_runtime_response(response, st)

        staged_updates: Dict[str, Any] = {}
        if st.defs:
            vars_payload = parsed["vars"]
            for spec in st.defs:
                value = vars_payload[spec.var_name]
                _validate_def_value(st, spec.var_name, spec.value_type, value)
                staged_updates[spec.var_name] = value

        # Commit only after all values in this step are validated.
        context.update(staged_updates)

        visible_outputs.append(parsed["out"])
        logs.append(
            {
                "step_index": st.index,
                "start_line_no": st.start_line_no,
                "text": st.text,
                "prompt": prompt,
                "raw_response": response,
                "parsed_json": parsed,
                "staged_updates": staged_updates,
            }
        )

    return context, logs, visible_outputs

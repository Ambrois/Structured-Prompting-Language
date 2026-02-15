from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

from parser_v02 import FromItem, Step


class ResponseSchema(TypedDict):
    type: str
    properties: Dict[str, Any]
    required: List[str]


ModelCall = Callable[[str, ResponseSchema], str]
CheapModelCall = Callable[[str], str]
_REF_PATTERN = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
_BUILTIN_VAR_NAMES = {"ALL", "CHAT"}


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


def _render_chat_history_text(chat_history: List[str]) -> str:
    lines = [line for line in chat_history if isinstance(line, str) and line.strip()]
    if not lines:
        return ""
    return "\n\n".join(lines)


def _build_builtin_values(context: Dict[str, Any], chat_history: List[str]) -> Dict[str, str]:
    chat_text = _render_chat_history_text(chat_history)

    vars_lines: List[str] = []
    for name, value in context.items():
        if name in _BUILTIN_VAR_NAMES:
            continue
        vars_lines.append(f"- {name}: {_render_value(value)}")

    all_parts: List[str] = []
    if chat_text:
        all_parts.append(f"Chat history:\n{chat_text}")
    if vars_lines:
        all_parts.append("Variables:\n" + "\n".join(vars_lines))

    return {
        "CHAT": chat_text,
        "ALL": "\n\n".join(all_parts).strip(),
    }


def build_step_prompt(
    step: Step,
    context: Dict[str, Any],
    nat_inputs: Optional[List[Tuple[str, str]]] = None,
) -> str:
    accessible = _resolve_accessible_inputs(step, context)
    embedded: set[str] = set()
    embedded.update(_extract_refs(step.text))
    for spec in step.defs:
        embedded.update(_extract_refs(spec.as_text or ""))

    instruction = _interpolate(step.text, accessible).strip()
    blocks: List[str] = [f"Instruction:\n{instruction}" if instruction else "Instruction:"]

    explicit_from = set(step.from_vars or [])
    extra_inputs = [
        name
        for name in accessible
        if name not in embedded
        and (name not in _BUILTIN_VAR_NAMES or step.from_vars is None or name in explicit_from)
    ]
    nat_inputs = list(nat_inputs or [])
    if extra_inputs:
        inputs_lines = "\n".join(
            f"- {name}: {_render_value(accessible[name])}" for name in extra_inputs
        )
        blocks.append(f"Inputs:\n{inputs_lines}")
    if nat_inputs:
        nat_lines = "\n".join(f"- {label}: {value}" for label, value in nat_inputs)
        if extra_inputs:
            blocks[-1] += "\n" + nat_lines
        else:
            blocks.append(f"Inputs:\n{nat_lines}")

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


def _schema_type_for_def(type_name: str) -> str:
    t = type_name.lower()
    if t in {"nat", "str"}:
        return "string"
    if t == "int":
        return "integer"
    if t == "float":
        return "number"
    if t == "bool":
        return "boolean"
    return "string"


def build_response_schema(step: Step) -> ResponseSchema:
    props: Dict[str, Any] = {
        "error": {
            "type": "integer",
        },
        "out": {
            "type": "string",
        },
    }
    required = ["error", "out"]

    if step.defs:
        vars_props: Dict[str, Any] = {}
        vars_required: List[str] = []
        for spec in step.defs:
            vars_props[spec.var_name] = {"type": _schema_type_for_def(spec.value_type)}
            vars_required.append(spec.var_name)

        props["vars"] = {
            "type": "object",
            "properties": vars_props,
            "required": vars_required,
        }
        required.append("vars")

    return {
        "type": "object",
        "properties": props,
        "required": required,
    }


def _default_stub_response(step: Step) -> str:
    payload: Dict[str, Any] = {
        "error": 0,
        "out": f"stub output for step {step.index}",
    }
    if step.defs:
        payload["vars"] = {spec.var_name: f"stub value for {spec.var_name}" for spec in step.defs}
    return json.dumps(payload)


def _build_prefilter_prompt(description: str, scope_var: str, scope_text: str) -> str:
    return (
        "Task: extract matching content with minimal rewriting.\n\n"
        f"Description:\n{description}\n\n"
        f"Scope (@{scope_var}):\n{scope_text}\n\n"
        "Rules:\n"
        "- Return only text matching the description.\n"
        "- Keep original wording/order when possible.\n"
        "- Return plain text only.\n"
        "- If nothing matches, return an empty string."
    )


def _run_prefilter(
    item: FromItem,
    runtime_context: Dict[str, Any],
    cheap_model_call: Optional[CheapModelCall],
) -> Tuple[str, str]:
    scope_var = item.scope_var or "ALL"
    scope_text = _render_value(runtime_context.get(scope_var, ""))
    prompt = _build_prefilter_prompt(item.value, scope_var, scope_text)
    if cheap_model_call is None:
        filtered_text = scope_text
    else:
        filtered_text = cheap_model_call(prompt)
    if not isinstance(filtered_text, str):
        raise ValueError("cheap prefilter call must return a string")
    label = f"{item.value} (from @{scope_var})"
    return label, filtered_text


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
    chat_history: Optional[List[str]] = None,
    cheap_model_call: Optional[CheapModelCall] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """Execute steps with prompt construction and model-call injection support."""
    logs: List[Dict[str, Any]] = []
    visible_outputs: List[str] = []
    chat_lines = list(chat_history or [])

    for st in steps:
        runtime_context = dict(context)
        runtime_context.update(_build_builtin_values(context, chat_lines + visible_outputs))
        nat_inputs: List[Tuple[str, str]] = []
        prefilter_logs: List[Dict[str, str]] = []
        for item in st.from_items or []:
            if item.kind != "nat":
                continue
            label, filtered = _run_prefilter(item, runtime_context, cheap_model_call)
            nat_inputs.append((label, filtered))
            prefilter_logs.append(
                {
                    "description": item.value,
                    "scope_var": item.scope_var or "ALL",
                    "filtered_text": filtered,
                }
            )

        prompt = build_step_prompt(st, runtime_context, nat_inputs=nat_inputs)
        response_schema = build_response_schema(st)
        if call_model is None:
            response = _default_stub_response(st)
        else:
            response = call_model(prompt, response_schema)

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
                "response_schema": response_schema,
                "raw_response": response,
                "parsed_json": parsed,
                "staged_updates": staged_updates,
                "prefilter_logs": prefilter_logs,
            }
        )

    return context, logs, visible_outputs

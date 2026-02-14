from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ParseError(ValueError):
    pass


@dataclass
class Command:
    name: str
    payload: str
    line_no: int


@dataclass
class DefSpec:
    var_name: str
    value_type: str = "nat"
    as_text: Optional[str] = None
    line_no: int = 0


@dataclass
class Step:
    index: int
    start_line_no: int
    text: str
    commands: List[Command] = field(default_factory=list)
    from_vars: Optional[List[str]] = None
    defs: List[DefSpec] = field(default_factory=list)
    out_text: Optional[str] = None


@dataclass
class _StepBuilder:
    index: int
    start_line_no: int
    text_lines: List[str] = field(default_factory=list)
    commands: List[Command] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (not self.commands) and (not any(line.strip() for line in self.text_lines))

    def build(self) -> Optional[Step]:
        if self.is_empty():
            return None
        return Step(
            index=self.index,
            start_line_no=self.start_line_no,
            text="\n".join(self.text_lines).strip(),
            commands=list(self.commands),
        )


_THEN_PATTERN = re.compile(r"^\s*/THEN(?:\s+(.*))?$")


def _split_csv_items(payload: str) -> List[str]:
    return [item.strip() for item in payload.split(",") if item.strip()]


def _parse_def_payload(payload: str, line_no: int) -> DefSpec:
    text = payload.strip()
    if not text:
        return DefSpec(var_name="", line_no=line_no)

    parts = text.split(None, 1)
    var_name = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    value_type = "nat"
    as_text: Optional[str] = None

    markers = list(re.finditer(r"/(TYPE|AS)\b", rest))
    for i, marker in enumerate(markers):
        key = marker.group(1).upper()
        seg_start = marker.end()
        seg_end = markers[i + 1].start() if i + 1 < len(markers) else len(rest)
        value = rest[seg_start:seg_end].strip()
        if key == "TYPE" and value:
            value_type = value
        elif key == "AS":
            as_text = value

    return DefSpec(var_name=var_name, value_type=value_type, as_text=as_text, line_no=line_no)


def _populate_step_fields(step: Step, sigil: str) -> None:
    from_vars: Optional[List[str]] = None
    defs: List[DefSpec] = []
    out_lines: List[str] = []

    for cmd in step.commands:
        name = cmd.name.upper()
        if name == "FROM":
            vars_out: List[str] = []
            for item in _split_csv_items(cmd.payload):
                token = item
                if token.startswith(sigil):
                    token = token[len(sigil):].strip()
                vars_out.append(token)
            from_vars = vars_out
        elif name == "DEF":
            defs.append(_parse_def_payload(cmd.payload, cmd.line_no))
        elif name == "OUT":
            out_lines.append(cmd.payload)

    step.from_vars = from_vars
    step.defs = defs
    step.out_text = "\n".join(out_lines) if out_lines else None


def parse_dsl(text: str, sigil: str = "@") -> List[Step]:
    """
    Step 1 scaffold parser:
    - splits steps by /THEN (leading indentation allowed)
    - preserves natural-language step text
    - stores non-/THEN command lines for later phases
    """
    if not isinstance(text, str):
        raise ParseError("DSL input must be a string")
    if not isinstance(sigil, str) or len(sigil) != 1:
        raise ParseError("sigil must be a single character")

    lines = text.splitlines()
    builder = _StepBuilder(index=0, start_line_no=1)
    steps: List[Step] = []

    for line_no, line in enumerate(lines, start=1):
        then_match = _THEN_PATTERN.match(line)
        if then_match:
            step = builder.build()
            if step is not None:
                _populate_step_fields(step, sigil=sigil)
                steps.append(step)
            builder = _StepBuilder(index=len(steps), start_line_no=line_no)
            inline_text = then_match.group(1)
            if inline_text:
                builder.text_lines.append(inline_text)
            continue

        stripped = line.lstrip()
        if stripped.startswith("/") and not stripped.startswith("/THEN"):
            payload = stripped[1:].strip()
            name, _, rest = payload.partition(" ")
            builder.commands.append(Command(name=name, payload=rest.strip(), line_no=line_no))
            continue

        builder.text_lines.append(line)

    final_step = builder.build()
    if final_step is not None:
        _populate_step_fields(final_step, sigil=sigil)
        steps.append(final_step)
    return steps


def steps_to_dicts(steps: List[Step]) -> List[Dict[str, Any]]:
    return [
        {
            "index": st.index,
            "start_line_no": st.start_line_no,
            "text": st.text,
            "from_vars": st.from_vars,
            "defs": [
                {
                    "var_name": d.var_name,
                    "value_type": d.value_type,
                    "as_text": d.as_text,
                    "line_no": d.line_no,
                }
                for d in st.defs
            ],
            "out_text": st.out_text,
            "commands": [
                {"name": cmd.name, "payload": cmd.payload, "line_no": cmd.line_no}
                for cmd in st.commands
            ],
        }
        for st in steps
    ]

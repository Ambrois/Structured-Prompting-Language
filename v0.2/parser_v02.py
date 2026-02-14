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

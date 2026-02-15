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
    from_items: Optional[List["FromItem"]] = None
    defs: List[DefSpec] = field(default_factory=list)
    out_text: Optional[str] = None


@dataclass
class FromItem:
    kind: str  # "var" | "nat"
    value: str  # var name for kind="var", description text for kind="nat"
    scope_var: Optional[str] = None  # only for kind="nat"; defaults to "ALL" downstream


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


_COMMAND_PATTERN = re.compile(r"^\s*/([A-Za-z][A-Za-z0-9_]*)\b(?:\s+(.*))?$")
_DEF_MARKER_PATTERN = re.compile(r"/(TYPE|AS)\b")
_ALLOWED_TYPES = {"nat", "str", "int", "float", "bool"}
_VAR_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KNOWN_COMMANDS = {"FROM", "DEF", "OUT", "TYPE", "AS"}
_RESERVED_READONLY_VARS = {"ALL", "CHAT"}


def _parse_command_line(line: str) -> Optional[tuple[str, str]]:
    match = _COMMAND_PATTERN.match(line)
    if not match:
        return None
    name = match.group(1).upper()
    payload = (match.group(2) or "").strip()
    return name, payload


def _split_csv_items(payload: str) -> List[str]:
    return [item.strip() for item in payload.split(",") if item.strip()]


def _last_def_marker(payload: str) -> Optional[str]:
    markers = list(_DEF_MARKER_PATTERN.finditer(payload))
    if not markers:
        return None
    return markers[-1].group(1).upper()


def _supports_multiline_continuation(cmd: Command) -> bool:
    name = cmd.name.upper()
    if name in {"OUT", "AS"}:
        return True
    if name == "DEF":
        return _last_def_marker(cmd.payload) == "AS"
    return False


def _validate_type_name(type_name: str, line_no: int) -> str:
    normalized = type_name.strip().lower()
    if normalized not in _ALLOWED_TYPES:
        raise ParseError(
            f"Line {line_no}: invalid /TYPE value {type_name!r}; allowed: {sorted(_ALLOWED_TYPES)}"
        )
    return normalized


def _validate_var_name(var_name: str, line_no: int, source: str) -> str:
    if not _VAR_NAME_PATTERN.match(var_name):
        raise ParseError(f"Line {line_no}: invalid variable name {var_name!r} in {source}")
    return var_name


def _parse_from_item(item: str, line_no: int, sigil: str) -> FromItem:
    token = item.strip()
    if not token:
        raise ParseError(f"Line {line_no}: /FROM contains an empty item")

    if token.startswith(sigil):
        if "/IN" in token:
            raise ParseError(f"Line {line_no}: /IN cannot be applied to variable references")
        var_name = _validate_var_name(token[len(sigil) :].strip(), line_no=line_no, source="/FROM")
        return FromItem(kind="var", value=var_name)

    if token.startswith("/IN"):
        raise ParseError(f"Line {line_no}: /IN requires a preceding natural-language description")

    if "/IN" not in token:
        return FromItem(kind="nat", value=token, scope_var="ALL")

    desc, tail = token.split("/IN", 1)
    desc = desc.strip()
    tail = tail.strip()
    if not desc:
        raise ParseError(f"Line {line_no}: /IN requires a preceding natural-language description")
    if not tail.startswith(sigil):
        raise ParseError(f"Line {line_no}: /IN must be followed by exactly one variable reference")
    scope_name = tail[len(sigil) :].strip()
    if not _VAR_NAME_PATTERN.match(scope_name):
        raise ParseError(f"Line {line_no}: /IN must be followed by exactly one variable reference")
    if " " in scope_name:
        raise ParseError(f"Line {line_no}: /IN must be followed by exactly one variable reference")
    return FromItem(kind="nat", value=desc, scope_var=scope_name)


@dataclass
class _DefParseState:
    spec: DefSpec
    seen_type: bool = False
    seen_as: bool = False


def _parse_def_payload(payload: str, line_no: int) -> _DefParseState:
    text = payload.strip()
    if not text:
        raise ParseError(f"Line {line_no}: /DEF requires a variable name")

    parts = text.split(None, 1)
    var_name = _validate_var_name(parts[0], line_no=line_no, source="/DEF")
    if var_name in _RESERVED_READONLY_VARS:
        raise ParseError(f"Line {line_no}: {var_name!r} is a reserved read-only variable name")
    rest = parts[1] if len(parts) > 1 else ""
    state = _DefParseState(spec=DefSpec(var_name=var_name, value_type="nat", line_no=line_no))

    markers = list(_DEF_MARKER_PATTERN.finditer(rest))
    if rest.strip() and not markers:
        raise ParseError(
            f"Line {line_no}: invalid /DEF payload after variable name; expected /TYPE and/or /AS"
        )
    for i, marker in enumerate(markers):
        key = marker.group(1).upper()
        seg_start = marker.end()
        seg_end = markers[i + 1].start() if i + 1 < len(markers) else len(rest)
        value = rest[seg_start:seg_end].strip()

        if key == "TYPE":
            if state.seen_type:
                raise ParseError(f"Line {line_no}: duplicate /TYPE in /DEF block")
            if not value:
                raise ParseError(f"Line {line_no}: /TYPE requires a value")
            state.spec.value_type = _validate_type_name(value, line_no=line_no)
            state.seen_type = True
        elif key == "AS":
            if state.seen_as:
                raise ParseError(f"Line {line_no}: duplicate /AS in /DEF block")
            if not value:
                raise ParseError(f"Line {line_no}: /AS requires description text")
            state.spec.as_text = value
            state.seen_as = True

    return state


def _apply_def_block_command(state: _DefParseState, cmd: Command) -> None:
    name = cmd.name.upper()
    payload = cmd.payload.strip()
    line_no = cmd.line_no

    if name == "TYPE":
        if state.seen_type:
            raise ParseError(f"Line {line_no}: duplicate /TYPE in /DEF block")
        if not payload:
            raise ParseError(f"Line {line_no}: /TYPE requires a value")
        state.spec.value_type = _validate_type_name(payload, line_no=line_no)
        state.seen_type = True
        return

    if name == "AS":
        if state.seen_as:
            raise ParseError(f"Line {line_no}: duplicate /AS in /DEF block")
        if not payload:
            raise ParseError(f"Line {line_no}: /AS requires description text")
        state.spec.as_text = payload
        state.seen_as = True
        return


def _populate_step_fields(step: Step, sigil: str) -> None:
    from_vars: Optional[List[str]] = None
    from_items: Optional[List[FromItem]] = None
    defs: List[DefSpec] = []
    out_lines: List[str] = []

    i = 0
    while i < len(step.commands):
        cmd = step.commands[i]
        name = cmd.name.upper()
        if name == "FROM":
            vars_out: List[str] = []
            items_out: List[FromItem] = []
            for item in _split_csv_items(cmd.payload):
                parsed = _parse_from_item(item, line_no=cmd.line_no, sigil=sigil)
                items_out.append(parsed)
                if parsed.kind == "var":
                    vars_out.append(parsed.value)
            from_vars = vars_out
            from_items = items_out
            i += 1
            continue

        if name == "DEF":
            state = _parse_def_payload(cmd.payload, cmd.line_no)
            i += 1
            while i < len(step.commands):
                nxt = step.commands[i]
                nxt_name = nxt.name.upper()
                if nxt_name not in {"TYPE", "AS"}:
                    break
                _apply_def_block_command(state, nxt)
                i += 1

            if not state.seen_as:
                state.spec.as_text = state.spec.var_name
            if not state.seen_type:
                state.spec.value_type = "nat"
            defs.append(state.spec)
            continue

        if name == "OUT":
            out_lines.append(cmd.payload)
            i += 1
            continue

        if name in {"TYPE", "AS"}:
            raise ParseError(f"Line {cmd.line_no}: /{name} is only valid inside a /DEF block")

        i += 1

    step.from_vars = from_vars
    step.from_items = from_items
    step.defs = defs
    step.out_text = "\n".join(out_lines) if out_lines else None


def _finalize_step(builder: _StepBuilder, steps: List[Step], sigil: str) -> None:
    step = builder.build()
    if step is None:
        return
    if step.text.strip() == "":
        raise ParseError(
            f"Step {step.index} (line {step.start_line_no}): instruction text is required before commands"
        )
    _populate_step_fields(step, sigil=sigil)
    steps.append(step)


def _extract_var_refs(text: str, sigil: str) -> set[str]:
    token_pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(sigil)}([^\s,.;:!?()\[\]{{}}\"'`]+)"
    )
    refs: set[str] = set()
    for token in token_pattern.findall(text or ""):
        if not _VAR_NAME_PATTERN.match(token):
            raise ParseError(f"invalid variable name {sigil}{token!s} in embedded reference")
        refs.add(token)
    return refs


def _extract_step_embedded_refs(step: Step, sigil: str) -> set[str]:
    refs = _extract_var_refs(step.text, sigil=sigil)
    for spec in step.defs:
        refs.update(_extract_var_refs(spec.as_text or "", sigil=sigil))
    return refs


def _validate_from_symbols(steps: List[Step], sigil: str) -> None:
    known_vars: set[str] = set(_RESERVED_READONLY_VARS)
    for step in steps:
        embedded_refs = _extract_step_embedded_refs(step, sigil=sigil)
        if step.from_vars is not None:
            allowed = set(step.from_vars)
            for name in step.from_vars:
                if name not in known_vars:
                    raise ParseError(
                        f"Step {step.index} (line {step.start_line_no}): /FROM references undefined variable {sigil}{name}"
                    )
            if step.from_items:
                for item in step.from_items:
                    if item.kind == "nat":
                        scope_name = item.scope_var or "ALL"
                        if scope_name not in known_vars:
                            raise ParseError(
                                f"Step {step.index} (line {step.start_line_no}): /FROM references undefined variable {sigil}{scope_name}"
                            )
            for name in sorted(embedded_refs):
                if name not in allowed:
                    raise ParseError(
                        f"Step {step.index} (line {step.start_line_no}): reference {sigil}{name} is not allowed by /FROM"
                    )
        for spec in step.defs:
            known_vars.add(spec.var_name)


def parse_dsl(text: str, sigil: str = "@") -> List[Step]:
    """Parse DSL text into steps with raw commands and Step-2/Step-4 structured fields."""
    if not isinstance(text, str):
        raise ParseError("DSL input must be a string")
    if not isinstance(sigil, str) or len(sigil) != 1:
        raise ParseError("sigil must be a single character")

    lines = text.splitlines()
    builder = _StepBuilder(index=0, start_line_no=1)
    steps: List[Step] = []

    for line_no, line in enumerate(lines, start=1):
        cmd = _parse_command_line(line)
        if cmd is not None:
            name, payload = cmd
            if name == "THEN":
                _finalize_step(builder, steps, sigil=sigil)
                builder = _StepBuilder(index=len(steps), start_line_no=line_no)
                if payload:
                    builder.text_lines.append(payload)
                continue

            if name not in _KNOWN_COMMANDS:
                raise ParseError(f"Line {line_no}: unknown command /{name}")

            builder.commands.append(Command(name=name, payload=payload, line_no=line_no))
            continue

        if builder.commands and _supports_multiline_continuation(builder.commands[-1]):
            if builder.commands[-1].payload:
                builder.commands[-1].payload += "\n" + line
            else:
                builder.commands[-1].payload = line
            continue

        if builder.commands and line.strip():
            raise ParseError(
                f"Line {line_no}: instruction text must appear before commands within a step"
            )
        builder.text_lines.append(line)

    _finalize_step(builder, steps, sigil=sigil)
    _validate_from_symbols(steps, sigil=sigil)
    return steps


def steps_to_dicts(steps: List[Step]) -> List[Dict[str, Any]]:
    return [
        {
            "index": st.index,
            "start_line_no": st.start_line_no,
            "text": st.text,
            "from_vars": st.from_vars,
            "from_items": [
                {"kind": item.kind, "value": item.value, "scope_var": item.scope_var}
                for item in (st.from_items or [])
            ],
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

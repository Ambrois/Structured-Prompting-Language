"""
NL-first DSL parser (v0.1)

Implements:
- Implicit first step
- Step delimiter: line starting with /THEN
- Directives: /FROM, /OUT, /AS (each optional)
  - directive payload is:
      /CMD payload...
- Payload parsing supports:
  - singular unquoted text (no top-level commas) -> one item
  - comma-separated list at top level
  - quoted items using double quotes "..." with escapes \"
  - commas inside quotes do NOT split items
- Variable sigil configurable (default '@'), only relevant for /AS validation and
  optional classification of /FROM items.

Enforces the /OUT + /AS interaction rules from your standard:
Let k = number of vars in /AS, m = number of descriptions in /OUT.
- If k = 0: /OUT must be singular (m == 1) if present, else ok.
- If k = 1: /OUT must be singular (m == 1) if present, else ok.
- If k > 1: /OUT must be present and have m == k, else error.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# -------------------------
# AST
# -------------------------

@dataclass
class Directive:
    name: str
    items: List[str]
    line_no: int

@dataclass
class Step:
    index: int
    start_line_no: int
    text: str  # natural language instructions (joined)
    from_items: Optional[List[str]] = None
    out_items: Optional[List[str]] = None
    as_vars: Optional[List[str]] = None  # variable names without sigil
    directives: List[Directive] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"Step(index={self.index}, start_line_no={self.start_line_no}, "
            f"text={self.text!r}, from_items={self.from_items}, "
            f"out_items={self.out_items}, as_vars={self.as_vars})"
        )


@dataclass
class StepBuilder:
    index: int
    start_line_no: int
    text_lines: List[str] = field(default_factory=list)
    directives: List[Directive] = field(default_factory=list)
    from_items: Optional[List[str]] = None
    out_items: Optional[List[str]] = None
    as_vars: Optional[List[str]] = None  # variable names without sigil

    def _has_nonblank_text(self) -> bool:
        return any(line.strip() for line in self.text_lines)

    def is_empty(self) -> bool:
        return (not self._has_nonblank_text()) and (not self.directives)

    def build(self) -> Optional[Step]:
        if self.is_empty():
            return None
        step_text = "\n".join(self.text_lines).strip()
        if step_text == "" and not self.directives:
            return None
        return Step(
            index=self.index,
            start_line_no=self.start_line_no,
            text=step_text,
            from_items=self.from_items,
            out_items=self.out_items,
            as_vars=self.as_vars,
            directives=list(self.directives),
        )

# -------------------------
# Parsing utilities
# -------------------------

class ParseError(ValueError):
    pass


def _strip_outer_parens(s: str) -> Tuple[bool, str]:
    s2 = s.strip()
    if s2.startswith("(") and s2.endswith(")"):
        return True, s2[1:-1]
    return False, s2


def _split_top_level_commas(payload: str) -> List[str]:
    """
    Split payload by commas that are not inside double quotes.

    Supports escaping inside quotes via \"
    """
    items: List[str] = []
    buf: List[str] = []
    in_quotes = False
    escape = False

    for ch in payload:
        if escape:
            buf.append(ch)
            escape = False
            continue

        if in_quotes and ch == "\\":
            # escape next char in quoted string
            buf.append(ch)
            escape = True
            continue

        if ch == '"':
            in_quotes = not in_quotes
            buf.append(ch)
            continue

        if (not in_quotes) and ch == ",":
            items.append("".join(buf).strip())
            buf = []
            continue

        buf.append(ch)

    if in_quotes:
        raise ParseError("Unclosed double quote in payload: " + payload)

    tail = "".join(buf).strip()
    if tail or payload.strip() == "":
        items.append(tail)

    # Drop empty items caused by trailing commas like "a, b,"
    items = [it for it in items if it != ""]
    return items


def _unquote_item(item: str) -> str:
    item = item.strip()
    if len(item) >= 2 and item[0] == '"' and item[-1] == '"':
        inner = item[1:-1]
        # interpret \" and \\ minimally
        inner = inner.replace(r'\"', '"').replace(r"\\", "\\")
        return inner
    return item


def parse_payload(payload: str) -> List[str]:
    """
    Parse a directive payload into a list of items (strings).

    Rules:
    - If there are no top-level commas, return [unquoted_payload]
    - If there are commas, split at top-level commas, then unquote each item
    """
    raw = payload.strip()
    if raw == "":
        return []

    # Determine whether it's a list by presence of a top-level comma.
    # We'll just always run split_top_level_commas; if no commas it returns [raw].
    parts = _split_top_level_commas(raw)
    return [_unquote_item(p) for p in parts]


def _parse_directive_line(line: str) -> Optional[Tuple[str, str]]:
    """
    If line begins with a known directive, return (directive_name, payload_raw)
    else None.

    Accepts:
      /THEN payload...
      /FROM payload...
      similarly for /OUT and /AS
    """
    s = line.lstrip()
    if not s.startswith("/"):
        return None

    def _extract_payload(cmd: str) -> Optional[str]:
        prefix = f"/{cmd}"
        if not s.startswith(prefix):
            return None
        tail = s[len(prefix):]
        # Match only exact command token, not prefixes like /OUTCOME or /THENx.
        if tail == "":
            return ""
        if tail[0].isspace():
            return tail.strip()
        return None

    then_payload = _extract_payload("THEN")
    if then_payload is not None:
        return "THEN", then_payload

    # Only parse directives at beginning of line (after whitespace)
    for cmd in ("FROM", "OUT", "AS"):
        payload = _extract_payload(cmd)
        if payload is not None:
            # payload is remainder of line
            return cmd, payload
    return None


def _parse_as_vars(items: List[str], sigil: str, line_no: int) -> List[str]:
    """
    /AS items are variable names, sigil optional.
    Return variable names without sigil.
    """
    vars_out: List[str] = []
    for it in items:
        t = it.strip()
        if t == "":
            continue
        if t.startswith(sigil):
            name = t[len(sigil):].strip()
        else:
            name = t
        if not name:
            raise ParseError(f"Line {line_no}: empty variable name in /AS: {t!r}")
        vars_out.append(name)
    return vars_out


def _validate_out_as(st: Step) -> None:
    # Enforce /OUT + /AS interaction constraints per your standard
    k = len(st.as_vars) if st.as_vars is not None else 0
    m = len(st.out_items) if st.out_items is not None else 0

    if k <= 1:
        if st.out_items is not None and m != 1:
            raise ParseError(
                f"Step {st.index} (line {st.start_line_no}): k={k} but /OUT has {m} items; must be singular."
            )
        return

    # k > 1
    if st.out_items is None:
        raise ParseError(
            f"Step {st.index} (line {st.start_line_no}): k={k} but missing /OUT; must provide {k} items."
        )
    if m != k:
        raise ParseError(
            f"Step {st.index} (line {st.start_line_no}): k={k} but /OUT has m={m}; must match exactly."
        )


# -------------------------
# Main parser
# -------------------------

def parse_dsl(text: str, sigil: str = "@") -> List[Step]:
    lines = text.splitlines()

    steps: List[Step] = []
    builder = StepBuilder(index=0, start_line_no=1)

    for i, line in enumerate(lines, start=1):
        d = _parse_directive_line(line)
        if d is None:
            # normal NL line
            builder.text_lines.append(line)
            continue

        cmd, payload_raw = d
        if cmd == "THEN":
            # /THEN starts a new step. If inline text follows, treat it as the
            # first NL line of the next step.
            st = builder.build()
            if st is not None:
                steps.append(st)
                builder = StepBuilder(index=builder.index + 1, start_line_no=i)
            if payload_raw:
                builder.text_lines.append(payload_raw)
            continue

        items = parse_payload(payload_raw)
        builder.directives.append(Directive(name=cmd, items=items, line_no=i))

        if cmd == "FROM":
            builder.from_items = items
        elif cmd == "OUT":
            builder.out_items = items
        elif cmd == "AS":
            builder.as_vars = _parse_as_vars(items, sigil=sigil, line_no=i)
        else:
            # unreachable due to _parse_directive_line
            raise ParseError(f"Line {i}: unknown directive {cmd}")

    st = builder.build()
    if st is not None:
        steps.append(st)

    # Enforce /OUT + /AS interaction constraints per your standard
    for st in steps:
        _validate_out_as(st)

    return steps


# -------------------------
# Simple test runner
# -------------------------

def _pretty_print_steps(steps: List[Step]) -> None:
    for st in steps:
        print(f"=== Step {st.index} (starts at line {st.start_line_no}) ===")
        print("Text:")
        print(st.text if st.text else "(empty)")
        print("FROM:", st.from_items)
        print("OUT :", st.out_items)
        print("AS  :", st.as_vars)
        print()


def _steps_to_dicts(steps: List[Step]) -> List[dict]:
    return [
        {
            "index": st.index,
            "start_line_no": st.start_line_no,
            "text": st.text,
            "from_items": st.from_items,
            "out_items": st.out_items,
            "as_vars": st.as_vars,
            "directives": [
                {"name": d.name, "items": d.items, "line_no": d.line_no}
                for d in st.directives
            ],
        }
        for st in steps
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse an NL-first DSL file.")
    parser.add_argument("path", help="Path to a text file containing the DSL.")
    parser.add_argument("--sigil", default="@", help="Variable sigil (default: @).")
    parser.add_argument(
        "--format",
        choices=["json", "pretty"],
        default="json",
        help="Output format (default: json).",
    )
    args = parser.parse_args()

    dsl_text = Path(args.path).read_text(encoding="utf-8")
    steps = parse_dsl(dsl_text, sigil=args.sigil)

    if args.format == "pretty":
        _pretty_print_steps(steps)
    else:
        print(json.dumps(_steps_to_dicts(steps), indent=2))

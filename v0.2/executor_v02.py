from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from parser_v02 import Step


ModelCall = Callable[[str], str]


def execute_steps(
    steps: List[Step],
    context: Dict[str, Any],
    call_model: Optional[ModelCall] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """
    Step 1 scaffold executor.
    This intentionally keeps behavior minimal so later steps can add v0.2 rules.
    """
    logs: List[Dict[str, Any]] = []
    visible_outputs: List[str] = []

    for st in steps:
        prompt = st.text.strip()
        if call_model is None:
            response = f"stub output for step {st.index}"
        else:
            response = call_model(prompt)

        visible_outputs.append(response)
        logs.append(
            {
                "step_index": st.index,
                "start_line_no": st.start_line_no,
                "text": st.text,
                "prompt": prompt,
                "raw_response": response,
            }
        )

    return context, logs, visible_outputs

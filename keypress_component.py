from __future__ import annotations

import streamlit.components.v1 as components


_KEYPRESS_COMPONENT = None


def ctrl_enter_submit(key: str = "ctrl_enter") -> int:
    global _KEYPRESS_COMPONENT
    if _KEYPRESS_COMPONENT is None:
        _KEYPRESS_COMPONENT = components.declare_component(
            "ctrl_enter_submit",
            path=str((__file__[:-3]) + "_frontend"),
        )
    return _KEYPRESS_COMPONENT(key=key, default=0)

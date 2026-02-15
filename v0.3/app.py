"""Run with: streamlit run v0.2/app.py"""

from __future__ import annotations

import os
import uuid
import json
import math

import streamlit as st

from parser_v02 import ParseError, parse_dsl, steps_to_dicts
from executor_v02 import execute_steps
from model_adapters_v02 import make_gemini_caller
from gemini_client_v02 import call_gemini
from state_store_v02 import load_chats, save_chats
from versioning_v02 import (
    backfill_history_metadata,
    cutoff_index_for_version_view,
    get_assistant_messages_for_run,
    get_thread_versions,
    new_message_id,
    next_version_for_thread,
    project_visible_history,
)


GRUVBOX_DARK_CSS = """
<style>

:root {
  --gb-bg: #282828;
  --gb-bg-1: #3c3836;
  --gb-bg-2: #504945;
  --gb-bg-3: #665c54;
  --gb-bg-alpha: rgba(40, 40, 40, 0.86);
  --gb-fg: #ebdbb2;
  --gb-fg-2: #d5c4a1;
  --gb-muted: #a89984;
  --gb-red: #cc241d;
  --gb-green: #98971a;
  --gb-yellow: #d79921;
  --gb-blue: #458588;
  --gb-purple: #b16286;
  --gb-aqua: #689d6a;
  --gb-orange: #d65d0e;
  --gb-font-serif: "Bitstream Vera Serif", "DejaVu Serif", "Liberation Serif", Georgia, Cambria, "Times New Roman", serif;
  --gb-font-weight: 500;
  --gb-heading-weight: 680;
}

html,
body,
[data-testid="stAppViewContainer"] {
  background: var(--gb-bg);
  color: var(--gb-fg);
  font-family: var(--gb-font-serif);
  font-weight: var(--gb-font-weight);
  line-height: 1.45;
}

[data-testid="stAppViewContainer"] > .main {
  background: var(--gb-bg);
}

div[data-testid="stAppViewContainer"] > div {
  background: var(--gb-bg);
}

[data-testid="stAppViewContainer"] *,
section[data-testid="stSidebar"] *,
header[data-testid="stHeader"] * {
  font-family: var(--gb-font-serif) !important;
}

.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
[data-testid="stSelectbox"] [role="combobox"],
.stButton > button,
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input {
  font-family: var(--gb-font-serif);
}

footer,
div[data-testid="stBottom"],
div[data-testid="stBottom"] > div,
div[data-testid="stBottomBlockContainer"],
div[data-testid="stBottomBlockContainer"] > div {
  background: var(--gb-bg);
}

section[data-testid="stSidebar"] {
  background: var(--gb-bg-1);
  border-right: 1px solid var(--gb-bg-3);
}

h1,
h2,
h3,
h4,
h5,
h6 {
  color: var(--gb-fg);
  letter-spacing: 0.01em;
  font-family: var(--gb-font-serif) !important;
  font-weight: var(--gb-heading-weight) !important;
}

a,
a:visited {
  color: var(--gb-purple);
}

small {
  color: var(--gb-muted);
}

div[data-testid="stChatMessage"],
div[data-testid="stChatMessageContent"] {
  background: transparent;
  border: none;
  border-radius: 14px;
  margin: 0.35rem 0;
  padding: 0.35rem 0.9rem;
  align-items: flex-start;
}

div[data-testid="stChatMessage"][aria-label="user"],
div[data-testid="stChatMessageContent"][aria-label="user"] {
  background: transparent;
}

div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
div[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p {
  margin: 0;
}

div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
div[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] {
  padding-top: 0;
  margin-top: -0.6rem;
}

div[data-testid="stChatInput"] textarea,
div[data-testid="stChatInput"] input,
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stSelectbox select {
  background: var(--gb-bg-2);
  border-color: var(--gb-bg-3);
  color: var(--gb-fg);
}

/* Selectbox (baseweb) styling */
[data-testid="stSelectbox"] [role="combobox"],
[data-testid="stSelectbox"] [data-baseweb="select"] > div {
  background: var(--gb-bg-2);
  border-color: var(--gb-bg-3);
  color: var(--gb-fg);
}

[data-testid="stSelectbox"] svg {
  fill: var(--gb-fg);
}

/* Number input +/- buttons */
[data-testid="stNumberInput"] button {
  background: var(--gb-bg-2);
  border-color: var(--gb-bg-3);
  color: var(--gb-fg);
}

div[data-testid="stChatInput"] textarea::placeholder,
div[data-testid="stChatInput"] input::placeholder,
.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
  color: var(--gb-muted);
}



.stButton > button {
  background: var(--gb-bg-2);
  border: 1px solid var(--gb-bg-3);
  color: var(--gb-fg);
}

.stButton > button:hover {
  border-color: var(--gb-yellow);
}

div[data-baseweb="popover"] {
  min-width: 0 !important;
  width: fit-content !important;
  max-width: min(90vw, 22rem) !important;
  background: var(--gb-bg-1) !important;
  border: 1px solid var(--gb-bg-3) !important;
  color: var(--gb-fg) !important;
}

div[data-baseweb="popover"] > div {
  background: var(--gb-bg-1) !important;
  color: var(--gb-fg) !important;
}

div[data-testid="stChatMessage"] [data-testid="stPopover"] :is(button, [role="button"]),
div[data-testid="stChatMessageContent"] [data-testid="stPopover"] :is(button, [role="button"]) {
  background: transparent !important;
  border: none !important;
  color: var(--gb-fg) !important;
  box-shadow: none !important;
}

div[data-testid="stChatMessage"] [data-testid="stPopover"] :is(button, [role="button"]):hover,
div[data-testid="stChatMessageContent"] [data-testid="stPopover"] :is(button, [role="button"]):hover {
  border-color: var(--gb-yellow) !important;
}

div[data-baseweb="popover"] [data-testid="stVerticalBlock"] {
  width: fit-content !important;
  max-width: 100% !important;
}

div[data-baseweb="popover"] .stButton > button {
  width: auto !important;
  white-space: nowrap;
}

div[data-baseweb="popover"] :is(button, [role="button"], [role="menuitem"]) {
  background: var(--gb-bg-2) !important;
  background-color: var(--gb-bg-2) !important;
  border: 1px solid var(--gb-bg-3) !important;
  color: var(--gb-fg) !important;
  box-shadow: none !important;
}

div[data-baseweb="popover"] :is(button, [role="button"], [role="menuitem"]):hover {
  border-color: var(--gb-yellow) !important;
}

code,
pre,
kbd {
  color: var(--gb-fg);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
  font-weight: 500;
}

header[data-testid="stHeader"],
div[data-testid="stHeader"] {
  background: var(--gb-bg);
  border-bottom: none;
  height: 3.9rem;
  min-height: 3.9rem;
  padding: 0 0.75rem;
  box-sizing: border-box;
}

header[data-testid="stHeader"] * {
  color: var(--gb-fg);
}

header[data-testid="stHeader"] button,
header[data-testid="stHeader"] [role="button"] {
  min-height: 1.75rem;
  height: 1.75rem;
  padding: 0 0.35rem;
  font-size: 0.85rem;
}

header[data-testid="stHeader"] svg {
  width: 0.9rem;
  height: 0.9rem;
}




[role="dialog"] {
  width: min(96vw, 1200px);
  max-width: 96vw;
  background: var(--gb-bg-2);
  color: var(--gb-fg);
  border: 1px solid var(--gb-bg-3);
}

div[data-testid="stDialog"] [role="dialog"] {
  background: var(--gb-bg-2);
  color: var(--gb-fg);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
}

div[data-testid="stDialog"] [role="dialog"] * {
  color: var(--gb-fg);
}

div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p {
  color: var(--gb-fg);
}

div[data-testid="stDialog"] textarea,
div[data-testid="stDialog"] input {
  background: var(--gb-bg-2);
  border-color: var(--gb-bg-3);
  color: var(--gb-fg);
}

div[data-testid="stDialog"] button {
  background: var(--gb-bg-2);
  border: 1px solid var(--gb-bg-3);
  color: var(--gb-fg);
}

div[data-testid="stDialog"] button:hover {
  border-color: var(--gb-yellow);
}

div[data-baseweb="modal"] {
  background-color: rgba(40, 40, 40, 0.42);
}

.block-container {
  max-width: 960px;
  padding-top: 2rem;
}
</style>
"""

GRUVBOX_CODE_FONT_OVERRIDES = """
<style>
:root {
  --gb-font-serif: "IBM Plex Mono", "JetBrains Mono", "Fira Code", "Cascadia Mono", "Cascadia Code", "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  --gb-font-weight: 500;
  --gb-heading-weight: 620;
}
</style>
"""

TEXTBOOK_THEME_OVERRIDES = """
<style>
:root {
  --gb-bg: #f4ecd8;
  --gb-bg-1: #efe4cc;
  --gb-bg-2: #e7d7b9;
  --gb-bg-3: #c6b08b;
  --gb-bg-alpha: rgba(244, 236, 216, 0.92);
  --gb-fg: #3d2d1c;
  --gb-fg-2: #4f3d28;
  --gb-muted: #6f5c43;
  --gb-red: #8a3c2c;
  --gb-green: #47653a;
  --gb-yellow: #8c6d2f;
  --gb-blue: #3f5f7a;
  --gb-purple: #70507d;
  --gb-aqua: #3f6c67;
  --gb-orange: #9b5a2b;
  --gb-font-serif: "Bitstream Vera Serif", "DejaVu Serif", "Liberation Serif", Georgia, Cambria, "Times New Roman", serif;
  --gb-font-weight: 500;
  --gb-heading-weight: 700;
}

html,
body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
div[data-testid="stAppViewContainer"] > div {
  background:
    radial-gradient(circle at 14% 16%, rgba(255, 255, 255, 0.55), transparent 42%),
    radial-gradient(circle at 84% 8%, rgba(127, 95, 58, 0.07), transparent 34%),
    linear-gradient(180deg, #f8efdd 0%, #f0e1c2 100%);
}

[data-testid="stAppViewContainer"] {
  color: var(--gb-fg);
}

[data-testid="stAppViewContainer"] :where(
  p,
  span,
  label,
  li,
  th,
  td,
  h1,
  h2,
  h3,
  h4,
  h5,
  h6,
  button,
  input,
  textarea,
  div[data-testid="stMarkdownContainer"],
  div[data-testid="stMarkdownContainer"] *
) {
  color: var(--gb-fg) !important;
}

a,
a:visited {
  color: #35566e !important;
}

[data-testid="stCaptionContainer"],
small {
  color: var(--gb-muted) !important;
}

section[data-testid="stSidebar"] {
  box-shadow: inset -1px 0 0 #c6b08b;
}

header[data-testid="stHeader"],
div[data-testid="stHeader"],
div[data-testid="stDecoration"],
div[data-testid="stToolbar"],
div[data-testid="stAppHeader"],
div[data-testid="stHeaderActionElements"] {
  display: none !important;
}

footer,
div[data-testid="stBottom"],
div[data-testid="stBottom"] > div,
div[data-testid="stBottomBlockContainer"],
div[data-testid="stBottomBlockContainer"] > div {
  background: var(--gb-bg-1) !important;
  background-color: var(--gb-bg-1) !important;
  background-image: none !important;
  box-shadow: none !important;
  border: none !important;
}

div[data-testid="stChatMessage"],
div[data-testid="stChatMessageContent"] {
  border: none;
  box-shadow: none;
}

div[data-testid="stChatMessage"][aria-label="user"],
div[data-testid="stChatMessageContent"][aria-label="user"] {
  border-color: transparent;
}

.stButton > button {
  background: #e8d8b8;
}

.stButton > button:hover {
  background: #eddcb9;
}

div[data-baseweb="popover"] :is(button, [role="button"], [role="menuitem"]) {
  background: #e8d8b8 !important;
  background-color: #e8d8b8 !important;
  border: 1px solid #c6b08b !important;
  color: var(--gb-fg) !important;
  box-shadow: none !important;
}

div[data-baseweb="popover"] :is(button, [role="button"], [role="menuitem"]):hover {
  background: #eddcb9 !important;
}

div[data-baseweb="modal"] {
  background-color: rgba(75, 55, 31, 0.18);
}
</style>
"""

THEMES = {
    "Gruvbox Dark": GRUVBOX_DARK_CSS + GRUVBOX_CODE_FONT_OVERRIDES,
    "Paper White (WIP)": GRUVBOX_DARK_CSS + TEXTBOOK_THEME_OVERRIDES,
    "Paper White": GRUVBOX_DARK_CSS + TEXTBOOK_THEME_OVERRIDES,
    "Textbook": GRUVBOX_DARK_CSS + TEXTBOOK_THEME_OVERRIDES,
    "Gruvbox Scholar": GRUVBOX_DARK_CSS,
    "Default": "",
}
THEME_DEFAULT = "Gruvbox Dark"
THEME_ORDER = ["Gruvbox Dark", "Paper White (WIP)", "Default"]

SHARED_LAYOUT_CSS = """
<style>
:root {
  --dsl-content-max-width: 780px;
}

div[data-testid="stAppViewContainer"] .main .block-container {
  width: 100%;
  max-width: min(calc(100vw - 1.5rem), var(--dsl-content-max-width)) !important;
  padding-top: 2rem;
  padding-left: 0.75rem;
  padding-right: 0.75rem;
}

div[data-testid="stBottomBlockContainer"],
div[data-testid="stBottomBlockContainer"] > div,
div[data-testid="stBottomBlockContainer"] [data-testid="stChatInput"] {
  width: 100%;
  max-width: min(calc(100vw - 1.5rem), var(--dsl-content-max-width)) !important;
  margin-left: auto !important;
  margin-right: auto !important;
}
</style>
"""


def _apply_theme(theme_name: str) -> None:
    css = THEMES.get(theme_name, "")
    if css:
        st.markdown(css, unsafe_allow_html=True)


st.set_page_config(page_title="Chat DSL", layout="wide")

if "draft_sync" in st.session_state:
    st.session_state["sidebar_draft"] = st.session_state.pop("draft_sync")

current_theme = st.session_state.get("ui_theme", THEME_DEFAULT)
if current_theme not in THEMES:
    current_theme = THEME_DEFAULT
_apply_theme(current_theme)
st.markdown(SHARED_LAYOUT_CSS, unsafe_allow_html=True)

st.title("Chat DSL v0.2")

st.session_state.setdefault("edit_target_chat_id", None)
st.session_state.setdefault("edit_target_message_id", None)
st.session_state.setdefault("versions_target_chat_id", None)
st.session_state.setdefault("versions_target_thread_id", None)
st.session_state.setdefault("versions_open", False)
st.session_state.setdefault("copy_target_chat_id", None)
st.session_state.setdefault("copy_target_message_id", None)
st.session_state.setdefault("copy_open", False)
st.session_state.setdefault("history_view_chat_id", None)
st.session_state.setdefault("history_view_message_id", None)

def _new_chat(name: str) -> dict:
    safe_name = name.strip() or "Untitled"
    return {
        "id": f"chat-{uuid.uuid4().hex[:8]}",
        "name": safe_name,
        "history": [],
        "vars": {},
    }


def _ensure_active_chat(state: dict) -> dict:
    chats = state.get("chats", [])
    if not chats:
        chat = _new_chat("Default")
        state["chats"] = [chat]
        state["active_chat_id"] = chat["id"]
        return chat

    active_id = state.get("active_chat_id")
    for chat in chats:
        if chat.get("id") == active_id:
            return chat

    state["active_chat_id"] = chats[0].get("id")
    return chats[0]


def _rename_chat(chat_id: str) -> None:
    state = st.session_state.chats_state
    chats = state.get("chats", [])
    new_name = st.session_state.get(f"rename_{chat_id}", "").strip()
    for chat in chats:
        if chat.get("id") == chat_id:
            chat["name"] = new_name or chat.get("name", chat_id)
            break
    save_chats(state)


def _clear_composer() -> None:
    st.session_state["chat_composer"] = ""

def _clear_draft() -> None:
    st.session_state["draft_sync"] = ""
    st.session_state["draft_dialog"] = ""


def _clear_edit_state() -> None:
    st.session_state["edit_target_chat_id"] = None
    st.session_state["edit_target_message_id"] = None


def _clear_history_view() -> None:
    st.session_state["history_view_chat_id"] = None
    st.session_state["history_view_message_id"] = None


def _set_history_view(message_id: str | None, active_chat_id: str) -> None:
    st.session_state["history_view_chat_id"] = active_chat_id
    st.session_state["history_view_message_id"] = message_id


def _find_message_by_id(chat_history: list, message_id: str | None) -> dict | None:
    if not message_id:
        return None
    for msg in chat_history:
        if msg.get("id") == message_id:
            return msg
    return None


def _start_edit_from_message(msg: dict, active_chat_id: str) -> None:
    content = str(msg.get("content", ""))
    st.session_state["edit_target_chat_id"] = active_chat_id
    st.session_state["edit_target_message_id"] = msg.get("id")
    st.session_state["draft_sync"] = content
    st.session_state["draft_dialog"] = content
    st.session_state["draft_fullscreen"] = True


def _open_versions_for_thread(thread_id: str, active_chat_id: str) -> None:
    st.session_state["versions_target_chat_id"] = active_chat_id
    st.session_state["versions_target_thread_id"] = thread_id
    st.session_state["versions_open"] = True


def _open_copy_for_message(msg: dict, active_chat_id: str) -> None:
    st.session_state["copy_target_chat_id"] = active_chat_id
    st.session_state["copy_target_message_id"] = msg.get("id")
    st.session_state["copy_open"] = True

def _format_var_preview(value: object, max_len: int = 140) -> str:
    if isinstance(value, str):
        preview = value.replace("\n", "\\n")
    elif isinstance(value, (dict, list, tuple)):
        try:
            preview = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        except TypeError:
            preview = repr(value)
    else:
        preview = repr(value)
    if len(preview) > max_len:
        preview = preview[: max_len - 1] + "…"
    return preview


def _approx_token_count(value: object) -> int:
    if isinstance(value, str):
        return len(value) // 4
    if isinstance(value, (dict, list, tuple)):
        try:
            return len(json.dumps(value, ensure_ascii=True)) // 4
        except TypeError:
            return 0
    return 0


def _run_dsl(
    input_text: str,
    use_gemini: bool,
    timeout_s: float,
    model: str | None,
    chat_history: list,
    chat_vars: dict,
    state: dict,
    edited_from_message_id: str | None = None,
) -> None:
    if input_text.strip() == "":
        return
    try:
        steps = parse_dsl(input_text, sigil="@")
    except ParseError as e:
        st.error(f"Parse error: {e}")
        st.stop()

    user_message_id = new_message_id("msg")
    run_id = new_message_id("run")
    thread_id = user_message_id
    version = 1
    edited_from_id = None
    vars_before = dict(chat_vars)

    edited_from_msg = _find_message_by_id(chat_history, edited_from_message_id)
    if (
        edited_from_msg
        and edited_from_msg.get("role") == "user"
        and edited_from_msg.get("mode") == "dsl"
    ):
        src_meta = edited_from_msg.get("meta", {})
        thread_id = src_meta.get("thread_id") or edited_from_msg.get("id") or user_message_id
        version = next_version_for_thread(chat_history, thread_id)
        edited_from_id = edited_from_msg.get("id")
        src_vars_before = src_meta.get("vars_before")
        if isinstance(src_vars_before, dict):
            vars_before = dict(src_vars_before)

    ctx = dict(vars_before)
    try:
        call_model = None
        if use_gemini:
            call_model = make_gemini_caller(model=model, timeout_s=timeout_s)
        ctx, logs, outputs = execute_steps(steps, ctx, call_model=call_model)
    except Exception as e:
        st.error(f"Execution error: {e}")
        st.stop()

    steps_dicts = steps_to_dicts(steps)

    user_meta = {
        "thread_id": thread_id,
        "version": version,
        "run_id": run_id,
        "parsed_steps": steps_dicts,
        "execution_logs": logs,
        "vars_before": vars_before,
        "vars_after": ctx,
    }
    if edited_from_id:
        user_meta["edited_from_message_id"] = edited_from_id
        user_meta["source_cutoff_index"] = cutoff_index_for_version_view(
            chat_history, edited_from_id
        )

    chat_history.append(
        {
            "id": user_message_id,
            "role": "user",
            "content": input_text,
            "mode": "dsl",
            "meta": user_meta,
        }
    )
    output_logs = logs
    if outputs:
        for idx, out in enumerate(outputs):
            step_log = output_logs[idx] if idx < len(output_logs) else None
            msg = {
                "id": new_message_id("msg"),
                "role": "assistant",
                "content": out,
                "mode": "dsl",
                "meta": {
                    "run_id": run_id,
                    "source_user_message_id": user_message_id,
                },
            }
            if step_log is not None:
                msg["meta"]["step_log"] = step_log
            chat_history.append(msg)
    else:
        chat_history.append(
            {
                "id": new_message_id("msg"),
                "role": "assistant",
                "content": "(no visible output; all steps produced variables)",
                "mode": "dsl",
                "meta": {
                    "run_id": run_id,
                    "source_user_message_id": user_message_id,
                    "parsed_steps": steps_dicts,
                    "execution_logs": logs,
                    "vars_after": ctx,
                },
            }
        )
    active_chat["vars"] = ctx
    save_chats(state)

    last_runs = st.session_state.setdefault("last_run_by_chat", {})
    last_runs[active_chat["id"]] = {
        "steps": steps_dicts,
        "logs": logs,
        "vars": ctx,
    }


def _run_raw(
    raw_text: str,
    timeout_s: float,
    model: str | None,
    chat_history: list,
    state: dict,
) -> None:
    if raw_text.strip() == "":
        return
    try:
        response_text = call_gemini(raw_text, model=model, timeout_s=timeout_s)
    except Exception as e:
        st.error(f"Execution error: {e}")
        st.stop()

    run_id = new_message_id("run")
    user_message_id = new_message_id("msg")
    chat_history.append(
        {
            "id": user_message_id,
            "role": "user",
            "content": raw_text,
            "mode": "raw",
            "meta": {"run_id": run_id},
        }
    )
    chat_history.append(
        {
            "id": new_message_id("msg"),
            "role": "assistant",
            "content": response_text,
            "mode": "raw",
            "meta": {
                "run_id": run_id,
                "source_user_message_id": user_message_id,
                "raw_response": response_text,
            },
        }
    )
    save_chats(state)

if "chats_state" not in st.session_state:
    st.session_state.chats_state = load_chats()
state = st.session_state.chats_state
active_chat = _ensure_active_chat(state)
chat_history = active_chat["history"]
chat_vars = active_chat["vars"]

if backfill_history_metadata(chat_history):
    save_chats(state)

if (
    st.session_state.get("edit_target_chat_id") is not None
    and st.session_state.get("edit_target_chat_id") != active_chat.get("id")
):
    _clear_edit_state()

if (
    st.session_state.get("history_view_chat_id") is not None
    and st.session_state.get("history_view_chat_id") != active_chat.get("id")
):
    _clear_history_view()

with st.sidebar:
    st.header("Chats")

    chats = state.get("chats", [])
    page_size = 20
    if "chat_page" not in st.session_state:
        st.session_state["chat_page"] = 0
    total_pages = max(1, math.ceil(len(chats) / page_size))
    if st.session_state["chat_page"] > total_pages - 1:
        st.session_state["chat_page"] = total_pages - 1

    if st.button("New chat", use_container_width=True):
        chat = _new_chat(f"New Chat {len(chats) + 1}")
        chats.append(chat)
        state["active_chat_id"] = chat["id"]
        st.session_state["chat_page"] = (len(chats) - 1) // page_size
        save_chats(state)
        st.rerun()

    start_idx = st.session_state["chat_page"] * page_size
    end_idx = start_idx + page_size

    for chat in chats[start_idx:end_idx]:
        chat_id = chat.get("id")
        chat_name = chat.get("name", chat_id)
        is_active = chat_id == state.get("active_chat_id")

        cols = st.columns([0.82, 0.18], vertical_alignment="center")
        with cols[0]:
            label = f"• {chat_name}" if is_active else chat_name
            if st.button(label, key=f"select_{chat_id}", use_container_width=True):
                state["active_chat_id"] = chat_id
                save_chats(state)
                st.rerun()
        with cols[1]:
            popover = getattr(st, "popover", None)
            if popover:
                menu_ctx = popover("⋮")
            else:
                menu_ctx = st.expander("⋮", expanded=False)
            with menu_ctx:
                new_name = st.text_input(
                    "Rename",
                    value=chat_name,
                    key=f"rename_{chat_id}",
                    on_change=_rename_chat,
                    args=(chat_id,),
                )

                idx = chats.index(chat)
                move_up = st.button(
                    "Move up", key=f"up_{chat_id}", use_container_width=True
                )
                move_down = st.button(
                    "Move down", key=f"down_{chat_id}", use_container_width=True
                )
                if move_up and idx > 0:
                    chats[idx - 1], chats[idx] = chats[idx], chats[idx - 1]
                    save_chats(state)
                    st.rerun()
                if move_down and idx < len(chats) - 1:
                    chats[idx + 1], chats[idx] = chats[idx], chats[idx + 1]
                    save_chats(state)
                    st.rerun()

                if st.button(
                    "Delete", key=f"delete_{chat_id}", use_container_width=True
                ):
                    chats[:] = [c for c in chats if c.get("id") != chat_id]
                    _ensure_active_chat(state)
                    save_chats(state)
                    st.rerun()

    pager_cols = st.columns([0.25, 0.5, 0.25], vertical_alignment="center")
    with pager_cols[0]:
        if st.button(
            "‹",
            key="chats_prev",
            use_container_width=True,
            disabled=st.session_state["chat_page"] == 0,
        ):
            st.session_state["chat_page"] -= 1
            st.rerun()
    with pager_cols[1]:
        st.caption(f"{st.session_state['chat_page'] + 1}/{total_pages}")
    with pager_cols[2]:
        if st.button(
            "›",
            key="chats_next",
            use_container_width=True,
            disabled=st.session_state["chat_page"] >= total_pages - 1,
        ):
            st.session_state["chat_page"] += 1
            st.rerun()

    st.divider()

    st.header("Settings")

    st.subheader("Appearance")
    theme_options = [name for name in THEME_ORDER if name in THEMES]
    if current_theme not in theme_options:
        current_theme = THEME_DEFAULT
    st.selectbox(
        "Theme",
        theme_options,
        index=theme_options.index(current_theme),
        key="ui_theme",
    )

    mode = st.radio("Mode", ["Use DSL", "Raw LLM"], index=0)

    use_gemini = True
    if mode == "Use DSL":
        use_gemini = st.toggle("Run executor (turn off for debugging)", value=True)

    default_model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
    model_options = [
        ("Gemini 2.5 Flash", "gemini-2.5-flash"),
        ("Gemini 3 Flash", "gemini-3-flash-preview"),
        ("Gemini 3 Pro", "gemini-3-pro-preview"),
    ]
    model_ids = [m[1] for m in model_options]
    model_labels = [m[0] for m in model_options]
    model_index = model_ids.index(default_model) if default_model in model_ids else 0
    selected_label = st.selectbox("Model", model_labels, index=model_index)
    selected_model = model_options[model_labels.index(selected_label)][1]

    timeout_s = st.number_input(
        "Request timeout (seconds, 0 = no timeout)",
        min_value=0,
        max_value=600,
        value=120,
        step=10,
    )

    edit_msg = None
    if st.session_state.get("edit_target_chat_id") == active_chat.get("id"):
        edit_msg = _find_message_by_id(
            chat_history, st.session_state.get("edit_target_message_id")
        )
    if edit_msg is not None:
        meta = edit_msg.get("meta", {})
        version = meta.get("version", "?")
        st.caption(f"Editing version v{version}. Sending will create a new version.")
        if st.button("Cancel Edit", use_container_width=True):
            _clear_edit_state()
            st.rerun()

    st.subheader("Staging")
    with st.form("sidebar_staging_form", clear_on_submit=False):
        staging_text = st.text_area(
            "Draft",
            height=180,
            placeholder="Draft here (Ctrl+Enter to send)",
            key="sidebar_draft",
            label_visibility="collapsed",
            help="Ctrl+Enter sends this draft.",
        )
        draft_cols = st.columns(3)
        with draft_cols[0]:
            staging_send = st.form_submit_button(
                "↩", type="secondary", help="Send", use_container_width=True
            )
        with draft_cols[1]:
            st.form_submit_button(
                "×", help="Clear", on_click=_clear_draft, use_container_width=True
            )
        with draft_cols[2]:
            staging_fullscreen = st.form_submit_button(
                "⤢", help="Fullscreen", use_container_width=True
            )

    if staging_fullscreen:
        st.session_state["draft_fullscreen"] = True
        st.session_state["draft_dialog"] = st.session_state.get("sidebar_draft", "")
        st.rerun()

    if staging_send and staging_text:
        if mode == "Use DSL":
            if "/NEXT" in staging_text:
                st.warning("You used /NEXT. Use /THEN to start a new step.")
            edit_source_id = None
            if st.session_state.get("edit_target_chat_id") == active_chat.get("id"):
                edit_source_id = st.session_state.get("edit_target_message_id")
            _run_dsl(
                staging_text,
                use_gemini,
                timeout_s,
                selected_model,
                chat_history,
                chat_vars,
                state,
                edited_from_message_id=edit_source_id,
            )
            _clear_history_view()
            _clear_edit_state()
        else:
            _run_raw(staging_text, timeout_s, selected_model, chat_history, state)
            _clear_history_view()

draft_fullscreen = st.session_state.get("draft_fullscreen", False)
dialog_available = hasattr(st, "dialog")
if dialog_available:

    @st.dialog("Draft editor")
    def _draft_dialog() -> None:
        with st.form("draft_dialog_form", clear_on_submit=False):
            dialog_text = st.text_area(
                "Draft editor",
                height=500,
                key="draft_dialog",
                label_visibility="collapsed",
                placeholder="Draft here (Ctrl+Enter to send)",
            )
            dialog_send = st.form_submit_button("Send", type="primary")

        dialog_cols = st.columns(2)
        with dialog_cols[0]:
            st.button("Clear", on_click=_clear_draft, use_container_width=True)
        with dialog_cols[1]:
            if st.button("Close", use_container_width=True):
                st.session_state["draft_sync"] = st.session_state.get(
                    "draft_dialog", ""
                )
                st.session_state["draft_fullscreen"] = False
                st.rerun()

        if dialog_send and dialog_text:
            if mode == "Use DSL":
                if "/NEXT" in dialog_text:
                    st.warning("You used /NEXT. Use /THEN to start a new step.")
                edit_source_id = None
                if st.session_state.get("edit_target_chat_id") == active_chat.get("id"):
                    edit_source_id = st.session_state.get("edit_target_message_id")
                _run_dsl(
                    dialog_text,
                    use_gemini,
                    timeout_s,
                    selected_model,
                    chat_history,
                    chat_vars,
                    state,
                    edited_from_message_id=edit_source_id,
                )
                _clear_history_view()
                _clear_edit_state()
            else:
                _run_raw(dialog_text, timeout_s, selected_model, chat_history, state)
                _clear_history_view()
            st.session_state["draft_sync"] = st.session_state.get("draft_dialog", "")
            st.session_state["draft_fullscreen"] = False
            st.rerun()

    @st.dialog("Message Versions")
    def _versions_dialog() -> None:
        target_chat_id = st.session_state.get("versions_target_chat_id")
        thread_id = st.session_state.get("versions_target_thread_id")
        if target_chat_id != active_chat.get("id") or not thread_id:
            st.info("Open versions from a message in the active chat.")
            return

        versions = get_thread_versions(chat_history, thread_id)
        if not versions:
            st.info("No versions found for this message thread.")
            return

        labels = []
        for msg in versions:
            meta = msg.get("meta", {})
            labels.append(f"v{meta.get('version', '?')} · {str(msg.get('id', ''))[:10]}")

        selected_label = st.selectbox("Version", labels, index=len(labels) - 1)
        selected_idx = labels.index(selected_label)
        selected_msg = versions[selected_idx]
        selected_meta = selected_msg.get("meta", {})

        st.write("DSL")
        st.code(str(selected_msg.get("content", "")), language="text")

        run_id = selected_meta.get("run_id")
        if run_id:
            st.write("Model Responses")
            run_msgs = get_assistant_messages_for_run(chat_history, run_id)
            if run_msgs:
                for i, amsg in enumerate(run_msgs, start=1):
                    st.markdown(f"**Response {i}**")
                    st.write(str(amsg.get("content", "")))
            else:
                st.caption("No assistant responses linked to this run.")

        vars_before = selected_meta.get("vars_before")
        vars_after = selected_meta.get("vars_after")
        if vars_before is not None:
            st.write("Vars Before")
            st.json(vars_before)
        if vars_after is not None:
            st.write("Vars After")
            st.json(vars_after)

        selected_msg_id = selected_msg.get("id")
        viewing_selected = (
            st.session_state.get("history_view_chat_id") == active_chat.get("id")
            and st.session_state.get("history_view_message_id") == selected_msg_id
        )
        if viewing_selected:
            st.caption("Current chat is showing this version's timeline.")

        action_cols = st.columns(3)
        with action_cols[0]:
            if st.button(
                "View This Version",
                use_container_width=True,
                disabled=viewing_selected,
            ):
                _set_history_view(selected_msg_id, active_chat.get("id"))
                st.session_state["versions_open"] = False
                st.rerun()
        with action_cols[1]:
            if st.button("View Latest", use_container_width=True):
                _clear_history_view()
                st.session_state["versions_open"] = False
                st.rerun()
        with action_cols[2]:
            if st.button("Edit This Version", type="primary", use_container_width=True):
                _start_edit_from_message(selected_msg, active_chat.get("id"))
                st.session_state["versions_open"] = False
                st.rerun()

    @st.dialog("Copy Message")
    def _copy_dialog() -> None:
        target_chat_id = st.session_state.get("copy_target_chat_id")
        target_message_id = st.session_state.get("copy_target_message_id")
        if target_chat_id != active_chat.get("id") or not target_message_id:
            st.info("Open copy from a message in the active chat.")
            return

        msg = _find_message_by_id(chat_history, target_message_id)
        if msg is None:
            st.info("Message not found.")
            return

        st.caption("Use the copy icon on the code block:")
        st.code(str(msg.get("content", "")), language="text")

if draft_fullscreen:
    # Treat fullscreen as a one-shot open request so it doesn't reopen on
    # unrelated reruns (e.g., creating a new chat).
    st.session_state["draft_fullscreen"] = False
    if dialog_available:
        st.session_state.setdefault(
            "draft_dialog", st.session_state.get("sidebar_draft", "")
        )
        _draft_dialog()
    else:
        st.info("Fullscreen editor requires a newer Streamlit version.")

if st.session_state.get("versions_open", False):
    st.session_state["versions_open"] = False
    if dialog_available:
        _versions_dialog()
    else:
        st.info("Versions view requires a newer Streamlit version.")

if st.session_state.get("copy_open", False):
    st.session_state["copy_open"] = False
    if dialog_available:
        _copy_dialog()
    else:
        st.info("Copy dialog requires a newer Streamlit version.")

chat_slot = st.container()

composer_placeholder = (
    "Enter DSL (use /THEN to chain steps)"
    if mode == "Use DSL"
    else "Send a message"
)
prompt = st.chat_input(composer_placeholder, key="chat_composer")
if prompt:
    if mode == "Use DSL":
        if "/NEXT" in prompt:
            st.warning("You used /NEXT. Use /THEN to start a new step.")
        edit_source_id = None
        if st.session_state.get("edit_target_chat_id") == active_chat.get("id"):
            edit_source_id = st.session_state.get("edit_target_message_id")
        _run_dsl(
            prompt,
            use_gemini,
            timeout_s,
            selected_model,
            chat_history,
            chat_vars,
            state,
            edited_from_message_id=edit_source_id,
        )
        _clear_history_view()
        _clear_edit_state()
    else:
        _run_raw(prompt, timeout_s, selected_model, chat_history, state)
        _clear_history_view()

last_runs = st.session_state.get("last_run_by_chat", {})
active_last_run = last_runs.get(active_chat["id"])

history_view_msg = None
history_view_cutoff = None
if st.session_state.get("history_view_chat_id") == active_chat.get("id"):
    history_view_message_id = st.session_state.get("history_view_message_id")
    history_view_msg = _find_message_by_id(chat_history, history_view_message_id)
    history_view_cutoff = cutoff_index_for_version_view(chat_history, history_view_message_id)

display_history = project_visible_history(chat_history, cutoff_index=history_view_cutoff)

if mode == "Use DSL":
    vars_data = None
    if history_view_msg is not None:
        for msg in reversed(display_history):
            if msg.get("role") == "user" and msg.get("mode") == "dsl":
                meta = msg.get("meta", {})
                if isinstance(meta.get("vars_after"), dict):
                    vars_data = meta.get("vars_after")
                    break
        if vars_data is None:
            vars_data = {}
    elif active_last_run:
        vars_data = active_last_run["vars"] or {}

if mode == "Use DSL" and vars_data is not None:
    st.subheader("Variables")
    if vars_data:
        rows = []
        for name in sorted(vars_data):
            value = vars_data[name]
            rows.append(
                {
                    "Name": name,
                    "Tokens": _approx_token_count(value),
                    "Preview": _format_var_preview(value),
                }
            )
        st.table(rows)
    else:
        st.info("No variables yet.")

if history_view_msg is not None:
    view_meta = history_view_msg.get("meta", {})
    view_version = view_meta.get("version", "?")
    view_msg_id = str(history_view_msg.get("id", ""))[:10]
    info_cols = st.columns([0.78, 0.22], vertical_alignment="center")
    with info_cols[0]:
        st.info(f"Viewing timeline at version v{view_version} ({view_msg_id}).")
    with info_cols[1]:
        if st.button("Back to Latest", use_container_width=True):
            _clear_history_view()
            st.rerun()

with chat_slot:
    for idx, msg in enumerate(display_history):
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        with st.chat_message(role):
            if role == "assistant":
                cols = st.columns([0.9, 0.1])
                with cols[0]:
                    st.write(content)
                with cols[1]:
                    popover = getattr(st, "popover", None)
                    if popover:
                        menu_ctx = popover("⋮")
                    else:
                        menu_ctx = st.expander("⋮", expanded=False)
                    with menu_ctx:
                        meta = msg.get("meta")
                        if meta and "step_log" in meta:
                            st.write("Parsed Output")
                            st.json(meta["step_log"].get("parsed_json"))
                            st.write("Execution Log")
                            st.json(meta["step_log"])
                        elif meta and "execution_logs" in meta:
                            st.write("Parsed Steps")
                            st.json(meta.get("parsed_steps"))
                            st.write("Execution Logs")
                            st.json(meta.get("execution_logs"))
                            st.write("Vars After")
                            st.json(meta.get("vars_after"))
                        elif meta:
                            st.json(meta)
                        else:
                            st.write("No details available.")
            else:
                if msg.get("mode") == "dsl":
                    cols = st.columns([0.9, 0.1])
                    with cols[0]:
                        st.write(content)
                    with cols[1]:
                        popover = getattr(st, "popover", None)
                        if popover:
                            menu_ctx = popover("⋮")
                        else:
                            menu_ctx = st.expander("⋮", expanded=False)
                        with menu_ctx:
                            msg_id = str(msg.get("id", idx))
                            msg_meta = msg.get("meta", {})
                            thread_id = msg_meta.get("thread_id") or msg.get("id")
                            if st.button(
                                "Edit",
                                key=f"edit_{active_chat['id']}_{msg_id}",
                                help="Edit message",
                                use_container_width=False,
                            ):
                                _start_edit_from_message(msg, active_chat.get("id"))
                                st.rerun()
                            if thread_id and st.button(
                                "Versions",
                                key=f"versions_{active_chat['id']}_{msg_id}",
                                use_container_width=False,
                            ):
                                _open_versions_for_thread(thread_id, active_chat.get("id"))
                                st.rerun()
                            if st.button(
                                "Copy",
                                key=f"copy_{active_chat['id']}_{msg_id}",
                                use_container_width=False,
                            ):
                                _open_copy_for_message(msg, active_chat.get("id"))
                                st.rerun()
                else:
                    st.write(content)

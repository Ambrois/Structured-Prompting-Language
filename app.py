from __future__ import annotations

import uuid

import streamlit as st

from example_parser import ParseError, parse_dsl, _steps_to_dicts
from executor import execute_steps, execute_steps_stub
from gemini_client import call_gemini
from state_store import load_chats, save_chats


st.set_page_config(page_title="DSL Runner", layout="wide")

st.title("DSL Runner")

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


def _run_dsl(
    input_text: str,
    use_gemini: bool,
    timeout_s: float,
    chat_history: list,
    chat_vars: dict,
    state: dict,
) -> None:
    if input_text.strip() == "":
        return
    try:
        steps = parse_dsl(input_text, sigil="@")
    except ParseError as e:
        st.error(f"Parse error: {e}")
        st.stop()

    ctx = dict(chat_vars)
    try:
        if use_gemini:
            ctx, logs, non_var_outputs = execute_steps(
                steps, ctx, timeout_s=timeout_s, chat_history=chat_history
            )
        else:
            ctx, logs, non_var_outputs = execute_steps_stub(
                steps, ctx, timeout_s=timeout_s, chat_history=chat_history
            )
    except Exception as e:
        st.error(f"Execution error: {e}")
        st.stop()

    chat_history.append({"role": "user", "content": input_text, "mode": "dsl"})
    if non_var_outputs:
        for out in non_var_outputs:
            chat_history.append({"role": "assistant", "content": out, "mode": "dsl"})
    else:
        chat_history.append(
            {
                "role": "assistant",
                "content": "(no visible output; all steps produced variables)",
                "mode": "dsl",
            }
        )
    active_chat["vars"] = ctx
    save_chats(state)

    last_runs = st.session_state.setdefault("last_run_by_chat", {})
    last_runs[active_chat["id"]] = {
        "steps": _steps_to_dicts(steps),
        "logs": logs,
        "vars": ctx,
    }


def _run_raw(
    raw_text: str,
    timeout_s: float,
    chat_history: list,
    state: dict,
) -> None:
    if raw_text.strip() == "":
        return
    try:
        response_text = call_gemini(raw_text, timeout_s=timeout_s)
    except Exception as e:
        st.error(f"Execution error: {e}")
        st.stop()

    chat_history.append({"role": "user", "content": raw_text, "mode": "raw"})
    chat_history.append({"role": "assistant", "content": response_text, "mode": "raw"})
    save_chats(state)

if "chats_state" not in st.session_state:
    st.session_state.chats_state = load_chats()
state = st.session_state.chats_state
active_chat = _ensure_active_chat(state)

with st.sidebar:
    st.header("Chats")

    chats = state.get("chats", [])

    if st.button("New chat", use_container_width=True):
        chat = _new_chat(f"New Chat {len(chats) + 1}")
        chats.append(chat)
        state["active_chat_id"] = chat["id"]
        save_chats(state)
        st.rerun()

    for chat in chats:
        chat_id = chat.get("id")
        chat_name = chat.get("name", chat_id)
        is_active = chat_id == state.get("active_chat_id")

        cols = st.columns([0.88, 0.12])
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

    st.divider()

mode = st.radio("Mode", ["Parse + Execute", "Raw LLM"], index=0)

use_gemini = True
if mode == "Parse + Execute":
    use_gemini = st.toggle("Use Gemini executor", value=True)

timeout_s = st.number_input(
    "Request timeout (seconds, 0 = no timeout)",
    min_value=0,
    max_value=600,
    value=120,
    step=10,
)

chat_slot = st.container()
chat_history = active_chat["history"]
chat_vars = active_chat["vars"]

st.subheader("Input")
if mode == "Parse + Execute":
    with st.form("dsl_form", clear_on_submit=True):
        input_text = st.text_area(
            "DSL text",
            height=200,
            help="Tip: Ctrl+Enter to run",
            key="dsl_input",
        )
        run = st.form_submit_button("Run", type="primary")

    if run:
        _run_dsl(input_text, use_gemini, timeout_s, chat_history, chat_vars, state)

    # staging removed
else:
    with st.form("raw_form", clear_on_submit=True):
        raw_text = st.text_area(
            "Message",
            height=200,
            help="Tip: Ctrl+Enter to send",
            key="raw_input",
        )
        send = st.form_submit_button("Send", type="primary")

    if send:
        _run_raw(raw_text, timeout_s, chat_history, state)

    # staging removed

last_runs = st.session_state.get("last_run_by_chat", {})
active_last_run = last_runs.get(active_chat["id"])

if mode == "Parse + Execute" and active_last_run:
    st.subheader("Parsed Steps")
    st.json(active_last_run["steps"])

    st.subheader("Execution Logs")
    st.json(active_last_run["logs"])

    st.subheader("Variables")
    st.json(active_last_run["vars"])

with chat_slot:
    st.subheader("Chat")
    for msg in chat_history:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        st.chat_message(role).write(content)

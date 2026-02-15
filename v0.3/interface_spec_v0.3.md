# Chat DSL v0.2 Interface Specification

## 1. Purpose

This document specifies the **current UI behavior** of the `v0.2` Streamlit app (`v0.2/app.py`).

It covers:
- visual layout and controls
- interaction flows
- timeline/version semantics
- persistence and message metadata used by the interface

It does not redefine DSL syntax/runtime rules (see `v0.2/spec_v0.2.md`).

---

## 2. Runtime Context

- Framework: Streamlit
- Entry point: `streamlit run v0.2/app.py`
- Primary persisted state file: `v0.2/state/chats.json`
- Optional environment variables:
  - `GEMINI_API_KEY`
  - `GEMINI_MODEL`
  - `GEMINI_TIMEOUT`
  - `GEMINI_API_BASE`

---

## 3. Information Architecture

The app has two main regions:

1. Sidebar
- chat list and chat management
- settings
- staging editor

2. Main panel
- chat composer (`st.chat_input`)
- variables panel (DSL mode)
- timeline status banner (when viewing historical version)
- chat transcript

---

## 4. Sidebar Specification

### 4.1 Chats Section

Controls:
- `New chat`
- Paginated chat list (page size = 20)
- Per-chat menu (`⋮`) with:
  - Rename (text input, immediate apply)
  - `Move up`
  - `Move down`
  - `Delete`
- Pagination:
  - previous `‹`
  - page indicator `current/total`
  - next `›`

Behavior:
- Active chat label is prefixed with `•`.
- Selecting a chat updates `active_chat_id` and reruns.
- Delete removes only selected chat; app ensures some chat remains active.

### 4.2 Settings Section

Controls:
- Theme select:
  - `Gruvbox Dark`
  - `Paper White (WIP)`
  - `Default`
- Mode radio:
  - `Use DSL`
  - `Raw LLM`
- DSL-only toggle:
  - `Run executor (turn off for debugging)`
    - On: uses Gemini caller in executor
    - Off: executor uses stub responses
- Model select:
  - `Gemini 2.5 Flash` (`gemini-2.5-flash`)
  - `Gemini 3 Flash` (`gemini-3-flash-preview`)
  - `Gemini 3 Pro` (`gemini-3-pro-preview`)
- Timeout number input:
  - label: `Request timeout (seconds, 0 = no timeout)`
  - range: `0..600`, step `10`, default `120`

### 4.3 Edit Status

When edit mode is active for current chat:
- shows caption: `Editing version vN. Sending will create a new version.`
- `Cancel Edit` button clears edit target.

### 4.4 Staging Editor

Form-based draft editor:
- text area (`sidebar_draft`)
- actions:
  - `↩` send
  - `×` clear
  - `⤢` open fullscreen dialog

Rules:
- If sent text contains `/NEXT`, show warning: `You used /NEXT. Use /THEN to start a new step.`
- Sending in DSL mode executes `_run_dsl`.
- Sending in Raw mode executes `_run_raw`.

---

## 5. Main Composer Specification

Control:
- `st.chat_input` (`chat_composer`)

Placeholder:
- DSL mode: `Enter DSL (use /THEN to chain steps)`
- Raw mode: `Send a message`

Rules:
- Empty input ignored.
- `/NEXT` warning shown in DSL mode.
- On send, clears historical-version view state and (if set) edit state after execution.

---

## 6. Dialogs

Dialogs are used when `st.dialog` is available.

### 6.1 Draft Editor Dialog

Title: `Draft editor`

Contents:
- large text area (`draft_dialog`)
- `Send` (primary)
- `Clear`
- `Close`

Behavior:
- Send path mirrors staging send behavior.
- Close syncs dialog text back to sidebar draft.

### 6.2 Message Versions Dialog

Title: `Message Versions`

Inputs:
- version selector (`Version`) for one thread

Sections:
- DSL source (`st.code`)
- model responses for selected run
- `Vars Before` JSON
- `Vars After` JSON

Actions:
- `View This Version`: enters historical timeline view for selected version
- `View Latest`: exits historical timeline view
- `Edit This Version`: starts edit mode from selected version

### 6.3 Copy Message Dialog

Title: `Copy Message`

Contents:
- caption instructing to use code-block copy icon
- message body in `st.code` for native copy action

---

## 7. Transcript Rendering

### 7.1 Display Source

The persisted chat history is append-only, but the UI renders a **projected timeline**:
- `display_history = project_visible_history(chat_history, cutoff_index=...)`

This projection applies version-branch semantics and optional historical cutoff.

### 7.2 Message Rendering

For each displayed message:
- assistant: content plus `⋮` details menu
- user DSL: content plus `⋮` actions menu
- user Raw: content only (no menu)

### 7.3 Assistant Menu (`⋮`)

Shows metadata based on available keys:
- `step_log`:
  - Parsed Output
  - Execution Log
- or execution bundle:
  - Parsed Steps
  - Execution Logs
  - Vars After
- or raw meta JSON
- or `No details available.`

### 7.4 User DSL Menu (`⋮`)

Buttons:
- `Edit`
- `Versions`
- `Copy`

Popover styling:
- compact width constrained (`max-width: min(90vw, 22rem)`)
- action controls are visually normalized across button roles

---

## 8. Variables Panel

Shown only in `Use DSL` mode.

Data source priority:
1. If historical version view is active: latest user DSL message in displayed timeline (`vars_after`)
2. Else: `last_run_by_chat[active_chat_id].vars` (session-memory cache)

Display format:
- table with columns:
  - `Name`
  - `Tokens` (approx `len(text)//4`)
  - `Preview` (truncated, newline-escaped)

If empty: `No variables yet.`

---

## 9. Timeline and Versioning Semantics

### 9.1 Message Identity and Version Metadata

Each DSL user message carries:
- `id`
- `meta.thread_id`
- `meta.version`
- `meta.run_id`
- `meta.parsed_steps`
- `meta.execution_logs`
- `meta.vars_before`
- `meta.vars_after`

Edits additionally include:
- `meta.edited_from_message_id`
- `meta.source_cutoff_index`

Assistant messages carry:
- `meta.run_id`
- `meta.source_user_message_id`
- optional `meta.step_log`

Raw-mode messages carry `run_id`; raw assistant also stores `raw_response`.

### 9.2 Edit Execution Context

Editing a DSL user message:
- creates a **new immutable version** in the same thread (`version = next_version_for_thread`)
- executes from the edited message’s `vars_before` (historical variable context)
- stores source cutoff used to preserve historical branch context

### 9.3 Replace-After-Edit Behavior

Displayed timeline semantics:
- an edit replaces the edited message **and everything after it** in the visible timeline
- persisted history remains append-only for auditability

### 9.4 Historical Version View

When viewing a selected version:
- app computes a cutoff index where that version is still visible in projected timeline
- transcript displays projected timeline up to that cutoff
- banner shown: `Viewing timeline at version vN (id-prefix).`
- `Back to Latest` exits historical view

### 9.5 Branch Preservation

If a message is edited from older context where ancestors have since changed:
- projection can restore the source prefix using `source_cutoff_index`
- this preserves both historical chat context and variable lineage for that edit branch

---

## 10. Run Modes

### 10.1 Use DSL Mode

Path:
- parse DSL
- execute steps via executor
- optional Gemini call per step (or stub if toggle off)

Output:
- one user DSL message
- one or more assistant DSL outputs (or synthetic no-visible-output assistant message)

Errors:
- parse/runtime errors shown via `st.error(...)` and stop current run

### 10.2 Raw LLM Mode

Path:
- send raw prompt directly to Gemini client
- append user raw + assistant raw messages

No DSL parsing/execution logs in this mode.

---

## 11. JSON Contract Visibility in UI

The interface assumes DSL runtime contract:
- per-step model response JSON with `error` and `out`
- optional typed `vars` payload for `/DEF`

The UI exposes resulting parsed logs and vars via assistant metadata menu and versions dialog.

---

## 12. Persistence Model

`state_store_v02.py` persists chat state to:
- `v0.2/state/chats.json`

Backward-compatible bootstrap:
- if `chats.json` missing, loads legacy `vars.json` + `chat_history.json` into default chat.

On app load:
- `backfill_history_metadata(...)` retrofits legacy messages with IDs/run/thread/version linkage.

---

## 13. Session State Keys (UI)

Key transient keys used by interface:
- `chats_state`
- `chat_page`
- `ui_theme`
- `chat_composer`
- `sidebar_draft`
- `draft_dialog`
- `draft_fullscreen`
- `edit_target_chat_id`
- `edit_target_message_id`
- `versions_target_chat_id`
- `versions_target_thread_id`
- `versions_open`
- `copy_target_chat_id`
- `copy_target_message_id`
- `copy_open`
- `history_view_chat_id`
- `history_view_message_id`
- `last_run_by_chat`

---

## 14. UX Notes and Constraints

- Menus rely on Streamlit popover when available; fallback is expander.
- Dialog features require Streamlit builds that support `st.dialog`; otherwise info messages are shown.
- LaTeX rendering is not custom; message content is rendered via `st.write` (markdown behavior).
- Copy is provided via native code-block copy affordance in the Copy dialog.

---

## 15. Acceptance Checklist (Current UI)

- Multi-chat create/select/rename/reorder/delete works.
- DSL and Raw modes both send successfully.
- Edit creates new version and visible timeline replaces suffix.
- Versions dialog can switch between latest and historical timeline views.
- Historical branch edits preserve historical context and variables.
- Copy dialog opens from user DSL message menu.
- Variables panel reflects current displayed timeline in historical view.
- State persists across app reloads via `state/chats.json`.


from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


def new_message_id(prefix: str = "msg") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _meta(msg: Dict[str, Any]) -> Dict[str, Any]:
    meta = msg.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        msg["meta"] = meta
    return meta


def backfill_history_metadata(history: List[Dict[str, Any]]) -> bool:
    """
    Make legacy history records compatible with versioned runs.
    Mutates history in place and returns whether anything changed.
    """
    changed = False
    current_run_id: Optional[str] = None
    current_user_id: Optional[str] = None

    for msg in history:
        if not isinstance(msg, dict):
            continue
        if not msg.get("id"):
            msg["id"] = new_message_id("msg")
            changed = True

        role = msg.get("role")
        mode = msg.get("mode")

        if role == "user" and mode == "dsl":
            meta = _meta(msg)
            if not meta.get("thread_id"):
                meta["thread_id"] = msg["id"]
                changed = True
            if not isinstance(meta.get("version"), int) or meta["version"] < 1:
                meta["version"] = 1
                changed = True
            if not meta.get("run_id"):
                meta["run_id"] = f"run-{msg['id']}"
                changed = True

            current_run_id = meta["run_id"]
            current_user_id = msg["id"]
            continue

        if role == "assistant":
            if current_run_id is not None:
                meta = _meta(msg)
                if not meta.get("run_id"):
                    meta["run_id"] = current_run_id
                    changed = True
                if current_user_id and not meta.get("source_user_message_id"):
                    meta["source_user_message_id"] = current_user_id
                    changed = True
            continue

        if role == "user":
            current_run_id = None
            current_user_id = None

    return changed


def next_version_for_thread(history: List[Dict[str, Any]], thread_id: str) -> int:
    max_version = 0
    for msg in history:
        if msg.get("role") != "user" or msg.get("mode") != "dsl":
            continue
        meta = msg.get("meta", {})
        if meta.get("thread_id") != thread_id:
            continue
        v = meta.get("version")
        if isinstance(v, int) and v > max_version:
            max_version = v
    return max_version + 1


def get_thread_versions(history: List[Dict[str, Any]], thread_id: str) -> List[Dict[str, Any]]:
    versions: List[Dict[str, Any]] = []
    for idx, msg in enumerate(history):
        if msg.get("role") != "user" or msg.get("mode") != "dsl":
            continue
        meta = msg.get("meta", {})
        if meta.get("thread_id") == thread_id:
            versions.append({"msg": msg, "index": idx})
    versions.sort(
        key=lambda it: (
            it["msg"].get("meta", {}).get("version", 0),
            it["index"],
        )
    )
    return [it["msg"] for it in versions]


def get_assistant_messages_for_run(
    history: List[Dict[str, Any]], run_id: str
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        meta = msg.get("meta", {})
        if meta.get("run_id") == run_id:
            out.append(msg)
    return out


def find_message_index(history: List[Dict[str, Any]], message_id: str | None) -> int | None:
    if not message_id:
        return None
    for idx, msg in enumerate(history):
        if msg.get("id") == message_id:
            return idx
    return None


def cutoff_index_for_version_view(
    history: List[Dict[str, Any]], version_message_id: str | None
) -> int:
    """
    Return the latest cutoff index where the selected message is still visible
    in the projected timeline. This preserves historical context even when the
    message is later hidden by an edit to an ancestor thread.
    """
    if not history:
        return -1
    msg_idx = find_message_index(history, version_message_id)
    if msg_idx is None:
        return len(history) - 1
    target_id = history[msg_idx].get("id")
    if not isinstance(target_id, str):
        return msg_idx

    last_visible_cutoff = msg_idx
    for cutoff in range(msg_idx, len(history)):
        projected_indices = project_visible_history_indices(history, cutoff_index=cutoff)
        visible_ids = {history[idx].get("id") for idx in projected_indices}
        if target_id in visible_ids:
            last_visible_cutoff = cutoff
        else:
            break
    return last_visible_cutoff


def project_visible_history_indices(
    history: List[Dict[str, Any]], cutoff_index: int | None = None
) -> List[int]:
    """
    Project append-only history into the active timeline by applying each edit
    (`edited_from_message_id`) as a suffix replacement.
    """
    if not history:
        return []

    last_idx = len(history) - 1 if cutoff_index is None else min(cutoff_index, len(history) - 1)
    if last_idx < 0:
        return []

    visible_indices: List[int] = []
    visible_pos_by_id: Dict[str, int] = {}

    for idx, msg in enumerate(history):
        if idx > last_idx:
            break
        if not isinstance(msg, dict):
            continue

        if msg.get("role") == "user" and msg.get("mode") == "dsl":
            meta = msg.get("meta", {})
            edited_from_id = meta.get("edited_from_message_id")
            if isinstance(edited_from_id, str):
                if edited_from_id not in visible_pos_by_id:
                    source_cutoff = meta.get("source_cutoff_index")
                    if isinstance(source_cutoff, int):
                        source_cutoff = max(-1, min(source_cutoff, idx - 1))
                        reset_visible = project_visible_history_indices(
                            history, cutoff_index=source_cutoff
                        )
                        visible_indices = list(reset_visible)
                        visible_pos_by_id = {}
                        for pos, vis_idx in enumerate(visible_indices):
                            vis_id = history[vis_idx].get("id")
                            if isinstance(vis_id, str):
                                visible_pos_by_id[vis_id] = pos

                if edited_from_id in visible_pos_by_id:
                    keep_pos = visible_pos_by_id[edited_from_id]
                    removed = visible_indices[keep_pos:]
                    for rem_idx in removed:
                        rem_id = history[rem_idx].get("id")
                        if isinstance(rem_id, str):
                            visible_pos_by_id.pop(rem_id, None)
                    visible_indices = visible_indices[:keep_pos]

        visible_indices.append(idx)
        msg_id = msg.get("id")
        if isinstance(msg_id, str):
            visible_pos_by_id[msg_id] = len(visible_indices) - 1

    return visible_indices


def project_visible_history(
    history: List[Dict[str, Any]], cutoff_index: int | None = None
) -> List[Dict[str, Any]]:
    indices = project_visible_history_indices(history, cutoff_index=cutoff_index)
    return [history[idx] for idx in indices]

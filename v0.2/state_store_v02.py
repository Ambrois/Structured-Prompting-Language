from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


_STATE_DIR = Path(__file__).resolve().parent / "state"
_VARS_PATH = _STATE_DIR / "vars.json"
_HISTORY_PATH = _STATE_DIR / "chat_history.json"
_CHATS_PATH = _STATE_DIR / "chats.json"


def _ensure_state_dir() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    data = path.read_text(encoding="utf-8")
    if data.strip() == "":
        return default
    return json.loads(data)


def _save_json(path: Path, data: Any) -> None:
    _ensure_state_dir()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_vars() -> Dict[str, Any]:
    _ensure_state_dir()
    loaded = _load_json(_VARS_PATH, default={})
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected vars.json to contain an object, got {type(loaded).__name__}")
    return loaded


def save_vars(vars_dict: Dict[str, Any]) -> None:
    if not isinstance(vars_dict, dict):
        raise ValueError("vars_dict must be a dict")
    _save_json(_VARS_PATH, vars_dict)


def load_history() -> List[Dict[str, Any]]:
    _ensure_state_dir()
    loaded = _load_json(_HISTORY_PATH, default=[])
    if not isinstance(loaded, list):
        raise ValueError(
            f"Expected chat_history.json to contain a list, got {type(loaded).__name__}"
        )
    return loaded


def save_history(history: List[Dict[str, Any]]) -> None:
    if not isinstance(history, list):
        raise ValueError("history must be a list")
    _save_json(_HISTORY_PATH, history)


def load_chats() -> Dict[str, Any]:
    _ensure_state_dir()
    if _CHATS_PATH.exists():
        loaded = _load_json(_CHATS_PATH, default=None)
        if not isinstance(loaded, dict):
            raise ValueError(
                f"Expected chats.json to contain an object, got {type(loaded).__name__}"
            )
        if "chats" not in loaded or not isinstance(loaded["chats"], list):
            raise ValueError("chats.json missing 'chats' list")
        if "active_chat_id" not in loaded:
            raise ValueError("chats.json missing 'active_chat_id'")
        return loaded

    # Backward-compatible bootstrap from legacy vars/history files.
    legacy_vars = load_vars()
    legacy_history = load_history()
    chat_id = "chat-1"
    return {
        "active_chat_id": chat_id,
        "chats": [
            {
                "id": chat_id,
                "name": "Default",
                "history": legacy_history,
                "vars": legacy_vars,
            }
        ],
    }


def save_chats(state: Dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be a dict")
    _save_json(_CHATS_PATH, state)

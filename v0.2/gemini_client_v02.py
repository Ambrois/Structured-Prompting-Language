from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


_DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_API_BASE = os.environ.get(
    "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
)
_RETRY_MAX = 3
_RETRY_BASE_DELAY_S = 1.0


def _get_default_timeout() -> float:
    raw = os.environ.get("GEMINI_TIMEOUT", "120")
    try:
        return float(raw)
    except ValueError:
        return 120.0


def call_gemini(
    prompt: str,
    model: Optional[str] = None,
    timeout_s: Optional[float] = None,
    response_schema: Optional[Dict[str, Any]] = None,
) -> str:
    if not isinstance(prompt, str) or prompt.strip() == "":
        raise ValueError("prompt must be a non-empty string")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set")

    model_name = model or _DEFAULT_MODEL
    url = f"{_API_BASE}/models/{model_name}:generateContent"

    generation_config: Dict[str, Any] = {
        "responseMimeType": "application/json",
    }
    if response_schema is not None:
        generation_config["responseSchema"] = response_schema

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        # Ask Gemini to emit JSON text directly to reduce markdown/prose drift.
        "generationConfig": generation_config,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    timeout = _get_default_timeout() if timeout_s is None else float(timeout_s)
    timeout_arg = None if timeout <= 0 else timeout

    for attempt in range(_RETRY_MAX + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_arg) as resp:
                data = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 503 and attempt < _RETRY_MAX:
                delay = _RETRY_BASE_DELAY_S * (2 ** attempt)
                delay += random.random() * 0.25
                time.sleep(delay)
                continue
            raise RuntimeError(f"Gemini HTTP error {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Gemini connection error: {e}") from e

    if "error" in data:
        raise RuntimeError(f"Gemini API error: {data['error']}")

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")

    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    text = "".join(texts).strip()
    if text == "":
        raise RuntimeError("Gemini returned empty text")

    return text

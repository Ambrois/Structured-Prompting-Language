from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional


_DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_API_BASE = os.environ.get(
    "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
)

def _get_default_timeout() -> float:
    raw = os.environ.get("GEMINI_TIMEOUT", "120")
    try:
        return float(raw)
    except ValueError:
        return 120.0


def call_gemini(
    prompt: str, model: Optional[str] = None, timeout_s: Optional[float] = None
) -> str:
    if not isinstance(prompt, str) or prompt.strip() == "":
        raise ValueError("prompt must be a non-empty string")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set")

    model_name = model or _DEFAULT_MODEL
    url = f"{_API_BASE}/models/{model_name}:generateContent"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
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

    try:
        with urllib.request.urlopen(req, timeout=timeout_arg) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
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

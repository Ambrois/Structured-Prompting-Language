from __future__ import annotations

import io
import json
import sys
from pathlib import Path


V02_DIR = Path(__file__).resolve().parents[1]
if str(V02_DIR) not in sys.path:
    sys.path.insert(0, str(V02_DIR))

import gemini_client_v02


def test_call_gemini_requests_json_mime_type(monkeypatch) -> None:
    captured: dict = {}

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        response_data = {
            "candidates": [
                {"content": {"parts": [{"text": '{"error":0,"out":"ok"}'}]}}
            ]
        }
        return FakeResp(json.dumps(response_data).encode("utf-8"))

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_client_v02.urllib.request, "urlopen", fake_urlopen)

    schema = {
        "type": "object",
        "properties": {"error": {"type": "integer"}, "out": {"type": "string"}},
        "required": ["error", "out"],
    }
    out = gemini_client_v02.call_gemini(
        "hello", model="gemini-2.5-flash", timeout_s=7, response_schema=schema
    )
    assert out == '{"error":0,"out":"ok"}'
    assert captured["payload"]["generationConfig"]["responseMimeType"] == "application/json"
    assert captured["payload"]["generationConfig"]["responseSchema"] == schema

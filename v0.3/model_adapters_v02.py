from __future__ import annotations

from typing import Optional

from executor_v02 import ModelCall, ResponseSchema
from gemini_client_v02 import call_gemini


def make_gemini_caller(model: Optional[str], timeout_s: float) -> ModelCall:
    def _caller(prompt: str, response_schema: ResponseSchema) -> str:
        return call_gemini(
            prompt,
            model=model,
            timeout_s=timeout_s,
            response_schema=response_schema,
        )

    return _caller

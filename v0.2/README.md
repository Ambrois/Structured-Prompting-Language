# Chat DSL v0.2

This folder contains the v0.2 specification, parser/executor implementation, and tests.

- `spec_v0.2.md`: formal v0.2 language and runtime specification
- `parser_v02.py`: parser for v0.2 command syntax and parse-time validation
- `executor_v02.py`: executor for prompt building, JSON contract checks, type checks, and fail-fast runtime semantics
- `runtime_v02.py`: app-facing wrapper for parse + execute with structured success/error results
- `gemini_client_v02.py`: Gemini HTTP client for optional live execution
- `model_adapters_v02.py`: adapter builders for model callers
- `app.py`: Streamlit UI for trying v0.2 interactively
- `tests/`: pytest suite covering parser + executor behavior

## Run tests

```bash
pytest -q v0.2/tests
```

## Run app

```bash
streamlit run v0.2/app.py
```

App modes:
- `Stub`: no external model call; executor uses built-in JSON stub outputs.
- `Gemini`: uses `GEMINI_API_KEY` and expects model output to follow v0.2 JSON contract.

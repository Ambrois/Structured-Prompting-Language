# Chat DSL v0.2

This folder contains the v0.2 specification, parser/executor implementation, and tests.
Checkpoint: UI parity migration with v0.1 layout is in progress.

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
- `Gemini`: uses `GEMINI_API_KEY` and sends both `responseMimeType=application/json` and a per-step `responseSchema` generated from `/DEF` declarations.

Implementation note: structured output schema enforcement is being integrated for Gemini mode.

## Multiline `/AS` in `/DEF`

`/AS` payload for variable definitions can span multiple lines.
Continuation lines are consumed until the next command line.

Example:

```txt
Write summary
/DEF summary
/AS first line about @topic
second line with extra detail
third line
```

Inline `/DEF ... /AS ...` also supports continuation:

```txt
Write summary
/DEF summary /AS first line
second line
```

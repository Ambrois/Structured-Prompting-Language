# Chat DSL v0.3

This folder contains the v0.3 specification, parser/executor implementation, and tests.

- `spec_changes_from_last.md`: authoritative v0.3 updates from v0.2
- `dsl_v0.3_specs.md`: compiled v0.3 aggregate spec
- `parser_v02.py`: parser with v0.3 `/FROM` mixed items and `/IN` handling
- `executor_v02.py`: executor with built-ins and cheap-model prefilter pipeline
- `runtime_v02.py`: app-facing wrapper for parse + execute with structured success/error results
- `gemini_client_v02.py`: Gemini HTTP client for optional live execution
- `model_adapters_v02.py`: adapter builders for model callers
- `app.py`: Streamlit UI for trying v0.2 interactively
- `tests/`: pytest suite covering parser + executor behavior

## Run tests

```bash
python -m pytest -q v0.3/tests
```

## Run app

```bash
streamlit run v0.3/app.py
```

App modes:
- `Stub`: no external model call; executor uses built-in JSON stub outputs.
- `Gemini`: runs a main model call for each step and cheap-model prefilter calls for natural-language `/FROM` inputs.

Model selection:
- `Model`: main per-step model.
- `Cheap Model`: prefilter model used for natural-language `/FROM` elements. Default: `gemini-3-flash-preview`.

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

## Chat Versioning UX

In chat history, user DSL messages have a `⋮` menu with:
- `Edit & Resend`: opens the message content in the draft editor and sends as a new immutable version.
- `Versions`: shows all versions for that message thread and the assistant responses for each run.

Each DSL run is stored with stable metadata (`thread_id`, `version`, `run_id`) so previous versions and outputs remain inspectable.

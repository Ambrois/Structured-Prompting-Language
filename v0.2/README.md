# Chat DSL v0.2

This folder contains the v0.2 specification, parser/executor implementation, and tests.

- `spec_v0.2.md`: formal v0.2 language and runtime specification
- `parser_v02.py`: parser for v0.2 command syntax and parse-time validation
- `executor_v02.py`: executor for prompt building, JSON contract checks, type checks, and fail-fast runtime semantics
- `tests/`: pytest suite covering parser + executor behavior

## Run tests

```bash
pytest -q v0.2/tests
```

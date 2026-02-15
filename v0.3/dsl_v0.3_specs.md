# DSL v0.3

## 1. Scope

This standard defines a lightweight, natural-language–first DSL for expressing **multi-step tasks** with:

- Sequential control flow  
- Explicit variable binding  
- Strict input restriction  
- Typed variable outputs  
- Structured model responses  

The system is:

- General-purpose  
- Deterministic to parse  
- Nondeterministic at execution time (LLM-driven)

---

## 2. Models

The implementation defines two configurable LLM endpoints:

- **Main Model** — primary execution model  
- **Cheap Model** — lower-cost alternative  

Model routing is implementation-defined and not part of DSL syntax.

---

## 3. Definitions

### Timeline
A single editable chain of user messages and model responses.

### Chat History
All user messages and all model replies (the `out` field from each valid JSON step response).

---

## 4. Built-in Variables

The following predefined variables always exist:

- `@ALL`  
  Contains:
  - Entire chat history from the current timeline  
  - All variables defined in the current timeline  

- `@CHAT`  
  Contains:
  - Entire chat history only  

These behave like regular variables for `/FROM` purposes.

---

## 5. Core Concepts

### 5.1 Step

A **step** consists of:

1. Instruction text (natural language; required)  
2. Zero or more directives  

The first step begins at the start of the document.

A new step begins at a line starting with:

```
/THEN
```

---

### 5.2 Variable

A variable:

- Name must:
  - Contain letters and underscores  
  - May contain digits  
  - May not begin with a digit  
- Is referenced using a sigil (default: `@`)  
- Persists across subsequent steps  
- May be overwritten  

Forward references are not allowed.

---

## 6. Step Structure

Within a step:

- Instruction text must appear first.
- Directives begin on the first nonwhitespace character of a line.
- Indentation is cosmetic only.

---

## 7. Directives

### 7.1 `/FROM`

Declares accessible inputs for the step.

#### Syntax

```
/FROM element1, element2, ...
```

Each comma-separated element is interpreted independently as one of:

---

#### (A) Variable Reference

```
@varname
```

Grants full access to that variable.

Parse-time error if undefined.

---

#### (B) Unscoped Natural-Language Description

```
description text
```

Interpreted as a `nat`-typed description scoped to `@ALL`.

---

#### (C) Scoped Natural-Language Description (`/IN` Extension)

```
description text /IN @varname
```

Rules:

- `/IN` must:
  - Appear immediately after a non-empty description  
  - Be followed by exactly one sigil-prefixed variable  
- Binds only to the immediately preceding description  
- The scoped variable must already exist  

Semantics:

- Restricts the description’s search scope to `@varname` only  
- Does not grant full access to the variable  

---

#### `/FROM` Global Rules

If `/FROM` is present:

- Only listed elements are accessible.

If `/FROM` is absent:

- All chat history is accessible  
- All variables are accessible  

Parse-time errors:

- Referencing variable not listed in `/FROM`  
- `/FROM` referencing undefined variable  
- `/IN` without preceding description  
- `/IN` not followed by exactly one variable  
- `/IN` applied to variable reference  
- Unknown directive  

---

### 7.2 `/DEF`

Declares a variable to be produced by the step.

#### Syntax

```
/DEF varname /TYPE type /AS description
```

or

```
/DEF varname /AS description /TYPE type
```

Block ends at next directive or EOF.

Rules:

- At most one `/AS`
- At most one `/TYPE`
- If `/AS` omitted → defaults to variable name
- If `/TYPE` omitted → defaults to `nat`

Allowed types:

- `nat` — natural-language string  
- `str` — exact string  
- `int` — integer  
- `float` — floating-point number  
- `bool` — boolean  

---

### 7.3 `/OUT`

Describes the human-facing output intent.

#### Syntax

```
/OUT description text...
```

- Multi-line allowed
- If omitted, output is unconstrained

---

## 8. Variable Interpolation

Let `FROM = {v1, ..., vn}`.

A variable is **embedded** if `@var` appears in:

- Instruction text  
- Any `/AS` payload  

Execution behavior:

- Embedded variables are replaced in-place before sending to model.
- Non-embedded `/FROM` variables are appended under an automatically generated **Inputs** section.

Referencing a variable not permitted by `/FROM` is a parse-time error.

---

## 9. Model Response Contract

Each step must return valid JSON.

### Required Keys

```json
{
  "error": 0,
  "out": "..."
}
```

If at least one `/DEF` is present:

```json
{
  "error": 0,
  "out": "...",
  "vars": {
    "x": 55
  }
}
```

Rules:

- `error` ∈ {0,1}
- `out` must exist
- All `/DEF` variables must appear in `vars`
- Missing keys → runtime error

---

## 10. Type Validation Rules

Strict JSON validation.

### `int`
- JSON number
- No fractional part
- `12.0` invalid
- Strings invalid

### `float`
- JSON number
- Integers allowed

### `bool`
- JSON `true` or `false`

### `nat`
- JSON string

### `str`
- JSON string

No implicit conversions.

---

## 11. Error Semantics

### Parse-Time Errors

- Duplicate `/TYPE`
- Duplicate `/AS`
- Invalid variable name
- Referencing variable not allowed by `/FROM`
- `/FROM` referencing undefined variable
- Malformed `/IN`
- Unknown directive

Execution does not begin.

---

### Runtime Errors

A step fails if:

- Invalid JSON
- Required keys missing
- `error = 1`
- `/DEF` variable missing
- Type validation fails
- Null/missing values

On runtime error:

- Execution stops immediately  
- No variables from that step are committed  
- Partial outputs may be logged but not persisted  

---

## 12. Variable Lifetime

- Variables persist across steps
- Later `/DEF` may overwrite earlier variables
- Only previously defined variables may be referenced
- No optional types in v0.2

---

## 13. Execution Model

For each step:

1. Validate syntax  
2. Resolve `/FROM`  
3. Interpolate embedded variables  
4. Construct model prompt including:
   - Instruction text  
   - Additional inputs  
   - `/DEF` requirements  
   - `/OUT` guidance  
   - JSON output schema requirement  
5. Send to selected model  
6. Validate JSON  
7. Validate types  
8. If `error = 0`, commit variables  
9. Otherwise stop execution  

---

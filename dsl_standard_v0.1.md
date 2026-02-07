Last updated 2026-02-06

## 1. Scope

This standard defines a lightweight, natural-language–first DSL for expressing **multi-step tasks** with:
- sequential control flow
- explicit data dependencies
- variable binding
- human-readable output intent
    
The system is designed to be:
- general-purpose
- readable without tooling
- deterministic to parse
- tolerant of natural language
It does **not** define model choice, execution engines, or UI.

## 2. Core Concepts
### Step
A **step** is a unit of execution consisting of:
- natural language instructions
- optional directives that constrain inputs and outputs

### Variable
A **variable** is a named value produced by a step and consumable by later steps.
- All variables are **text** in v0.1.
- Variables are referenced using a configurable sigil (default: `@`).
- Variables exist only in the execution environment, not in raw text.

## 3. Step Structure

### 3.1 Step Boundaries
- The first step is **implicit** and begins at the start of the document.
- A new step begins at a line starting with: `/THEN`

## 4. Directives
Directives are optional, line-based instructions that modify step execution.

### 4.1 `/FROM`
Declares the inputs available to the step.

**Syntax**
`/FROM <payload> /FROM(<payload>)`

**Payload**
- Natural language: may be quoted or unquoted if singular, quoted in part of a list
- Variable references (e.g. `@toc`)
- A comma-separated list of the above

**Semantics**
- If present, the step may access only the specified inputs.
- If absent, default input is the entire current environment.

---
### 4.2 `/OUT`
Describes the intended output of the step.

**Syntax**
`/OUT <payload> /OUT(<payload>)`

**Payload**
- Natural language description: quoted or unquoted if singular, quoted if in a list
- May be a comma-separated list of the above

**Semantics**
- If singular, the payload describes the intended output of the response
- a list of payload elements describe intended contents of variables

---
### 4.3 `/AS`
Binds the step output to one or more variables.

**Syntax**
```
/AS var
/AS var1, var2 
/AS(var1, var2)
```

**Semantics**
- If one variable is listed:
    - The step output is assigned to that variable.
- If multiple variables are listed:
    - The step is expected to produce structured output containing values for each variable.

---
## 5. `/OUT` + `/AS` Interaction
Let:
- `k` = number of variables in `/AS`
- `m` = number of descriptions parsed from `/OUT`
### Description Mapping Rules
- If `k = 0`: `/OUT` describes the overall output only.
- If `k = 1`: `/OUT` describes that variable.
- If `k > 1`:
    - If `m = k`: descriptions map positionally.
    - If `m != k`: raise error.


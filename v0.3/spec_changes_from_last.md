everything form [[Chat DSL V0.2 Specs]].

### Models

We will refer to a "Main" and "Cheap" LLM model. These can be set by the implementation.

### Definitions

**Timeline**: To support the ability to edit history, we'll refer to a single chain of messages and responses as a timeline.

**Chat History**: All user messages and all model replies (the content of the `out` key in the returned JSON).

### Built in Variables

Predefined variables

`@ALL`: This will contain all chat history from the current timeline, and all variables from the current timeline.

`@CHAT`: This will contain all chat history from the current timeline.

### 4.1.1 `/IN`: Scoped Natural-Language Inputs (Extension to `/FROM`)

The `/IN` modifier applies only within a `/FROM` directive and is used to **scope a natural-language (`nat`) description to a specific variable**.

It allows a step to request information matching a description, but restrict the search space to a particular variable rather than the default scope.

---
#### Syntax

Within a `/FROM` payload:
```
/FROM element1, element2, ..., description text /IN @varname, ...
```

Where:
- `description text` is a natural-language descriptor (not a variable reference).
- `/IN @varname` must:
    1. Appear immediately after a non-empty natural-language description.
    2. Be followed by exactly one sigil-prefixed variable name.
- The `/IN` modifier binds only to the immediately preceding description.
- The scoped variable must already exist.

---
#### Semantics

Each comma-separated element in `/FROM` is interpreted independently:

1. **Variable reference**
    ```
    @var
    ```
    Grants full access to the variable as defined in v0.2.

2. **Unscoped natural-language description**
    ```
    description text
    ```
    Interpreted as a `nat` description scoped to `@ALL`.

3. **Scoped natural-language description**
    ```
    description text /IN @var
    ```
    Interpreted as a `nat` description scoped exclusively to `@var`.

---
#### Parse-Time Errors

A parse-time error occurs if:
- `/IN` appears without a preceding description.
- `/IN` is not followed by exactly one variable.
- The scoped variable is undefined.
- `/IN` is applied to a variable reference.




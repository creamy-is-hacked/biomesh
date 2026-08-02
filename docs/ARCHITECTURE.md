# Architecture

## M0 – Repository Bootstrap implementation

The current codebase contains a minimal `biomesh` Python package and a
typed command-line entry point. The command-line interface provides package
help and version discovery only; it has no simulation behavior.

Dependency direction is intentionally simple:

```text
CLI entry point -> biomesh package metadata
tests           -> public package/module command
```

Documentation and parameter provenance contracts are separate from runtime
code. CI installs the package and runs linting, type checking, and tests.

## Planned components

The following P1 – Phase 1 – Core Model components are planned but not implemented: parameter
configuration, solute fields, cell geometry, mechanics, metabolism,
simulation orchestration, and scientific outputs. They must keep a directed
dependency structure and avoid coupling presentation or output layers back
into scientific calculations.

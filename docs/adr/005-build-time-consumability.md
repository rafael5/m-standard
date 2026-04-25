# ADR-005 — Designed to be code-generated against

**Status:** accepted (v0.1)
**Spec reference:** `docs/spec.md` §3 AD-05

## Context

`m-standard`'s primary consumer is `tree-sitter-m`, which generates
grammar fragments (command-keyword tables, abbreviation maps,
intrinsic-name lists, operator precedence tables, pattern codes)
from the integrated layer at *its own* build time. Other downstream
projects — `vista-meta`'s analyzers, AI agents, formatters and
linters — sit in the same position: they read m-standard's outputs
mechanically, not by hand.

That makes the integrated layer a **machine-readable interface**,
not just a published reference document. Interfaces have evolution
contracts. Without one, every refactor of m-standard's outputs
ripples into every downstream build.

## Decision

The integrated outputs have stable, versioned schemas:

- Every JSON file carries `"schema_version": "1"`. The version is
  pinned for v1.0 of `m-standard` itself.
- TSV column ordering is locked. Re-runs of the pipeline produce
  TSVs with columns in a fixed order; new columns are appended
  rather than inserted, and renames bump the schema version.
- JSON output is gated by JSON Schemas in `schemas/`, validated
  by the emitter and re-validated by the validation harness in CI
  (spec §7.4 gate #4).
- TSV column order is implicitly gated by the round-trip
  determinism gate (spec §7.4 gate #6): if the reconciler stops
  producing the committed TSV byte-for-byte, CI fails.

Schema evolution is deliberate:

- A **breaking change** (column removed, renamed, retyped; required
  field added; enum value removed) bumps `schema_version` and is
  announced in `CHANGELOG.md`.
- A **non-breaking addition** (new optional column / field, new
  enum value at the end) is appended without a version bump.

## Consequences

- **Downstream builds are stable across non-breaking m-standard
  releases.** A consumer that reads `commands.json` keeps working
  when the next m-standard release adds a new optional field.
- **Breaking changes are visible.** CHANGELOG.md announcements are
  the contract; downstream consumers can pin to a specific
  `schema_version` and gate their own build on it.
- **The validation harness is the enforcement mechanism.** No
  schema discipline is needed in code review beyond "did CI pass?"
  — the round-trip + schema-validation gates catch drift
  automatically.
- **Code generation lives downstream, not here.** `m-standard`
  itself does not vendor or ship grammar fragments. It ships the
  citable data; consumers do the codegen at their build time.

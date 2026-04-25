# ADR-004 — Dual output format: TSV flat facts + JSON structured detail

**Status:** accepted (v0.1)
**Spec reference:** `docs/spec.md` §3 AD-04

## Context

The integrated layer needs to be useful to two different kinds of
consumer:

- **Ad-hoc analysts** who want to query the data in `duckdb`,
  `pandas`, `awk`, or shell — joining commands against intrinsic
  functions, counting Z-extensions, computing coverage against a
  body of M code, etc. These consumers want flat rectangular tables.
- **Code generators** like `tree-sitter-m`, which read enumerations
  (command-keyword tables, abbreviation maps, intrinsic-name lists,
  pattern codes) at *their own* build time and emit grammar
  fragments. These consumers want structured records with typed
  fields, predictable nesting, and a stable schema they can pin.

Picking only one format would either force code generators to parse
TSV (re-deriving types every build) or force analysts to flatten
JSON in their queries.

## Decision

Each concept family is published as **both** a TSV and a JSON file
under `integrated/`, kept structurally consistent by a single
emitter:

- `integrated/<concept>.tsv` — one row per entry, columns for flat
  facts. The primary queryable index. Rows are sorted on the
  per-concept primary key for stable diffs.
- `integrated/<concept>.json` — one entry object per record, with
  typed fields (`true`/`false` strings become JSON booleans, empty
  `conflict_id` becomes `null`) plus space for nested structures
  (argument grammars, parameter lists, error tables) that don't
  fit a flat row.

The two are kept consistent by `m_standard.tools.emit_json` — the
*only* place TSV-to-JSON conversion happens. CI gates the pair with
the `tsv-json-consistency` validation gate (spec §7.4 #5): every
TSV row has a corresponding JSON entry, every JSON entry has a
corresponding TSV row, and common fields agree.

## Consequences

- **No redundancy of truth.** The TSV is the canonical store.
  JSON is generated from it; manual edits to JSON are caught by the
  consistency gate at next CI run.
- **Code generators get a stable surface.** JSON files carry
  `schema_version: "1"` and validate against
  `schemas/<concept>.schema.json` — see ADR-005 for the schema
  evolution policy.
- **Analysts get rectangular tables.** TSV columns are locked in
  order; downstream tooling can rely on `cut -f3` style access.
- **Future enrichment has a home.** When the project starts parsing
  argument grammars (rather than recording verbatim format strings),
  the structured forms land in JSON's nested fields without
  changing the TSV columns.

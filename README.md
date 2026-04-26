# m-standard

An integrated, citable, machine-readable reference for the M (MUMPS)
programming language. Reconciles four primary sources into a unified
data layer that downstream tools (parsers, linters, AI agents,
analyzers) consume directly.

> **Status:** v1.0 tagged for the AnnoStd + YottaDB scope; v0.2
> in progress for the IRIS + SAC additions. End-to-end pipeline
> green; all 9 validation gates passing on every CI run.

## Sources

Four primary sources, all held as offline local replicas under
`sources/` — the pipeline reads only from these replicas, never the
live network at run time.

| Source | What it is | Authoritative for |
| --- | --- | --- |
| **AnnoStd** ([`sources/anno/`](sources/anno/)) | The Annotated M Standard (X11.1-1995 / ISO 11756:1999), crawled mirror | "Is X part of the ANSI standard?" |
| **YottaDB** ([`sources/ydb/`](sources/ydb/)) | Full clone of [`gitlab.com/YottaDB/DB/YDBDoc`](https://gitlab.com/YottaDB/DB/YDBDoc) | Current YDB engine behaviour + YDB extensions |
| **InterSystems IRIS** ([`sources/iris/`](sources/iris/)) | Bounded crawl of `docs.intersystems.com/irislatest` | Current IRIS engine behaviour + IRIS extensions |
| **VA SAC / XINDEX** ([`sources/sac/`](sources/sac/)) | The 17 XINDX routines from `WorldVistA/VistA-M` Toolkit | What the VA M Programming Standards Committee permits in VistA code |

The full design is in [`docs/spec.md`](docs/spec.md). ADRs in
[`docs/adr/`](docs/adr/).

## Pipeline

```
sources/   →  per-source/   →  integrated/   →  emit/  →  validate
(replicas)   (raw TSVs)        (reconciled)    (JSON +    (9 gates)
                                                grammar +
                                                pragmatic +
                                                SAC +
                                                operational)
```

Byte-deterministic end-to-end. Re-running `make all` produces the
committed integrated layer exactly.

## Published outputs

### Per-concept reconciled data

For each of the seven concept families (commands, intrinsic
functions, intrinsic special variables, operators, pattern codes,
errors, environment), `integrated/<concept>.tsv` and
`integrated/<concept>.json` carry every entry from any source with
provenance flags (`in_anno` / `in_ydb` / `in_iris`) and cross-source
section references. Schemas pinned at `schema_version="1"` per
[ADR-005](docs/adr/005-build-time-consumability.md).

[`integrated/conflicts.tsv`](integrated/conflicts.tsv) records every
non-trivial reconciliation across sources.

### Three layered standards

The data resolves three different questions about M:

| Standard | Question | Output | Count |
| --- | --- | --- | --- |
| **Pragmatic** | What runs on both engines? | [`integrated/pragmatic-m-standard.{tsv,json}`](integrated/pragmatic-m-standard.tsv) | **81** |
| **VA SAC** | What does the VA permit? | [`mappings/va-sac.tsv`](mappings/va-sac.tsv) + [`integrated/va-sac-rules.tsv`](integrated/va-sac-rules.tsv) | 65 rules / 171 per-name flags |
| **Operational** | What can a VistA developer use? | [`integrated/operational-m-standard.{tsv,json}`](integrated/operational-m-standard.tsv) | **58** |

The operational standard is the intersection (pragmatic-core ∩
SAC-clean) — what runs unmodified on both YDB and IRIS AND passes
XINDEX SAC validation. Full rationale in
[`docs/pragmatic-m-standard.md`](docs/pragmatic-m-standard.md) and
[`docs/va-sac-and-pragmatic-standard.md`](docs/va-sac-and-pragmatic-standard.md).

### Grammar surface

[`integrated/grammar-surface.json`](integrated/grammar-surface.json)
is the **single-file bundle** purpose-built for grammar generators.
Contains every command / function / ISV / operator / pattern code
from any source, with abbreviation prefix-form expansion already
done (~954 keyword forms total) and `standard_status` per token.

This is what [`m-parser`](../m-parser/) (the tree-sitter grammar
project, sibling repo) consumes at build time. See
[`docs/m-standards-guide.md`](docs/m-standards-guide.md) for the
human-readable reference.

### Cross-vendor mappings

[`mappings/`](mappings/) holds hand-curated and auto-derived mappings
between vendor namespaces:

- `ydb-ansi-errors.tsv` — YDB mnemonics ↔ ANSI Mn codes
- `iris-ansi-errors.tsv` — IRIS `<NAMES>` ↔ ANSI Mn codes
- `iris-ydb-errors.tsv` — IRIS ↔ YDB cross-vendor pairs
- `va-sac.tsv` — auto-derived per-name overlay from XINDEX rules

### M-source linter

[`m_standard.tools.lint_m`](src/m_standard/tools/lint_m.py) applies
the subset of XINDEX SAC rules that need usage-pattern detection
(rather than per-name lookup): trailing whitespace, line >245
bytes, exclusive Kill, READ without timeout, lowercase commands,
LOCK without timeout, etc. (8 rules in v0.2). Run on M source files;
exit code is non-zero if any F/S findings exist (CI-gate-friendly).

```bash
.venv/bin/python -m m_standard.tools.lint_m routine.m
```

## Downstream consumers

- **[`m-parser`](../m-parser/)** ([spec](../m-parser/docs/spec.md)) —
  tree-sitter grammar for M, generated mechanically from
  `integrated/grammar-surface.json`. Single coupling point with
  m-standard, pinned to a specific `schema_version`. Specification
  phase as of writing; implementation is a separate project.
- **`tree-sitter-m-lint`** (planned sibling of m-parser) — consumes
  m-parser's AST plus m-standard's tier classifications
  (operational / pragmatic / SAC) to enforce developer-chosen
  profiles.
- **[`vista-meta`](../vista-meta/)** — VEHU classification sandbox;
  joins m-standard's per-concept TSVs against VistA's code-model TSVs.
- **AI agents and other M tooling** — the integrated TSV+JSON pair
  is prompt-pack target. Any agent reasoning about M code can be
  loaded with these as ground truth — no hallucination about whether
  `$ZSEARCH` is standard, no guessing at command abbreviations.

## Workflow

```bash
make install         # create .venv, install deps, install pre-commit hooks
make sources         # build all four offline replicas
make extract         # per-source TSVs from the replicas
make reconcile       # integrated TSVs + conflicts.tsv
make emit            # JSON + grammar-surface + pragmatic + SAC + operational
make validate        # 9 CI gates (manifests, provenance, schemas, round-trip, ...)
make all             # everything end-to-end
make serve-anno      # browse the AnnoStd mirror at http://localhost:8765
make check           # lint + mypy + cov
```

Per-source target subset (when you only need to refresh one):

```bash
make sources-anno    # re-crawl AnnoStd
make sources-ydb     # re-clone YottaDB docs
make sources-iris    # re-crawl IRIS docs subset
make sources-sac     # re-fetch XINDX routines
```

Per-emit target subset:

```bash
make emit-json          # per-concept JSON files
make emit-grammar       # grammar-surface.json + multi-vendor-extensions.tsv
make emit-pragmatic     # pragmatic-m-standard.{tsv,json}
make emit-sac           # va-sac-compliance.{tsv,json}
make emit-operational   # operational-m-standard.{tsv,json}
```

## Repository structure

```
m-standard/
├── sources/        # 4 offline replicas (anno + ydb + iris + sac)
├── per-source/     # raw extracted TSVs per source
├── integrated/     # reconciled TSVs + JSON + the three standards
├── mappings/       # cross-vendor mappings + SAC overlay
├── schemas/        # JSON Schemas (one per output, schema_version="1")
├── src/m_standard/tools/   # extractors + reconciler + emitters + linter + validator
├── tests/          # pytest tests (164 in v0.2)
├── docs/           # spec.md + ADRs + build-log + standards guides
├── tools/          # bash helpers (clone-ydb.sh, clone-sac.sh)
└── Makefile        # the pipeline entry points
```

## Versioning and schema contract

- **Project version** in [`CHANGELOG.md`](CHANGELOG.md) — semver,
  bumped per release.
- **Schema version** pinned to `"1"` in every published JSON file.
  Per [ADR-005](docs/adr/005-build-time-consumability.md), additive
  schema changes don't bump the version; breaking changes bump and
  announce in the changelog.

Downstream consumers (m-parser, lint tools, vista-meta, AI agents)
pin against a specific `schema_version` rather than the project
version. Additive m-standard updates flow through; breaking ones
require deliberate adoption.

## License

AGPL-3.0 — see [LICENSE](LICENSE). Source materials redistributed
under `sources/` are governed by their own licenses (GFDL-1.3 for
YottaDB docs, public-domain for VA M routines, AnnoStd and IRIS
docs gitignored pending licence verification); see
[`sources/README.md`](sources/README.md).

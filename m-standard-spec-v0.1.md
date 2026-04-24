# m-standard — Specification v0.1

**Status:** draft for review
**License of this document:** AGPL-3.0 (matches the artifact it specifies)
**Sources reconciled:** Annotated M Standard (X11.1-1995, hosted at
71.174.62.16/Demo/AnnoStd), YottaDB Programmer's Guide (current),
GT.M Programmer's Guide (current)
**Primary downstream consumer:** `tree-sitter-m` grammar; secondary
consumers include `vista-meta`, AI agents, and any other M tooling
project that benefits from a citable, machine-readable standard.

---

## Table of contents

* [1. Project identity](#1-project-identity)
* [2. Scope and non-goals](#2-scope-and-non-goals)
* [3. Architectural decisions](#3-architectural-decisions)
* [4. Sources and their treatment](#4-sources-and-their-treatment)
* [5. The integrated standard — concept coverage](#5-the-integrated-standard--concept-coverage)
* [6. Output specification](#6-output-specification)
* [7. Reconciliation and validation methodology](#7-reconciliation-and-validation-methodology)
* [8. Repository layout](#8-repository-layout)
* [9. Toolchain and dependencies](#9-toolchain-and-dependencies)
* [10. Downstream consumption](#10-downstream-consumption)
* [11. Milestones and roadmap](#11-milestones-and-roadmap)
* [12. Risks and open questions](#12-risks-and-open-questions)
* [13. Success criteria for v1.0](#13-success-criteria-for-v10)

---

## 1. Project identity

**Name.** `m-standard`.

**Purpose.** A single, integrated, citable, machine-readable
reference standard for the M (MUMPS) programming language,
synthesized by extracting and reconciling three primary sources:
the Annotated M Standard (AnnoStd), the YottaDB Programmer's
Guide, and the GT.M Programmer's Guide. Output is two coordinated
artifacts: a human-readable narrative (M-Standards-Guide) and a
machine-readable data layer (TSV + JSON) that downstream tools
consume directly.

**License.** AGPL-3.0, matching YottaDB and the rest of the
project family. Source materials redistributed in `sources/` are
governed by their own licenses (see §4.4 on redistribution).

**Why this exists.** No single canonical, machine-readable M
standard is available today. AnnoStd is normative for the 1995
ANSI standard but is hosted on a single ageing server, formatted
as static HTML, and contains no machine-extractable structure.
YottaDB and GT.M Programmer's Guides are exhaustive and current
but mix standard behavior with vendor extensions, and present
their content in narrative PDF/HTML that resists automated
consumption. A grammar built against any one of these is
brittle; a grammar built against all three, with disagreements
explicitly reconciled, is defensible.

**Relationship to the project family.** `m-standard` is an
upstream component. `tree-sitter-m` consumes its machine-readable
outputs at build time to generate enumeration grammar fragments
(commands and abbreviations, intrinsic functions, operators,
pattern codes). `vista-meta` consumes its outputs for analyzer
metadata. Other M tooling projects can consume or cite it
without inheriting any project-specific assumptions.

---

## 2. Scope and non-goals

**In scope for v1.0:**

* Core M language as defined by ANSI X11.1-1995 / ISO 11756:1999 —
  lexical structure, syntax, semantics, all standard commands,
  intrinsic functions, intrinsic special variables, operators,
  patterns, indirection
* The M execution environment: process model, namespace/job
  structure, locks, transactions, error handling (`$ETRAP`,
  `$ECODE`, `$ESTACK`, `$STACK`), device I/O parameters
* Standard-library routines that are part of M proper: `%DT`,
  `%DTC`, `%ZIS` family for I/O, etc.
* YottaDB-specific extensions, clearly marked as such (separate
  rows / records, with `extension_of=ydb` flag)
* GT.M-specific extensions, clearly marked as such

**Deferred to v0.2 or later:**

* MWAPI (ANSI X11.2, the M Window API — largely unused in modern
  M, deserves its own integration project if revived)
* MSQL (SQL extensions to M — vendor-specific, not standardized)
* InterSystems Caché / IRIS extensions (`&sql(...)`,
  `##class(...)`, `$ZF` family) — would require a fourth source
* Pre-ANSI dialects (DSM-11, MUMPS-11) — historical, not relevant
  to live codebases
* The VA's SAC (Standards and Conventions) — this is a
  coding-style standard, not a language standard; lives in
  vista-meta if anywhere

**Non-goals:**

* A tutorial or teaching text. M-Standards-Guide is a reference,
  not a textbook.
* Implementation-specific configuration (`yottadb.conf`,
  `gtm.conf`, etc.) beyond what affects observable language
  behavior.
* Performance tuning, optimization advice, or operational
  guidance.
* Replacing AnnoStd, YDB, or GT.M's own documentation. This is a
  *reconciliation layer* over them, not a replacement for them.

---

## 3. Architectural decisions

Five decisions drive the rest of the spec. Listed once here so
downstream sections can reference them by number.

### AD-01: Three-source hierarchy with explicit precedence

When the three sources disagree, the resolution follows a fixed
hierarchy:

* **AnnoStd** is normative for what counts as standard ANSI M. If
  AnnoStd does not describe a behavior, that behavior is not part
  of the standard, regardless of what YDB or GT.M say.
* **YottaDB Programmer's Guide** is authoritative for current
  real-world implementation behavior of the leading open-source
  M engine, and is the source of truth for YottaDB-specific
  extensions.
* **GT.M Programmer's Guide** is the cross-check on YottaDB
  (since YDB descends from GT.M) and is the authority for the
  small set of GT.M-isms that did not carry forward into YDB.

Disagreements are not silently resolved — every conflict is
recorded in `conflicts.tsv` with the resolution and a reference
to this AD.

### AD-02: Separate normative text from annotations

AnnoStd is the 1995 ANSI standard *with annotations*. The
annotations are commentary by the M committee — examples,
historical context, intent — and are *not* normative. The
extraction pipeline must distinguish the two: only the normative
standard text drives standard claims; annotations are preserved
as supplementary context (`anno_commentary` column on relevant
TSV rows) but do not establish standard behavior. Conflating the
two is the most common error in informal citations of AnnoStd
and is explicitly avoided here.

### AD-03: Per-source preservation alongside integrated output

Raw per-source TSVs are preserved in `per-source/anno/`,
`per-source/ydb/`, `per-source/gtm/` as first-class artifacts,
not intermediate scratch. The integrated layer in `integrated/`
is derived from them and carries provenance columns (`in_anno`,
`in_ydb`, `in_gtm`, plus per-source section references). This
guarantees that any claim in the integrated layer can be traced
to its source rows, and that re-running the reconciler on
updated sources is reproducible. It also lets a downstream
consumer query a single source if they prefer (e.g., "what does
GT.M alone say about `$ZSEARCH`?").

### AD-04: Dual output format — TSV flat facts + JSON structured detail

Each concept (commands, intrinsic functions, etc.) is published
as both a TSV (one row per entry, columns for flat facts) and a
JSON file (one object per entry, with nested structure for
things that don't fit a flat row — argument grammar, error
condition tables, parameter lists). The TSV is the primary
queryable index, joinable in `duckdb`, `pandas`, `awk`, and
shell. The JSON is the structured-detail surface, suitable for
code generation in `tree-sitter-m`. The two are kept consistent:
every TSV row has a corresponding JSON object identified by the
same primary key.

### AD-05: Designed to be code-generated against

The integrated outputs have stable, versioned schemas
(`schema_version: "1"` in every JSON file; column ordering
locked in TSVs; both gated by JSON Schema and column-checksum
in CI). Consumers like `tree-sitter-m` build code from these
outputs at *their* build time. This means schema evolution is
deliberate: a breaking change to a schema bumps the version and
is announced in `CHANGELOG.md`. Non-breaking additions are
appended without a version bump.

---

## 4. Sources and their treatment

### 4.1 AnnoStd — the Annotated M Standard

* **What it is.** The 1995 ANSI X11.1 standard with annotations
  by the M Development Committee. ISO 11756:1999 is substantively
  the same document with international packaging.
* **Where it lives.** Currently at `http://71.174.62.16/Demo/AnnoStd`
  as a static HTML tree.
* **Version pinned.** v1.0 of `m-standard` pins to a single
  snapshot taken at project start; the snapshot is identified in
  `sources/anno/manifest.tsv` by URL, fetch date, and sha256.
* **Treatment.** Crawled once, mirrored locally to `sources/anno/`
  (subject to §4.4). Per AD-02, normative text and annotations
  are extracted to separate columns in
  `per-source/anno/*.tsv`. AnnoStd is the authority for "is X
  part of the standard."

### 4.2 YottaDB Programmer's Guide

* **What it is.** The official documentation for YottaDB, the
  current open-source M engine maintained by YottaDB LLC.
  Comprehensive and current.
* **Where it lives.** At `https://docs.yottadb.com/`.
* **Version pinned.** v1.0 pins to the YottaDB release current
  at project start (recorded in `sources/ydb/manifest.tsv`).
* **Treatment.** Documents are fetched (HTML preferred over PDF
  for extractability). Per AD-01, YDB is authoritative for
  current implementation and for YDB-specific extensions. YDB
  extensions are flagged `extension_of=ydb` in the integrated
  layer.

### 4.3 GT.M Programmer's Guide

* **What it is.** Documentation for GT.M, the predecessor to
  YottaDB, historically maintained by Fidelity National
  Information Services. Largely overlaps YDB but differs in
  some detail and contains a small number of GT.M-isms that
  didn't carry forward.
* **Where it lives.** At `https://fis-gtm.com/products/`,
  current open-source releases.
* **Treatment.** Fetched and mirrored. Used per AD-01 as
  cross-check on YDB and authority for GT.M-only behaviors.

### 4.4 Redistribution and snapshot policy

Each source has its own license. Before mirroring any of them
into `sources/`, the project verifies redistribution rights:

* **If redistribution is permitted:** the snapshot is committed
  to `sources/<src>/` directly, with `manifest.tsv` recording
  URL → local path → sha256 → fetch date.
* **If redistribution is not permitted:** `sources/<src>/`
  contains only `manifest.tsv` plus an extraction script
  (`fetch.sh`) that re-acquires the source from its origin.
  Local users can run `make sources` to populate; the binary
  content stays out of git.

The project starts with the redistribution-allowed assumption
for AnnoStd (the M Technology Association has historically
encouraged mirroring) and the redistribution-not-allowed
assumption for YDB and GT.M (commercial documentation, even when
free to read). This is verified in Phase A0 before any commit.

---

## 5. The integrated standard — concept coverage

The integrated layer covers seven concept families. Each is a
TSV+JSON pair under `integrated/`.

### 5.1 Commands

The ~25 standard commands plus all vendor extensions, with:

* Canonical name (`SET`, `WRITE`, `XECUTE`)
* All valid abbreviations (`S`, `W`, `X`)
* Whether a postconditional is allowed
* Argument count (min, max; or `unbounded` for variable)
* Argument grammar (in JSON, expressed as an EBNF-like fragment)
* Standard status (`ansi`, `ydb-extension`, `gtm-extension`,
  `multi-vendor-extension`)
* Per-source section references (`anno_section`, `ydb_section`,
  `gtm_section`)
* Notes on per-source divergence (free text)

### 5.2 Intrinsic functions

The ~22 ANSI intrinsic functions plus Z-prefix extensions:

* Canonical name (`$EXTRACT`)
* Abbreviations (`$E`)
* Argument signature (positional, with names and types)
* Return type
* Standard status
* Per-source section references
* Side-effect classification (pure, reads-state, modifies-state)

### 5.3 Intrinsic special variables

The ~21 ANSI special variables plus Z-prefix extensions:

* Canonical name (`$HOROLOG`)
* Abbreviations (`$H`)
* Read-only or read-write
* Type and example values
* Standard status
* Per-source section references

### 5.4 Operators

All M operators with:

* Symbol (`+`, `_`, `[`, `]]`, `?`)
* Arity (unary, binary)
* Class (arithmetic, string, comparison, logical, pattern)
* Associativity (left, right — though M is largely strict left)
* Notes on M's no-precedence rule
* Per-source section references

### 5.5 Pattern codes

All pattern-match codes (`A`, `C`, `E`, `L`, `N`, `P`, `U`, plus
vendor extensions) with:

* Code character
* Match definition (e.g., "alphabetic characters")
* Whether case-sensitive
* Standard status
* Per-source section references

### 5.6 Errors and error processing

The standard error condition codes (`M1`–`M75` and friends),
plus `$ECODE` / `$ETRAP` / `$ESTACK` / `$STACK` semantics:

* Error code
* Description
* Standard / vendor classification
* Trap behavior
* Per-source section references

### 5.7 Environment

The M execution environment: process model, lock semantics,
transaction semantics (`TSTART` / `TCOMMIT` / `TROLLBACK`,
isolation behavior), device I/O parameters (the `OPEN` /
`USE` / `CLOSE` parameter sets, organized by device class),
namespace and routine resolution rules.

This is the most heterogeneous concept family — environment
behavior is where vendors diverge most. Per-source preservation
is most important here.

---

## 6. Output specification

### 6.1 Per-source TSVs

`per-source/<src>/<concept>.tsv`. Format: tab-separated, UTF-8,
header row, RFC-4180-ish quoting. Every row carries a
`source_section` column citing the source location (e.g.,
`§7.1.5.4` for AnnoStd, `Chapter 5 — Commands` for YDB). These
are deliberately raw — minimal interpretation, maximum fidelity
to the source's own organization.

### 6.2 Integrated TSVs

`integrated/<concept>.tsv`. Format identical to per-source.
Additional columns:

| Column | Type | Description |
| --- | --- | --- |
| `in_anno` | bool | Present in AnnoStd |
| `in_ydb` | bool | Present in YDB guide |
| `in_gtm` | bool | Present in GT.M guide |
| `anno_section` | string | Reference if `in_anno` |
| `ydb_section` | string | Reference if `in_ydb` |
| `gtm_section` | string | Reference if `in_gtm` |
| `standard_status` | enum | `ansi` / `ydb-extension` / `gtm-extension` / `multi-vendor` |
| `conflict_id` | string | FK to `conflicts.tsv` if reconciliation was non-trivial |

### 6.3 Integrated JSON per-entry

`integrated/<concept>.json`. One JSON object per entry, keyed by
canonical name. Carries the flat fields from the TSV plus
nested structure that doesn't fit a row: argument grammars,
parameter lists, error tables, examples. Validated against
`schemas/<concept>.schema.json` in CI.

### 6.4 Conflicts table

`integrated/conflicts.tsv`. One row per non-trivial reconciliation:

| Column | Type | Description |
| --- | --- | --- |
| `conflict_id` | string | Stable ID (`CONF-NNN`) |
| `concept` | string | Which concept (commands / intrinsics / etc.) |
| `entry` | string | Which entry (e.g., `$ZSEARCH`) |
| `kind` | enum | `existence` / `definition` / `extension` / `errata` / `annotation-only` |
| `anno_says` | string | What AnnoStd says (or "absent") |
| `ydb_says` | string | What YDB says |
| `gtm_says` | string | What GT.M says |
| `resolution` | string | What the integrated layer chose |
| `resolution_basis` | string | Reference to AD-01 hierarchy or other rationale |

### 6.5 M-Standards-Guide

`docs/m-standards-guide.md` — the human-readable narrative.
Organized by concept family (one chapter per §5 family). Each
section tells the story of what is standard, where the sources
diverge, and why; cites `integrated/<concept>.tsv` for facts and
`conflicts.tsv` for reconciled disagreements. Written in
vista-meta's house style: prose-forward, with tables and lists
where structural.

### 6.6 Sources manifest

`sources/<src>/manifest.tsv`. Columns:

| Column | Type | Description |
| --- | --- | --- |
| `source_url` | string | Origin URL |
| `local_path` | string | Path under `sources/<src>/` if mirrored |
| `sha256` | string | Content hash |
| `fetched_at` | datetime | ISO-8601 fetch timestamp |
| `format` | enum | `html` / `pdf` / `txt` |
| `extraction_target` | string | Which `per-source/<src>/<concept>.tsv` rows it feeds |

---

## 7. Reconciliation and validation methodology

### 7.1 Per-source extraction

Each source has its own extractor (`tools/extract-anno.py`,
`tools/extract-ydb.py`, `tools/extract-gtm.py`). Extractors are
deliberately conservative — they do not interpret, they just
pull structured facts from the source's own organization into
the per-source TSV format. Every extracted row cites its
`source_section`.

### 7.2 Three-way reconciliation

`tools/reconcile.py` consumes the per-source TSVs and produces
the integrated TSVs plus `conflicts.tsv`. The reconciler is
fully deterministic; given the same per-source inputs it
produces byte-identical outputs. Resolution logic follows AD-01
strictly. Any case the reconciler cannot resolve automatically
emits a `conflict_id` with `resolution=PENDING-MANUAL`, which
is a hard CI failure until a human sets the resolution.

### 7.3 JSON emission

`tools/emit-json.py` reads the integrated TSVs and produces the
JSON per-entry files. Validation against `schemas/<concept>.schema.json`
is enforced. The emitter is the only place where TSV-to-JSON
conversion happens, ensuring TSV/JSON consistency is structural,
not aspirational.

### 7.4 Validation gates

`tools/validate.py` runs in CI and enforces:

1. **Manifest integrity.** Every file in `sources/<src>/`
   appears in `manifest.tsv` with a current sha256.
2. **Provenance.** Every row in every `integrated/*.tsv` has
   `in_anno`/`in_ydb`/`in_gtm` flags consistent with the
   per-source TSVs. No integrated row may exist without at
   least one source attesting it.
3. **Conflict resolution.** No row in `conflicts.tsv` has
   `resolution=PENDING-MANUAL`.
4. **Schema validation.** Every JSON file in `integrated/`
   validates against its schema in `schemas/`.
5. **TSV/JSON consistency.** Every TSV row has a corresponding
   JSON object; every JSON object has a corresponding TSV row;
   common fields agree.
6. **Round-trip.** Per-source TSVs + `conflicts.tsv` →
   `reconcile.py` → integrated TSVs are byte-identical to what's
   committed. (Defends against drift between the reconciler and
   manual edits to integrated files.)
7. **Coverage check.** Every entry named in any per-source TSV
   appears in the corresponding integrated TSV.

### 7.5 Continuous integration

GitHub Actions runs `tools/validate.py` on every PR. Passing
validation is required to merge. A nightly job re-runs
extraction against the pinned snapshots to confirm extractor
determinism.

### 7.6 Source updates

When the pinned source version is updated (a new YDB release,
say), the workflow is: bump the manifest, re-run extraction,
re-run reconcile, review the diff in the integrated layer, edit
`conflicts.tsv` if new conflicts surfaced, commit. Source
updates are deliberate, traceable, and version-bumped.

---

## 8. Repository layout

```
m-standard/
├── sources/
│   ├── README.md                  # Acquisition + redistribution status
│   ├── anno/
│   │   ├── manifest.tsv
│   │   └── pages/                 # Mirrored AnnoStd HTML (or fetch.sh if not redistributable)
│   ├── ydb/
│   │   ├── manifest.tsv
│   │   └── (PDF/HTML or fetch.sh)
│   └── gtm/
│       ├── manifest.tsv
│       └── (PDF/HTML or fetch.sh)
├── per-source/
│   ├── anno/
│   │   ├── commands.tsv
│   │   ├── intrinsic-functions.tsv
│   │   ├── intrinsic-special-variables.tsv
│   │   ├── operators.tsv
│   │   ├── pattern-codes.tsv
│   │   ├── errors.tsv
│   │   └── environment.tsv
│   ├── ydb/  (same shape)
│   └── gtm/  (same shape)
├── integrated/
│   ├── commands.tsv
│   ├── commands.json
│   ├── intrinsic-functions.tsv
│   ├── intrinsic-functions.json
│   ├── intrinsic-special-variables.tsv
│   ├── intrinsic-special-variables.json
│   ├── operators.tsv
│   ├── operators.json
│   ├── pattern-codes.tsv
│   ├── pattern-codes.json
│   ├── errors.tsv
│   ├── errors.json
│   ├── environment.tsv
│   ├── environment.json
│   └── conflicts.tsv
├── schemas/
│   ├── command.schema.json
│   ├── intrinsic-function.schema.json
│   ├── intrinsic-special-variable.schema.json
│   ├── operator.schema.json
│   ├── pattern-code.schema.json
│   ├── error.schema.json
│   └── environment-entry.schema.json
├── docs/
│   ├── spec.md                    # This document
│   ├── m-standards-guide.md       # Human-readable narrative reference
│   ├── adr/
│   │   ├── 001-three-source-hierarchy.md
│   │   ├── 002-normative-vs-annotation-separation.md
│   │   ├── 003-per-source-preservation.md
│   │   ├── 004-tsv-plus-json-output.md
│   │   ├── 005-build-time-consumability.md
│   │   └── ...
│   └── build-log.md
├── tools/
│   ├── crawl-anno.py              # AnnoStd crawler
│   ├── extract-anno.py            # AnnoStd HTML → per-source TSVs
│   ├── extract-ydb.py             # YDB guide → per-source TSVs
│   ├── extract-gtm.py             # GT.M guide → per-source TSVs
│   ├── reconcile.py               # per-source → integrated + conflicts
│   ├── emit-json.py               # integrated TSVs → JSON per-entry
│   └── validate.py                # CI validation harness
├── .github/workflows/
│   └── ci.yml
├── CHANGELOG.md                   # Schema versions and source pin updates
├── LICENSE                        # AGPL-3.0
├── README.md
├── pyproject.toml                 # Inherits vista-meta python style
└── Makefile                       # `make sources`, `make extract`, `make reconcile`, `make validate`, `make all`
```

---

## 9. Toolchain and dependencies

* **Python ≥3.11** for all extractors, reconciler, emitter, and
  validator.
* **Stdlib + the minimum** — `requests` for fetching, `lxml` or
  `beautifulsoup4` for HTML parsing, `pdfplumber` for PDF
  extraction, `jsonschema` for validation. All pinned in
  `pyproject.toml`. No optional speed wins (no `orjson`); this
  is a build-time tool and runs in seconds.
* **Make** for orchestration (mirrors vista-meta convention).
* **GitHub Actions** for CI.

No runtime dependencies — `m-standard` ships TSVs and JSON, both
zero-dependency to consume.

---

## 10. Downstream consumption

### 10.1 tree-sitter-m

`tree-sitter-m`'s `tools/build-grammar.js` reads
`integrated/commands.json`, `integrated/intrinsic-functions.json`,
`integrated/intrinsic-special-variables.json`,
`integrated/operators.json`, and `integrated/pattern-codes.json`
at grammar-generate time. From these, it generates the
enumeration fragments of `grammar.js`: the command-keyword
table, the abbreviation map, the intrinsic name lists, the
operator precedence tables. The hand-written parts of the
grammar (line structure, dot blocks, indirection) remain
hand-written. When `m-standard` releases an update,
`tree-sitter-m` regenerates these enumerations with one command.

### 10.2 vista-meta

vista-meta's analyzers gain a new metadata source: the
integrated TSVs are joinable to existing 19 code-model TSVs.
Example: a "commands actually used in VistA vs commands in the
standard" coverage report is a single join.

### 10.3 AI agents and other tooling

The integrated TSV+JSON pair is the prompt-pack target. Any
agent reasoning about M code can be loaded with these as
ground truth — no hallucination about whether `$ZSEARCH` is
standard, no guessing at command abbreviations. Other M tooling
projects (formatters, linters, transpilers) consume the same
artifacts.

---

## 11. Milestones and roadmap

| Milestone | Scope | Exit criterion |
| --- | --- | --- |
| **A0** | Source acquisition & snapshot. Verify redistribution rights. Stand up repo skeleton with AGPL, ADR directory, build-log stub, CI skeleton, Makefile. | All three sources accessible from the repo (mirrored or fetchable). Manifests committed. CI skeleton runs green. |
| **A1** | Per-source extractors for all three sources. Iterate per concept family (commands first, then intrinsics, then the rest). | All seven concepts extracted from all three sources where present. Per-source TSVs committed and reviewed. |
| **A2** | Reconciler. AD-01 hierarchy implemented. `conflicts.tsv` populated. Manual resolution of every `PENDING-MANUAL` conflict. | Reconciler is deterministic; integrated TSVs committed; `conflicts.tsv` has zero `PENDING-MANUAL` rows. |
| **A3** | JSON emitter and schemas. TSV/JSON consistency enforced in CI. | Every concept has a passing JSON file matching its schema. |
| **A4** | M-Standards-Guide narrative. One chapter per concept family. Cites integrated outputs for every claim. | Document reviewed and merged. |
| **A5** | ADRs (one per architectural decision plus any project-specific decisions made during A1–A4). Build log up to date. | ADR set complete. Build log has BL entries for any non-trivial issues encountered. |
| **A6** | Validation harness complete. All seven validation gates from §7.4 enforced in CI. | CI gates all seven checks; PR-per-milestone workflow validated. |
| **v1.0** | Tag and release. | All §13 success criteria met. |

Estimated total: **~5–8 days of focused work for v1.0.**

The largest unknowns are AnnoStd extraction quality (how
machine-extractable the HTML actually is) and conflict volume
(how often the three sources actually disagree on substantive
points). Both will be quantified at A1 exit and may revise the
A2 estimate.

---

## 12. Risks and open questions

**AnnoStd availability.** The host at 71.174.62.16 is a single
point of failure. Mitigation: snapshot once at A0 and pin to
that snapshot for v1.0. Even if the source goes offline mid-project,
work continues from the local mirror. Long-term mitigation: if
redistribution is permitted, the snapshot in the repo *is* the
durable copy.

**AnnoStd extraction quality.** Static HTML from a 1990s-era
site is rarely well-structured. The extractor may need to be
tag-soup-tolerant. Budget extra time at A1 for this; if
extraction yield is poor, fall back to manual transcription of
the affected sections (AnnoStd is not enormous — ~300 pages
equivalent).

**Conflict volume.** The three sources will agree on the bulk
of standard M; conflicts concentrate around (a) Z-extensions
where YDB and GT.M diverge slightly, (b) under-specified ANSI
behavior where YDB and GT.M filled in different defaults, and
(c) errata in AnnoStd. If conflict volume exceeds ~100 rows,
A2 will need additional review time.

**Z-extension namespace overlap.** YDB and GT.M both use the
`$Z*` and `Z*` namespace for extensions; the same name can
mean different things in different vendors. The integrated
layer must record `extension_of` per row and accept that two
rows with the same name but different `extension_of` is a
valid state, not a duplicate.

**Source license redistribution.** YDB and GT.M Programmer's
Guides are commercial documentation, free to read but possibly
not free to mirror. If both are non-redistributable, the
`sources/` tree carries fetch scripts only and local users must
re-acquire — slightly less reproducible but legally defensible.

**Standard versioning.** AnnoStd is the 1995 standard. The M
Development Committee circulated draft revisions post-1995 that
were never formally approved. Some of those drafts' content is
present in YDB/GT.M as "common practice" but is not standard
per AnnoStd. Per AD-01 + AD-02, these go in as
`standard_status=multi-vendor` extensions, not as ANSI standard.

**Pin-stability vs currency.** v1.0 pins to source snapshots.
Future versions update the pins. The trade-off: pin-stability
gives reproducibility for downstream consumers; currency gives
accuracy. The CHANGELOG.md and version bumps are how this is
managed.

---

## 13. Success criteria for v1.0

The following must all be true for v1.0 release:

1. **Source snapshots committed or fetchable.** All three
   sources accessible from the repo with verified manifests
   (URL, sha256, fetch date).
2. **Per-source extraction complete.** All seven concept
   families extracted from each of the three sources where the
   source covers that concept.
3. **Integrated layer complete.** All seven concept families
   reconciled. Every row carries provenance flags and source
   section references.
4. **Conflicts resolved.** `conflicts.tsv` has zero
   `PENDING-MANUAL` rows; every conflict has a resolution
   citing AD-01 hierarchy or other documented rationale.
5. **Schema validation.** Every `integrated/*.json` validates
   against its schema; every TSV/JSON pair is consistent.
6. **CI gates.** All seven validation gates from §7.4 enforced
   on every PR.
7. **M-Standards-Guide reviewed.** Document complete, every
   claim cites the integrated layer, reviewed and merged.
8. **ADR set complete.** AD-01 through AD-05 documented; any
   additional decisions made during build documented as ADRs
   006+.
9. **Build log up to date.** `BL-NNN` entries for non-trivial
   issues encountered, in vista-meta convention.
10. **Reproducibility.** A fresh clone, `make all`, succeeds on
    Linux without network access (if sources are mirrored) or
    with network access (if sources are fetch-only).
11. **License compliance.** AGPL-3.0 stamped in `LICENSE` and
    in every source file's header. Source materials in
    `sources/` carry their original license notices.

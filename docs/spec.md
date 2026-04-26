# m-standard — Specification v0.2

**Status:** draft for review
**License of this document:** AGPL-3.0 (matches the artifact it specifies)
**Sources reconciled:** three primary sources, all held as offline
local replicas under `sources/`:

1. **Annotated M Standard** (X11.1-1995, hosted at
   `71.174.62.16/Demo/AnnoStd`) — crawled and mirrored locally for
   offline browsing. Normative for "is X part of the ANSI standard."
2. **YottaDB documentation corpus** — cloned in full from its GitLab
   source repository. Authoritative for current YottaDB engine
   behaviour and YDB-specific extensions.
3. **InterSystems IRIS documentation** (added v0.2; rationale in
   ADR-006) — crawled subset of `docs.intersystems.com/irislatest`.
   Authoritative for current IRIS engine behaviour and IRIS-specific
   extensions. **IRIS is the operational engine that runs VistA in
   production at the VA**, which is why it's a primary source rather
   than a possible future addition.

The replicas — not the live upstream — are the foundation for all
extraction and analysis.

**Primary downstream consumer:** [`m-parser`](../../m-parser/) (the
tree-sitter-m grammar project, sibling repo) — see §10.1 for the
contract. Secondary consumers include the planned
`tree-sitter-m-lint`, `vista-meta`, AI agents, and any other M
tooling project that benefits from a citable, machine-readable
standard.

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
synthesized by extracting and reconciling two primary sources:
the Annotated M Standard (AnnoStd) and the YottaDB documentation
corpus. Both sources are first captured as offline local replicas
— a crawled mirror of the AnnoStd website, and a full clone of the
YottaDB documentation GitLab repository — and all subsequent
extraction, reconciliation, and analysis runs against those
replicas, not the live upstream. Output is two coordinated
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
The YottaDB documentation corpus is exhaustive and current but
mixes standard behavior with vendor extensions, and its rendered
form resists automated consumption. The GT.M Programmer's Guide,
which would have been a natural cross-check on YottaDB, is no
longer reliably accessible and is therefore out of scope. A
grammar built against either source alone is brittle; a grammar
built against both, with disagreements explicitly reconciled, is
defensible.

**Relationship to the project family.** `m-standard` is an
upstream component. [`m-parser`](../../m-parser/) (the
tree-sitter-m grammar project) consumes
`integrated/grammar-surface.json` at build time to generate
enumeration grammar fragments (commands and abbreviations,
intrinsic functions, operators, pattern codes). `vista-meta`
consumes per-concept TSVs for analyzer metadata. The planned
`tree-sitter-m-lint` will consume both m-parser's AST and
m-standard's tier classifications (operational / pragmatic / SAC).
Other M tooling projects can consume or cite m-standard without
inheriting any project-specific assumptions.

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

**Deferred to v0.2 or later:**

* MWAPI (ANSI X11.2, the M Window API — largely unused in modern
  M, deserves its own integration project if revived)
* MSQL (SQL extensions to M — vendor-specific, not standardized)
* InterSystems Caché / IRIS extensions (`&sql(...)`,
  `##class(...)`, `$ZF` family) — would require an additional source
* GT.M-specific behaviors that diverge from YottaDB — currently
  out of scope because the GT.M Programmer's Guide is no longer
  reliably accessible; revisit if a durable mirror surfaces
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
* Replacing AnnoStd or YottaDB's own documentation. This is a
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
  of the standard, regardless of what either implementation source
  says.
* **YottaDB documentation corpus** is authoritative for current
  real-world implementation behavior of the leading open-source
  M engine, and is the source of truth for YottaDB-specific
  extensions (`standard_status=ydb-extension`).
* **InterSystems IRIS documentation** is authoritative for current
  IRIS engine behavior and IRIS-specific extensions
  (`standard_status=iris-extension`). IRIS and YottaDB are *peers*
  in this hierarchy — neither outranks the other for implementation
  detail. Where the two implementations describe the same ANSI
  behaviour differently, that's a real cross-vendor divergence
  worth surfacing as a conflict.

Disagreements are not silently resolved — every conflict is
recorded in `conflicts.tsv` with the resolution and a reference
to this AD.

**Note on standard_status values.** v0.2 introduces a fifth value
`multi-vendor-ext` for entries present in *both* implementation
sources but not in AnnoStd — i.e. de facto extensions that the M
community has converged on without formal standardisation. The
full enum is now: `ansi`, `ydb-extension`, `iris-extension`,
`multi-vendor-ext`, plus the legacy `ydb-extension`-only label
retained for v1.0 compatibility.

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

Raw per-source TSVs are preserved in `per-source/anno/` and
`per-source/ydb/` as first-class artifacts, not intermediate
scratch. The integrated layer in `integrated/` is derived from
them and carries provenance columns (`in_anno`, `in_ydb`, plus
per-source section references). This guarantees that any claim
in the integrated layer can be traced to its source rows, and
that re-running the reconciler on updated sources is
reproducible. It also lets a downstream consumer query a single
source if they prefer (e.g., "what does the YottaDB documentation
alone say about `$ZSEARCH`?").

Both per-source TSVs are derived from offline local replicas of
their upstreams (AnnoStd as a crawled HTML mirror, YottaDB as a
full clone of its documentation GitLab repository). Extraction
never reaches the live network at run time; the local replica is
the analysis foundation, and the upstream is consulted only when
the snapshot is deliberately refreshed.

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
* **Where it lives upstream.** Currently at
  `http://71.174.62.16/Demo/AnnoStd` as a static HTML tree on a
  single ageing host.
* **How it is captured.** Crawled in full and cloned to a local
  offline replica under `sources/anno/site/`, preserving the
  original directory structure, asset references, and inter-page
  links so the mirror can be opened directly in a browser
  (`file://…/sources/anno/site/index.html`) and navigated as if
  it were the live site. The crawler rewrites only what it must
  to make local browsing work (absolute → relative links within
  the mirror); page bodies are preserved byte-for-byte for
  extraction purposes. A simple `make serve-anno` target also
  serves the mirror over `http://localhost` for users who prefer
  a web server.
* **Version pinned.** v1.0 of `m-standard` pins to a single
  crawl taken at project start; the snapshot is identified in
  `sources/anno/manifest.tsv` by URL, fetch date, and sha256
  per file.
* **Treatment.** All extraction reads the local mirror, never the
  live host. Per AD-02, normative text and annotations are
  extracted to separate columns in `per-source/anno/*.tsv`.
  AnnoStd is the authority for "is X part of the standard."

### 4.2 YottaDB documentation corpus

* **What it is.** The official documentation for YottaDB, the
  current open-source M engine maintained by YottaDB LLC.
  Comprehensive and current. The rendered site at
  `https://docs.yottadb.com/` is generated from a documentation
  source repository hosted on YottaDB's GitLab.
* **How it is captured.** The entire documentation source
  repository is `git clone`d into `sources/ydb/repo/` as a full
  working tree, then the inner `.git/` is stripped before commit
  so the bulk content can be vendored in `m-standard`'s own repo
  as plain files. (Submodules were considered and rejected — they
  would require a separate network fetch on every fresh clone of
  `m-standard`, defeating the "self-contained offline replica"
  goal.) The pinned commit SHA is preserved per-row in
  `sources/ydb/manifest.tsv` so reproducibility holds without the
  embedded `.git/`. Updates re-run `tools/clone-ydb.sh`, which
  clones fresh into a temp directory at the new pin and mirrors
  the working tree onto `sources/ydb/repo/`. Working from the
  source repository — rather than crawling the rendered HTML —
  gives stable, versioned, well-structured input (RST/Markdown
  with predictable headings, anchors, and cross-references) that
  is far more amenable to extraction than scraped HTML. The
  vendored tree is the analysis foundation; the rendered site is
  referenced only for human verification.
* **Version pinned.** v1.0 pins to the commit SHA of the docs
  repository at project start (recorded in
  `sources/ydb/manifest.tsv` alongside the upstream remote URL).
* **Treatment.** Extraction walks the cloned tree directly. Per
  AD-01, the YottaDB documentation is authoritative for current
  implementation and for YDB-specific extensions. YDB extensions
  are flagged `extension_of=ydb` in the integrated layer.

### 4.3 InterSystems IRIS documentation

* **What it is.** The official documentation for InterSystems IRIS
  Data Platform, the current commercial M engine maintained by
  InterSystems Corporation. IRIS descends from Caché, which in turn
  evolved from the original ISM/MSM/M[5] family. Comprehensive,
  current, and (critically for the VA's VistA install base) the
  engine that VistA runs on in production.
* **Where it lives upstream.** The rendered docs live at
  `https://docs.intersystems.com/irislatest/csp/docbook/Doc.View.cls`
  with content addressed by a `KEY` query parameter
  (e.g. `KEY=RERR_system` for the M-language system error reference,
  `KEY=RCOS` for the ObjectScript Reference). InterSystems publishes
  this docs site freely to read; there is no public source
  repository (unlike YottaDB's `YDBDoc` repo on GitLab), so the only
  acquisition path is to crawl the rendered HTML.
* **How it is captured.** A bounded crawl from a configurable seed
  set of `KEY`s (default: the M-language relevant subset — error
  references, ObjectScript reference, Class Reference). Pages are
  saved under `sources/iris/site/<KEY>.html` with the page body
  preserved byte-for-byte. The crawl is *seed-bounded* rather than
  link-following because the IRIS docs are vast (thousands of
  pages, including SQL, %CSP, productions, deployment, etc.) and
  most of it is out of scope for an M-language standard.
* **Version pinned.** v0.2 pins to the `irislatest` redirect
  resolved at project start (recorded in `sources/iris/manifest.tsv`
  by URL, fetch date, and sha256). The `irislatest` URL itself
  redirects to the most recent release (e.g. 2026.1); the manifest
  records which release was actually fetched for reproducibility.
* **Treatment.** Per AD-01, IRIS is authoritative for current IRIS
  engine behaviour. IRIS-specific extensions are flagged
  `standard_status=iris-extension`. Where IRIS and YottaDB describe
  the same construct under different names (`<DIVIDE>` vs
  `DIVZERO`), the integrated layer joins them via cross-vendor
  mappings under `mappings/` (see ADR-006 + spec §5.6).
* **Redistribution.** InterSystems publishes the docs free to read
  but with copyright reserved; v0.2 treats the bulk crawl like
  AnnoStd's mirror — gitignored pending explicit redistribution
  permission, with manifest + fetch.sh tracked so the local replica
  is reproducible.

### 4.4 Redistribution and snapshot policy

Each source has its own license; the offline-replica strategy is
applied within those constraints.

* **AnnoStd mirror.** The M Technology Association has
  historically encouraged mirroring of AnnoStd. Subject to a
  license check at Phase A0, the crawled mirror under
  `sources/anno/site/` is committed directly so a fresh clone
  is browseable offline with no network round-trip. If the
  license check at A0 disallows redistribution, `sources/anno/`
  retains only `manifest.tsv` plus a `fetch.sh` that recreates
  the local mirror from the upstream host; the analysis pipeline
  is unchanged because it always reads the local mirror.
* **YottaDB documentation clone.** The YottaDB documentation
  source repository is open-source and freely cloneable. The
  preferred mode is to commit the clone into `sources/ydb/repo/`
  as a vendored snapshot, so the project's source-of-truth is
  fully self-contained and reproducible. If repository size or
  policy makes vendoring undesirable, `sources/ydb/` instead
  carries `manifest.tsv` (with remote URL + pinned commit SHA)
  plus a `fetch.sh` that performs `git clone --depth=1 …` at
  the pinned commit. Either way, the local clone is what the
  pipeline reads.

In every case, every file under `sources/<src>/` appears in
`sources/<src>/manifest.tsv` with URL → local path → sha256 →
fetch date, and the manifest is the authority CI uses to detect
drift.

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
* Standard status (`ansi`, `ydb-extension`)
* Per-source section references (`anno_section`, `ydb_section`)
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
| `in_ydb` | bool | Present in YottaDB documentation corpus |
| `anno_section` | string | Reference if `in_anno` |
| `ydb_section` | string | Reference if `in_ydb` (file path + heading anchor in the cloned docs repo) |
| `standard_status` | enum | `ansi` / `ydb-extension` |
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
| `ydb_says` | string | What the YottaDB documentation says (or "absent") |
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
| `source_url` | string | Origin URL (web URL for AnnoStd pages, repo + path for the YDB clone) |
| `local_path` | string | Path under `sources/<src>/` (mirrored page or file in the cloned repo) |
| `sha256` | string | Content hash of the local file |
| `fetched_at` | datetime | ISO-8601 fetch / clone timestamp |
| `format` | enum | `html` / `rst` / `md` / `txt` / `asset` |
| `commit_sha` | string | For `sources/ydb/`: the pinned commit of the YottaDB docs repo this file is from. Empty for AnnoStd. |
| `extraction_target` | string | Which `per-source/<src>/<concept>.tsv` rows it feeds |

---

## 7. Reconciliation and validation methodology

### 7.1 Per-source extraction

Each source has its own extractor (`tools/extract-anno.py`,
`tools/extract-ydb.py`). Both extractors read exclusively from
the offline local replicas under `sources/` — `extract-anno.py`
walks the crawled HTML mirror, `extract-ydb.py` walks the
cloned YottaDB documentation repository. Neither reaches the
network at run time. Extractors are deliberately conservative
— they do not interpret, they just pull structured facts from
the source's own organization into the per-source TSV format.
Every extracted row cites its `source_section`.

### 7.2 Two-way reconciliation

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
   `in_anno`/`in_ydb` flags consistent with the per-source
   TSVs. No integrated row may exist without at least one
   source attesting it.
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

When a pinned source version is updated, the workflow is:
refresh the local replica (re-crawl AnnoStd, or re-run
`tools/clone-ydb.sh` with `PIN_COMMIT=<new_sha>` to mirror a
new commit of the YottaDB docs), bump the manifest with the new
sha256s and (for YDB) the new commit SHA, re-run extraction,
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
│   │   ├── site/                  # Crawled offline mirror of AnnoStd; browseable as file:// or via `make serve-anno`
│   │   └── fetch.sh               # Re-crawls the mirror from the upstream host
│   └── ydb/
│       ├── manifest.tsv           # Includes upstream remote URL + pinned commit SHA
│       ├── repo/                  # Vendored working tree from the YottaDB documentation repository (inner .git/ stripped)
│       └── fetch.sh               # Re-runs the clone+strip mirror at the pinned commit
├── per-source/
│   ├── anno/
│   │   ├── commands.tsv
│   │   ├── intrinsic-functions.tsv
│   │   ├── intrinsic-special-variables.tsv
│   │   ├── operators.tsv
│   │   ├── pattern-codes.tsv
│   │   ├── errors.tsv
│   │   └── environment.tsv
│   └── ydb/  (same shape)
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
│   │   ├── 001-two-source-hierarchy.md
│   │   ├── 002-normative-vs-annotation-separation.md
│   │   ├── 003-per-source-preservation.md
│   │   ├── 004-tsv-plus-json-output.md
│   │   ├── 005-build-time-consumability.md
│   │   └── ...
│   └── build-log.md
├── tools/
│   ├── crawl-anno.py              # Crawls AnnoStd into sources/anno/site/ for offline browsing + extraction
│   ├── clone-ydb.sh               # Clones / updates the YottaDB docs repo into sources/ydb/repo/ at the pinned commit
│   ├── extract-anno.py            # AnnoStd local mirror → per-source TSVs
│   ├── extract-ydb.py             # YottaDB cloned docs repo → per-source TSVs
│   ├── reconcile.py               # per-source → integrated + conflicts
│   ├── emit-json.py               # integrated TSVs → JSON per-entry
│   └── validate.py                # CI validation harness
├── .github/workflows/
│   └── ci.yml
├── CHANGELOG.md                   # Schema versions and source pin updates
├── LICENSE                        # AGPL-3.0
├── README.md
├── pyproject.toml                 # Inherits vista-meta python style
└── Makefile                       # `make sources`, `make serve-anno`, `make extract`, `make reconcile`, `make validate`, `make all`
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

### 10.1 m-parser (tree-sitter-m)

[`m-parser`](../../m-parser) is the tree-sitter grammar project
for M (separate repo at `~/projects/m-parser/`, sibling to
`m-standard`). Its full design is in
[`m-parser/docs/spec.md`](../../m-parser/docs/spec.md). The
relationship is one-way and minimally coupled: m-parser is a
**strict downstream consumer** that reads exactly one file from
m-standard at build time — `integrated/grammar-surface.json` —
and ships pre-generated artifacts so its own consumers (npm /
crates.io / PyPI / Go) need neither m-standard nor
tree-sitter-cli to install.

`m-parser`'s `tools/build-grammar.js` reads
`grammar-surface.json` and emits the data-driven half of
`grammar.js`: every command / function / ISV / operator / pattern
code from the union of all sources, with abbreviation prefix-form
expansion already done. The hand-written parts of the grammar
(line structure, postconditionals, dot blocks, indirection,
strings, numbers) remain hand-written because they're invariant
across sources.

Per `m-parser`'s AD-01, the parser implements the **union** of
all sources, NOT the pragmatic / SAC / operational subsets.
Subsetting belongs in the linter layer one level up (see
§10.3 below). Per AD-03, every recognised keyword node carries
its `standard_status` as an AST attribute so downstream tools
can classify portability tier without re-parsing.

Per `m-parser`'s AD-04, m-parser pins to a specific
`schema_version`. m-standard's additive schema changes (new
tokens, new optional fields) flow through automatically;
breaking changes (per ADR-005 here) require deliberate adoption
in m-parser and bump m-parser's major version.

### 10.2 tree-sitter-m-lint (planned)

The planned sibling of `m-parser`. Consumes both m-parser's AST
and m-standard's tier classifications:

- `integrated/operational-m-standard.json` — the strictest
  default profile (portable + SAC-clean)
- `integrated/pragmatic-m-standard.tsv` + `va-sac-compliance.tsv`
  — looser profiles (`--profile=pragmatic`, `--profile=portable-vendor`)
- `integrated/va-sac-rules.tsv` — pattern-rule definitions
  consumed alongside `m_standard.tools.lint_m`'s detector logic

This is where the actual standards-enforcement happens for
downstream code. The parser stays neutral; the linter takes
sides per the developer's chosen profile.

### 10.3 vista-meta

vista-meta's analyzers gain a new metadata source: the
integrated TSVs are joinable to existing 19 code-model TSVs.
Example: a "commands actually used in VistA vs commands in the
standard" coverage report is a single join.

### 10.4 AI agents and other tooling

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
| **A0** | Source acquisition & offline replicas. Crawl AnnoStd into `sources/anno/site/`; `git clone` the YottaDB documentation repository into `sources/ydb/repo/` at a pinned commit. Verify redistribution rights for each. Stand up repo skeleton with AGPL, ADR directory, build-log stub, CI skeleton, Makefile. | Both offline replicas exist locally and are browseable / walkable; manifests committed; AnnoStd mirror opens correctly from disk; YDB clone is at a pinned SHA. CI skeleton runs green. |
| **A1** | Per-source extractors for both sources, reading exclusively from the local replicas. Iterate per concept family (commands first, then intrinsics, then the rest). | All seven concepts extracted from both sources where present. Per-source TSVs committed and reviewed. |
| **A2** | Reconciler. AD-01 hierarchy implemented. `conflicts.tsv` populated. Manual resolution of every `PENDING-MANUAL` conflict. | Reconciler is deterministic; integrated TSVs committed; `conflicts.tsv` has zero `PENDING-MANUAL` rows. |
| **A3** | JSON emitter and schemas. TSV/JSON consistency enforced in CI. | Every concept has a passing JSON file matching its schema. |
| **A4** | M-Standards-Guide narrative. One chapter per concept family. Cites integrated outputs for every claim. | Document reviewed and merged. |
| **A5** | ADRs (one per architectural decision plus any project-specific decisions made during A1–A4). Build log up to date. | ADR set complete. Build log has BL entries for any non-trivial issues encountered. |
| **A6** | Validation harness complete. All seven validation gates from §7.4 enforced in CI. | CI gates all seven checks; PR-per-milestone workflow validated. |
| **v1.0** | Tag and release. | All §13 success criteria met. |

Estimated total: **~5–8 days of focused work for v1.0.**

The largest unknowns are AnnoStd extraction quality (how
machine-extractable the mirrored HTML actually is) and conflict
volume (how often the two sources actually disagree on
substantive points). Both will be quantified at A1 exit and may
revise the A2 estimate.

---

## 12. Risks and open questions

**AnnoStd availability.** The host at 71.174.62.16 is a single
point of failure. Mitigation: crawl into a local mirror once at
A0 and pin to that mirror for v1.0. Even if the upstream goes
offline mid-project, all extraction and analysis continue from
the local replica. Long-term mitigation: if redistribution is
permitted, the mirror committed to the repo *is* the durable
copy and protects against permanent loss of the upstream host.

**AnnoStd extraction quality.** Static HTML from a 1990s-era
site is rarely well-structured. The extractor may need to be
tag-soup-tolerant. Budget extra time at A1 for this; if
extraction yield is poor, fall back to manual transcription of
the affected sections (AnnoStd is not enormous — ~300 pages
equivalent). Because the mirror is local and stable, transcription
work is reproducible against an unchanging input.

**Conflict volume.** The two sources will agree on the bulk of
standard M; conflicts concentrate around (a) under-specified
ANSI behavior where YottaDB filled in defaults of its own,
(b) YottaDB Z-extensions that overlap or extend ANSI surface
area, and (c) errata in AnnoStd. If conflict volume exceeds
~100 rows, A2 will need additional review time.

**Z-extension namespace.** YottaDB uses the `$Z*` and `Z*`
namespace for its extensions. The integrated layer records
`extension_of=ydb` per row so consumers can cleanly distinguish
ANSI surface area from vendor surface area. (GT.M historically
used the same namespace with occasional divergent semantics; that
divergence is out of scope for v1.0 — see §2.)

**Source license redistribution.** AnnoStd's mirror and the
YottaDB documentation clone each have their own redistribution
status. Phase A0 verifies both. The pipeline is unaffected
either way: when a source is non-redistributable, `sources/<src>/`
carries `manifest.tsv` plus a `fetch.sh` that recreates the
local replica, and extraction reads the recreated replica.

**Standard versioning.** AnnoStd is the 1995 standard. The M
Development Committee circulated draft revisions post-1995 that
were never formally approved. Some of those drafts' content is
present in YottaDB as "common practice" but is not standard per
AnnoStd. Per AD-01 + AD-02, these go in as
`standard_status=ydb-extension`, not as ANSI standard.

**Pin-stability vs currency.** v1.0 pins to source snapshots.
Future versions update the pins. The trade-off: pin-stability
gives reproducibility for downstream consumers; currency gives
accuracy. The CHANGELOG.md and version bumps are how this is
managed.

---

## 13. Success criteria for v1.0

The following must all be true for v1.0 release:

1. **Offline source replicas in place.** Both sources are
   available as offline local replicas (AnnoStd as a crawled
   browseable HTML mirror, YottaDB as a `git clone` of its
   documentation repository at a pinned commit), either
   committed or recreatable via `make sources`, with verified
   manifests (URL, sha256, fetch date, and commit SHA for the
   YDB clone). The AnnoStd mirror opens and navigates correctly
   from `file://` and via `make serve-anno`.
2. **Per-source extraction complete.** All seven concept
   families extracted from each of the two sources where the
   source covers that concept, reading exclusively from the
   local replicas.
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

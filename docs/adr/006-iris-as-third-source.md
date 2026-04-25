# ADR-006 — Add InterSystems IRIS as a third primary source

**Status:** accepted (v0.2)
**Spec reference:** `docs/spec.md` §1, §3 AD-01 (revised), §4.3
**Supersedes (in part):** ADR-001 (v0.1 two-source hierarchy)

## Context

v1.0 of `m-standard` shipped as a deliberately two-source project:
AnnoStd (1995 ANSI X11.1, normative for the standard) and YottaDB
(authoritative for current open-source M engine behaviour). ADR-001
documented why GT.M was excluded — its Programmer's Guide is no
longer reliably accessible.

That two-source framing was correct for the open-source M ecosystem,
but it left out the vendor that **operationally matters most for the
biggest M codebase in existence**: InterSystems IRIS, the engine
that runs VistA in production at the Department of Veterans Affairs.

A reference standard that catalogues YottaDB's `DIVZERO` but not
IRIS's `<DIVIDE>` is incomplete from the perspective of any
downstream tool that reasons about VistA — which is the dominant
real-world M codebase, and a primary motivation for `m-standard`'s
sibling projects (`vista-meta`, `vista-docs`).

## Decision

InterSystems IRIS becomes the third primary source as of v0.2.

The hierarchy in AD-01 is revised:

- **AnnoStd** stays normative for "is X part of the standard."
- **YottaDB** and **IRIS** are *peers* for current implementation
  behaviour — neither outranks the other. Where they describe the
  same ANSI construct under different names, that's a cross-vendor
  mapping (recorded in `mappings/`), not a hierarchy decision.
- A new `multi-vendor-ext` value of `standard_status` flags entries
  present in both YDB and IRIS but not in AnnoStd — de facto
  extensions the M community has converged on.

## Why now (and why not earlier)

When v1.0 shipped, the project's design was deliberately
conservative — keep the source set small, get the pipeline shape
right, prove the reconciler is byte-deterministic. With those
foundations in place (ADRs 001–005, eight CI gates, three persisted
pipeline stages), adding a third source is incremental architectural
change, not foundational. The extractor and reconciler already
parameterise on per-source manifests; the integrated TSV columns
already carry per-source presence flags; the JSON schemas already
allow new `standard_status` enum values as additive
(non-version-bumping) per ADR-005.

## What changes mechanically

- `sources/iris/` joins `sources/anno/` and `sources/ydb/` as a
  first-class source tree.
- A bounded IRIS crawler (`m_standard.tools.crawl_iris`) downloads
  M-language-relevant pages from `docs.intersystems.com/irislatest`
  by KEY, using a seed list rather than full link-following (IRIS's
  docs include vast areas — SQL, productions, %CSP — that are out
  of scope for an M-language standard).
- A new `extract_iris` module produces `per-source/iris/*.tsv`.
- The reconciler grows to handle the three-way join. Where v1.0
  used per-concept specialised reconcilers (`reconcile_commands`,
  `reconcile_errors`, etc.) that were two-source, v0.2 generalises
  them to N-source with the same key-field-driven join.
- `mappings/iris-ydb-errors.tsv` (new) and the existing
  `mappings/ydb-ansi-errors.tsv` triangulate the three error
  namespaces. The integrated `errors.tsv` row for `DIVZERO` will
  carry both `ansi_code=M9` and `iris_mnemonic=<DIVIDE>`.
- The validation harness gains a coverage-symmetry gate: every
  cross-vendor mapping endpoint must exist in the target source's
  per-source TSV (extension of the existing `mapping-integrity`
  gate to handle multiple mapping files).

## What does NOT change

- AnnoStd remains normative for ANSI status (AD-01 rule 1).
- The pipeline shape (sources → per-source → integrated → JSON →
  validate) is unchanged.
- The `schema_version="1"` JSON contract is preserved — adding
  `iris-extension` and `multi-vendor-ext` to the `standard_status`
  enum is an additive change per ADR-005, no version bump.
- Per-source TSVs remain raw per spec §6.1.
- The round-trip determinism gate still gates CI.

## Consequences

- **Downstream coverage roughly triples on the implementation side.**
  IRIS catalogues hundreds of error mnemonics, dozens of `$Z*`
  functions/svns, and a parallel command set with its own
  abbreviations.
- **The cross-vendor mapping work becomes ongoing curation.**
  v1.0's 18-row `ydb-ansi-errors.tsv` was a starter; v0.2 adds the
  IRIS axis and grows the mapping table accordingly. This is
  manual work — there's no shortcut.
- **Reproducibility cost rises.** IRIS docs aren't versioned by a
  public commit hash like YottaDB's GitLab clone. v0.2 pins the
  IRIS release reported by the `irislatest` redirect at fetch time;
  if the upstream redirect moves, the manifest's recorded sha256s
  catch the drift but a deliberate refresh is required to advance
  the pin.
- **GT.M stays out.** The decision in ADR-001 to exclude GT.M
  remains in force. Adding IRIS does not reopen GT.M — different
  vendor, different access situation, different operational
  relevance.

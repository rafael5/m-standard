# ADR-003 — Per-source preservation alongside integrated output

**Status:** accepted (v0.1)
**Spec reference:** `docs/spec.md` §3 AD-03

## Context

`m-standard`'s output is a *reconciled* view across two sources
(AnnoStd and the YottaDB documentation corpus). Reconciliation is
inherently lossy and opinionated: it picks one source's wording over
another, flags some divergences as conflicts and lets others pass,
applies the AD-01 hierarchy, and so on.

Two failure modes follow from publishing only the reconciled view:

1. **Opacity.** A consumer who disagrees with a reconciliation
   decision (or who simply wants to know what one source said in
   isolation) cannot reconstruct that view from the integrated layer
   alone.
2. **Non-reproducibility on re-extraction.** When upstream sources
   are refreshed and the extractor reruns, the diff in the
   integrated layer is hard to attribute. Was the change a real
   upstream change? An extractor regression? A reconciliation
   policy shift?

## Decision

Raw per-source TSVs are preserved as **first-class artifacts**,
not intermediate scratch:

- `per-source/anno/<concept>.tsv` — raw extraction from AnnoStd.
- `per-source/ydb/<concept>.tsv` — raw extraction from the YottaDB
  documentation clone.

The integrated layer in `integrated/` is *derived* from these two
trees and carries provenance columns (`in_anno`, `in_ydb`,
`anno_section`, `ydb_section`) so every integrated row can be
traced back to its source rows.

Both per-source TSVs are themselves derived from the offline local
replicas under `sources/` — AnnoStd as a crawled HTML mirror,
YottaDB as a vendored clone of its documentation GitLab repository.
Extraction never reaches the live network at run time; the local
replica is the analysis foundation, and the upstream is consulted
only when a snapshot is deliberately refreshed.

## Consequences

- **Single-source queries are first-class.** A consumer who wants
  "what does YottaDB alone say about `$ZSEARCH`?" can read
  `per-source/ydb/intrinsic-functions.tsv` directly without going
  through the reconciler.
- **Reproducibility holds end-to-end.** Per-source TSVs + the
  reconciler are byte-deterministic; the integrated layer is the
  reconciler's output. The validation harness's round-trip gate
  (spec §7.4) enforces this in CI.
- **Extractor regressions are localised.** A change in extractor
  behaviour shows up as a diff in the per-source TSV first, then
  propagates predictably into the integrated layer.
- **The data pipeline has three persisted stages.** Sources →
  per-source → integrated. Each stage's output lives in the repo;
  intermediate state is never lost and never invisible.

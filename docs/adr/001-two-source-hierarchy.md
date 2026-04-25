# ADR-001 — Two-source hierarchy with explicit precedence

**Status:** accepted (v0.1)
**Spec reference:** `docs/spec.md` §3 AD-01

## Context

`m-standard` synthesises a reference standard for M from documentation
that lives in different places, was written at different times, and
serves different purposes. There is no single canonical, machine-readable
ANSI M standard available today.

Three documentation sources were considered:

1. **Annotated M Standard (AnnoStd)** — the 1995 ANSI X11.1 standard with
   committee annotations, hosted as a static HTML tree at
   `http://71.174.62.16/Demo/AnnoStd`. Normative for the standard, but
   ageing and unstructured.
2. **YottaDB documentation corpus** — current, comprehensive
   documentation for the leading open-source M engine, available as a
   `git`-versioned source repository on GitLab.
3. **GT.M Programmer's Guide** — historical sibling of YottaDB,
   maintained by Fidelity National Information Services. No longer
   reliably accessible in a form we can pin to.

## Decision

Reconcile **two** sources — AnnoStd and the YottaDB documentation
corpus — under a fixed precedence hierarchy:

- **AnnoStd is normative for what counts as standard ANSI M.** If
  AnnoStd does not describe a behaviour, that behaviour is not part of
  the standard, regardless of what the YottaDB documentation says.
- **YottaDB is authoritative for current real-world implementation
  behaviour** of the leading open-source M engine, and the source of
  truth for YottaDB-specific extensions
  (`standard_status=ydb-extension`).

Disagreements are not silently resolved — every conflict is recorded in
`integrated/conflicts.tsv` with the resolution and a reference back to
this ADR.

## GT.M is out of scope (for v0.1)

GT.M would have been a natural cross-check on YottaDB (since YDB
descends from GT.M) and the authority for the small set of GT.M-isms
that did not carry forward into YDB. It is excluded from v0.1 because
its Programmer's Guide is no longer reliably accessible at a stable
URL we can pin and hash, and a source we cannot pin cannot meet the
project's reproducibility requirement.

If a durable mirror of the GT.M Programmer's Guide surfaces later, the
hierarchy can be extended in a v0.2 ADR. The integrated schema (`in_*`
provenance flags, conflict-table columns) was designed with addition in
mind.

## Consequences

- The integrated layer carries `in_anno` and `in_ydb` provenance flags
  per row; `standard_status` is `ansi` or `ydb-extension`.
- Conflict resolution is a two-way decision (`anno_says` vs
  `ydb_says`), simpler than a three-way reconciliation but less
  defensible against YDB-only divergence from prior GT.M behaviour.
  We accept this trade-off until a stable third source returns.
- Z-namespace divergence between YDB and historical GT.M is documented
  as historical context but not modelled per row (see spec §12 risks).

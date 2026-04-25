# ADR-002 — Separate normative text from annotations

**Status:** accepted (deferred for v1.0; see Implementation status below)
**Spec reference:** `docs/spec.md` §3 AD-02

## Context

The Annotated M Standard (AnnoStd) bundles two kinds of content on
the same pages:

- **Normative text:** the words of the 1995 ANSI X11.1 standard
  itself. These words establish what is and is not standard ANSI M.
- **Annotations:** commentary by the M Development Committee —
  examples, historical context, intent, errata. Annotations are
  *non-normative*; they explain the standard but do not create
  obligations.

A common error in informal citations of AnnoStd is to quote an
annotation as if it were standard. AnnoStd's editors call this out
explicitly with a separate "notes" edition, which renders only the
annotations layer.

If `m-standard` extracted both layers as a single blob it would
inherit the same confusion. A downstream consumer reading
`integrated/commands.json` could not tell whether a particular
behaviour they're seeing is actually in the standard or is editorial
commentary on it.

## Decision

The extraction pipeline must distinguish normative text from
annotations:

- Only the normative standard text drives standard claims (i.e.
  `standard_status=ansi`).
- Annotations are preserved as supplementary context — held in a
  dedicated `anno_commentary` column on relevant TSV rows — but do
  not establish standard behaviour.

Conflating the two is the most common error in informal citations of
AnnoStd and is explicitly avoided here.

## Implementation status (v1.0)

The current AnnoStd extractor (`m_standard.tools.extract_anno`) reads
the `Edition=1995` content only. The `Edition=notes` edition would
be the source for the annotation layer; pulling it in requires a
second crawl pass and extending each per-source TSV with the
`anno_commentary` column.

For v1.0 the extractor populates only the normative layer (Edition
1995). The `anno_commentary` column is reserved on the per-source
schema but always empty. A future release will add a parallel `notes`
crawl and populate the column. The decision in this ADR is
unchanged; only the implementation is staged.

This staging is logged in `docs/build-log.md` so the gap is visible
to consumers and to future maintainers.

## Consequences

- Per-source TSVs from AnnoStd carry verbatim 1995-edition text;
  they do not silently mix in annotations.
- Until the parallel notes crawl lands, AnnoStd-derived rows in the
  integrated layer represent the normative-only view of the 1995
  standard. Where annotations would have nuanced a row, the
  reconciler simply doesn't have access to that nuance yet.
- The dual-edition extraction pattern is also reusable for the
  earlier ANSI versions (1977, 1984, 1990, MDC) AnnoStd carries.

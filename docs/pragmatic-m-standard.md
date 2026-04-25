# The Pragmatic M Standard

> **What "pragmatic" means here.** Strictly: *portable across YottaDB
> and InterSystems IRIS*. It is a mechanical set-intersection over
> the source documentation, not a judgement about what's wise to
> write. An entry being in the pragmatic standard means it **can run**
> on both engines unmodified — not that you **should** use it.
>
> For VistA development specifically, you also need VA SAC compliance
> (security, code-quality, long-term-maintainability rules that the
> pragmatic standard does not model). The intersection of pragmatic +
> SAC-clean is the **operational M standard**, published as a
> separate output:
> [`integrated/operational-m-standard.tsv`](../integrated/operational-m-standard.tsv)
> and explained in [`docs/va-sac-and-pragmatic-standard.md`](va-sac-and-pragmatic-standard.md).
>
> If you came here looking for "what M can a VistA developer
> actually write", read that doc, not this one.

A **portable subset** of the M (MUMPS) language — the cross-vendor
surface that runs unmodified on both YottaDB and InterSystems IRIS,
the two M engines that matter for VistA development today.

This is one of the published outputs of `m-standard`, alongside the
per-concept integrated TSVs/JSONs and the grammar surface. It is
**auto-derived** from the integrated layer; nothing here is
hand-curated. Re-running the pipeline regenerates this file
deterministically.

> **TL;DR (portability angle only).** If you need code that runs on
> both YottaDB (open-source, OSEHRA's target) and IRIS (commercial,
> the VA's production engine), restrict yourself to entries with
> `pragmatic_tier=core` in [`integrated/pragmatic-m-standard.tsv`](../integrated/pragmatic-m-standard.tsv).
> That's **81 entries** in v0.2: 29 commands, 26 intrinsic functions,
> 26 intrinsic special variables. **For VistA, intersect with SAC**
> — the operational subset is **58 entries**.

## Pragmatic ≠ operational ≠ wise

These three terms are easy to conflate. They are not the same.

| Standard | Question it answers | Optimises for | Output |
| --- | --- | --- | --- |
| **Pragmatic** (this doc) | Will this run on both engines? | Portability across YDB and IRIS | `pragmatic-m-standard.tsv` (81 entries) |
| **VA SAC** (XINDEX-derived) | Should we write this in VistA? | Security, code quality, decades of maintenance | `mappings/va-sac.tsv` + `va-sac-rules.tsv` |
| **Operational** (intersection) | What can a VistA developer actually use? | Both portability AND policy-compliance | `operational-m-standard.tsv` (58 entries) |

The pragmatic standard is **strictly more permissive than
operational**: it includes 23 entries (BREAK, HALT, JOB, VIEW,
ZWRITE, $ZHOROLOG, etc.) that are portable but SAC blocks for
non-portability reasons. The compliance counts in
`integrated/va-sac-compliance.json` show this directly:
zero entries where SAC permits something non-portable, but 23
where SAC forbids something portable.

If "pragmatic" sounds like "the wise default," that's the wrong
read. *Pragmatic = portable.* For "wise + portable," see the
operational standard.

## Why this exists

Three competing realities make "writing portable M" harder than it
sounds:

1. **The 1995 ANSI standard** is normative for what counts as
   standard M, but documents commands (Async I/O, MWAPI events,
   RLOAD/RSAVE) that no current vendor implements. Coding to the
   standard alone leaves you using features that don't run anywhere.

2. **Each vendor has filled in the standard's gaps** with its own
   extensions. YottaDB has $ZTRIGGER, ZRUPDATE, $ZAUDIT. IRIS has
   TRY/CATCH, $CASE, $ZBOOLEAN. Code that uses any of these is
   non-portable to the other engine.

3. **The two vendors converged on a de facto core** of practical
   extensions both implement: `ZWRITE`, `$INCREMENT`, `$ZHOROLOG`,
   `$ZTRAP`, etc. These aren't in ANSI but they're safe to use on
   either engine — and VistA depends on many of them.

The "pragmatic M standard" is the answer to "what should I actually
restrict myself to?" — the **intersection of what YDB and IRIS both
support**, regardless of ANSI status. ANSI is the floor, not the
ceiling, of portable M.

## How tiering works

Every entry in the integrated layer is classified into one of four
**pragmatic tiers** based on its source presence:

| Tier | Rule | What it means for VistA developers |
| --- | --- | --- |
| `core` | `in_ydb && in_iris` | **The pragmatic standard.** Use freely; portable across both engines. |
| `ydb-only` | `in_ydb && !in_iris` | YDB-specific. Avoid when targeting IRIS. |
| `iris-only` | `!in_ydb && in_iris` | IRIS-specific. Avoid when targeting YDB. |
| `ansi-unimplemented` | `in_anno && !in_ydb && !in_iris` | Standard-but-historical. Do not use. |

**The `core` tier is the pragmatic standard.** It includes both:

- **The ANSI core that survived** — entries in the 1995 standard
  that both vendors actually implement. The largest group; the
  safest layer.
- **De-facto multi-vendor extensions** — entries both vendors
  shipped without ANSI sanction (`ZWRITE`, `$INCREMENT`,
  `$ZHOROLOG`, etc.). The M community converged on these; the M
  standard hasn't yet.

## Coverage in v0.2

| Concept | Core | YDB-only | IRIS-only | ANSI-unimplemented | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| commands | **29** | 21 | 18 | 14 | 82 |
| intrinsic-functions | **26** | 34 | 93 | 6 | 159 |
| intrinsic-special-variables | **26** | 39 | 16 | 1 | 82 |
| **Total** | **81** | 94 | 127 | 21 | 323 |

The numbers tell a useful story:

- **Commands** have the highest portable percentage (29/82 ≈ 35%
  core). Most of the M language's flow-control surface works on
  both engines.
- **Functions** have the worst (26/159 ≈ 16% core). IRIS in
  particular has aggressively extended the function namespace —
  93 IRIS-only functions, mostly trigonometric (`$ZSIN`,
  `$ZARCCOS`), JSON/array (`$LISTBUILD`, `$LISTGET`), and class-related.
- **ISVs** are middle (26/82 ≈ 32% core). The shared core is
  smaller than expected because vendors disagree on naming for
  many state variables (e.g. YDB's `$ZA` vs IRIS's `$ZA` are both
  there, but their semantics differ).

## How to consume it

### As a TSV (analysts, shell scripts, lint rules)

```bash
# All 81 portable entries:
awk -F'\t' '$3=="core"' integrated/pragmatic-m-standard.tsv

# Just the portable commands:
awk -F'\t' '$1=="commands" && $3=="core" {print $2}' \
  integrated/pragmatic-m-standard.tsv

# Things to flag in code review (used IRIS-only feature):
grep -F -w -f \
  <(awk -F'\t' '$3=="iris-only" {print $2}' \
      integrated/pragmatic-m-standard.tsv) \
  some-vista-routine.m
```

### As JSON (linters, code generators, agents)

```python
import json
data = json.load(open("integrated/pragmatic-m-standard.json"))

portable_command_names = {
    e["name"] for e in data["entries"]
    if e["concept"] == "commands" and e["pragmatic_tier"] == "core"
}
```

### As a grammar input

The grammar surface ([`integrated/grammar-surface.json`](../integrated/grammar-surface.json))
already has `standard_status` per entry; combine with the pragmatic
standard to gate token recognition by portability tier.

```python
import json
gs = json.load(open("integrated/grammar-surface.json"))
prag = json.load(open("integrated/pragmatic-m-standard.json"))
core_names = {e["name"] for e in prag["entries"] if e["pragmatic_tier"] == "core"}

portable_commands = [c for c in gs["commands"] if c["canonical"] in core_names]
# portable_commands now has 29 entries with all_forms expanded.
```

## Limitations and scope

- **The pragmatic standard is about *names*, not *semantics*.**
  Two vendors implementing the same name with subtly different
  argument signatures or return values will both show up as `core`.
  Catching those divergences requires per-entry signature
  comparison — out of scope for v0.2 but tracked as future work.
- **Format strings are still vendor-specific.** AnnoStd's
  metalanguage (`postcond`, `SP`) and YottaDB's (`[:tvexpr]`)
  describe the same constructs differently; v1.0+ of the
  reconciler does not normalise across them. The `format` field
  on each integrated row is informational, not a normalised parse
  tree.
- **Operators and pattern codes are not tiered yet.** v0.2 ships
  IRIS data only for the named-entry concepts (commands /
  functions / ISVs). When the IRIS operator + pattern-code
  extractors land, this artifact will gain those tiers without a
  schema-version bump (the `concept` enum is open per ADR-005).
- **Errors are intentionally excluded.** Error mnemonics live in
  three disjoint namespaces (AnnoStd `Mn`, YDB vendor mnemonics,
  IRIS `<NAME>` style); the cross-vendor mapping there is handled
  separately in [`mappings/`](../mappings/) and [`integrated/errors.tsv`](../integrated/errors.tsv).
- **Nothing here is hand-curated.** This file is a deterministic
  derivation from the integrated layer. Disagreement with a
  classification means the underlying source TSV is wrong (or the
  source itself is — file an issue / fix the extractor / refresh
  the source pin).

## How VistA development actually uses this

The intended workflow is gradual, not big-bang:

1. **Existing IRIS-only VistA code:** keep running on IRIS as
   today. The pragmatic standard is not a migration mandate.
2. **New code or refactors:** target the `core` tier; check any
   non-`core` use against this artifact at code review time. A
   simple lint rule (`grep` against the iris-only / ydb-only
   names) catches accidental coupling.
3. **Cross-engine verification:** when YottaDB-flavoured VistA
   (e.g. OSEHRA's effort) needs to consume an IRIS routine, the
   `iris-only` and `ydb-only` lists tell you exactly what to
   shim, port, or replace.
4. **Tooling (formatters, linters, language servers):** consume
   `pragmatic-m-standard.json` to flag portability concerns at
   edit time.

## Provenance

This artifact is regenerated whenever the integrated layer
regenerates. Source pins as of v0.2:

- AnnoStd: Edition 1995, mirror crawled 2026-04-25
- YottaDB: `gitlab.com/YottaDB/DB/YDBDoc.git` at commit
  `25a97c4c8405bcccc85e7a4eadc4f91bd07b6de9` (2026-04-21)
- IRIS: `docs.intersystems.com/irislatest`, RCOS subset crawled
  2026-04-25 (303 pages)

Schema: pinned at `schema_version: "1"` per ADR-005. Breaking
changes will bump and announce in `CHANGELOG.md`.

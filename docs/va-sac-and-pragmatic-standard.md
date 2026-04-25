# VA SAC vs the Pragmatic M Standard

Two standards layer over M for VistA development:

1. **The pragmatic M standard** ([`integrated/pragmatic-m-standard.tsv`](../integrated/pragmatic-m-standard.tsv))
   — what runs on both YottaDB and InterSystems IRIS. Auto-derived
   from per-source documentation.
2. **The VA Standards and Conventions (SAC)** — what the VA
   officially permits or forbids in VistA M code. A policy
   document, not a language definition.

These layers answer different questions. The pragmatic standard
asks "is this *possible* on both engines?" SAC asks "is this
*allowed* in VistA?" An entry can be portable but forbidden by
policy (e.g. `XECUTE` runs everywhere but SAC restricts it for
security reasons). An entry can also be SAC-permitted but
non-portable — that's a portability gap worth surfacing.

This artifact joins the two and flags the gaps.

## How the join works

[`m_standard.tools.emit_sac_compliance`](../src/m_standard/tools/emit_sac_compliance.py)
reads the SAC overlay ([`mappings/va-sac.tsv`](../mappings/va-sac.tsv))
and joins it against the pragmatic standard. Each entry gets one
of five concern classifications:

| Concern | Meaning | What to do |
| --- | --- | --- |
| `aligned` | SAC permits a portable entry, OR SAC forbids an unportable entry | Nothing; this is the desired state. |
| `sac_says_use_but_not_portable` | SAC permits/recommends but the entry isn't in pragmatic-core | **Real portability gap.** VistA code following SAC literally would break on the missing engine. |
| `sac_says_avoid_but_portable` | SAC forbids/restricts but the entry IS pragmatic-core | SAC may be overly conservative, or the entry was added to both engines after SAC was written. Worth reviewing. |
| `sac_silent_on_portable` | SAC doesn't mention; entry is pragmatic-core | Probably safe but unguided. Consider adding to SAC. |
| `sac_silent_on_unportable` | SAC doesn't mention; entry is vendor-specific | Likely fine to ignore — SAC didn't anticipate the entry. |

## Outputs

- `integrated/va-sac-compliance.tsv` — flat queryable join.
- `integrated/va-sac-compliance.json` — typed bundle with counts
  summary, gated by `schemas/va-sac-compliance.schema.json`.

## SAC overlay file format

`mappings/va-sac.tsv`:

| Column | Meaning |
| --- | --- |
| `concept` | One of `commands`, `intrinsic-functions`, `intrinsic-special-variables`. |
| `name` | Canonical name as it appears in `integrated/<concept>.tsv` (must match exactly; the `mapping-integrity` validation gate enforces this). |
| `sac_status` | One of `permitted`, `recommended`, `restricted`, `forbidden`. |
| `sac_section` | Reference into the authoritative SAC document (e.g. `SAC §2.4.1`). |
| `notes` | Free-text rationale or commentary. |

Entries not in the file are treated as `sac_status=""` (silent).

## Authoritative source: XINDEX

The `mappings/va-sac.tsv` overlay is **auto-derived** from XINDEX
— the operational SAC validator the VA actually runs against
VistA M routines. XINDEX lives in the **Toolkit** package
(`Packages/Toolkit/Routines/XINDEX.m` + `XINDX1.m`–`XINDX13.m`)
and its rule table is the canonical machine-readable definition
of what SAC enforces. This is more authoritative than any prose
SAC document because it's what runs against actual code.

The 18 XINDX routines are mirrored under `sources/sac/routines/`
from `WorldVistA/VistA-M`. The full 65-rule table is parsed by
`m_standard.tools.extract_sac` from `XINDX1.m`'s `ERROR` label
and emitted as:

- `integrated/va-sac-rules.tsv` — every rule with severity
  (F/S/W/I), exempt namespaces, and description. Useful for
  downstream linters that flag pattern-level violations
  (e.g. rule 33 "READ without timeout" — not a per-name
  restriction so doesn't appear in the overlay).
- `mappings/va-sac.tsv` — the per-name overlay for entries the
  rules target by name (rule 25 "BREAK", rule 2 "any Z*
  command", rule 28 "any $Z* svn", etc.). Each row's
  `sac_section` points back at the rule (e.g.
  `XINDEX rule 25 (severity S)`).

**Update workflow.** When the VA publishes a new SAC revision,
WorldVistA/VistA-M's Toolkit package picks up the updated XINDX
routines. To refresh:

```bash
make sources-sac      # re-fetch XINDX routines
make extract          # regenerate va-sac.tsv + va-sac-rules.tsv
make reconcile emit   # propagate through the pipeline
make validate         # 9 gates including mapping-integrity
```

The `mapping-integrity` gate fails if XINDEX references a name
that doesn't exist in the integrated TSVs — useful when SAC
revs reference commands that vendors removed.

## Severity codes

XINDEX classifies violations:

| Code | Meaning |
| --- | --- |
| `F` | Fatal — parser / language error (won't compile) |
| `S` | Standard — SAC violation; fails compliance |
| `W` | Warning — discouraged but allowed |
| `I` | Info — stylistic note |

The auto-derived overlay maps:
- F/S rules with named targets → `sac_status=forbidden`
- "Use X instead" rules (HALT→XUSCLEAN, JOB→TASKMAN) → `sac_status=restricted`
- W/I rules → currently not projected to the overlay (they're in
  `va-sac-rules.tsv` for downstream linter use)

## Why this lives in m-standard rather than vista-meta

The original spec excluded SAC from m-standard's scope on the
grounds that it's a coding-style standard, not a language
standard. That framing is correct for SAC's full content (naming
conventions, formatting rules, header requirements, etc.) — but
the *language-subset* portion of SAC is exactly the kind of thing
m-standard's join machinery is good at.

This artifact handles only the language-subset overlap. The rest
of SAC (naming, formatting, headers) belongs in vista-meta or
similar tooling, where it can be applied to actual routine code.

## Future work

- Populate from the authoritative SAC document (see "How to
  populate" above).
- Extend the overlay to operators and pattern codes once SAC's
  treatment of those is incorporated.
- Add an "M-language linter" downstream tool that consumes
  `va-sac-compliance.json` and flags violations in routine
  source.

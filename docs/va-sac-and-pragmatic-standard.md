# VA SAC, the Pragmatic M Standard, and the Operational Subset

Three M standards layer over each other for VistA development. They
optimise for different things and produce different — increasingly
restrictive — sets.

| Standard | Question it answers | Optimises for | Source | Size in v0.2 |
| --- | --- | --- | --- | ---: |
| **Pragmatic** | Will this run on both engines? | Portability (YDB ∩ IRIS) | Mechanical join over per-source documentation | **81 entries** |
| **VA SAC** | Should we write this in VistA? | Security, code quality, decades of maintenance | Hand-curated by VA M Programming Standards Committee; encoded in XINDEX | 65 rules / 171 per-name flags |
| **Operational** | What can a VistA developer actually use? | Portability **AND** policy-compliance | Intersection: pragmatic-core ∧ SAC-clean | **58 entries** |

The pragmatic standard is **strictly more permissive than
operational** — it lets in 23 portable entries that SAC blocks for
non-portability reasons (BREAK, HALT, JOB, VIEW, ZWRITE,
$ZHOROLOG, $ZTRAP, ...). The operational subset is what a VistA
developer can actually write that runs unmodified on both engines
AND passes XINDEX.

> **Common mis-reading.** "Pragmatic" doesn't mean "the wise
> default." It means *portable*. SAC isn't impractical — it's
> optimising for a different (equally legitimate) definition of
> practical: long-term system maintainability over short-term
> feature use. The operational standard is the answer to "wise AND
> portable" — pick that one for new VistA code unless you have a
> reason not to.

## What the layers look like

```
   ANSI 1995 (in_anno)  ──┐
                          ├── pragmatic-core (in_ydb && in_iris)  81
   YDB (in_ydb)         ──┤    │
                          │    └── ∩ SAC-clean      = operational  58
   IRIS (in_iris)       ──┘    └── ∩ SAC-blocked   = ban list     23
                                    (BREAK, HALT, JOB, VIEW,
                                     ZWRITE, $ZHOROLOG, ...)
```

## The operational standard

[`integrated/operational-m-standard.tsv`](../integrated/operational-m-standard.tsv)
holds the **58 entries** that satisfy both standards: portable
across YDB and IRIS, and not blocked by SAC. Auto-derived by
[`m_standard.tools.emit_operational_standard`](../src/m_standard/tools/emit_operational_standard.py)
from the pragmatic standard ∩ SAC compliance. By concept:

- 21 commands (CLOSE, DO, ELSE, FOR, GOTO, HANG, IF, KILL, LOCK,
  MERGE, NEW, OPEN, QUIT, READ, SET, TCOMMIT, TROLLBACK, TSTART,
  USE, WRITE, XECUTE)
- 21 intrinsic functions ($ASCII, $CHAR, $DATA, $EXTRACT, ...)
- 16 intrinsic special variables ($DEVICE, $ECODE, $ESTACK,
  $ETRAP, $HOROLOG, $IO, $JOB, ...)

For VistA development, **start from the operational standard**.
A routine written entirely from the operational subset:

- runs unmodified on YDB and IRIS, and
- passes XINDEX SAC validation, and
- doesn't depend on the 23 entries that are portable but
  policy-blocked (BREAK, HALT, JOB, VIEW, ZWRITE, $ZHOROLOG,
  $ZTRAP, ...).

The smallness (58 of M's full lexical surface) is the cost of
critical-system development on heterogeneous engines.

For the pattern-level SAC rules — READ-without-timeout,
LOCK-without-timeout, exclusive Kill, exclusive NEW, lowercase
commands, line-too-long — see the lint_m tool below.

## How the SAC compliance join works

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

## The pattern-rule linter

The va-sac.tsv overlay handles **per-name** rules — XINDEX rule 25
"BREAK command used", rule 31 "Non-standard $Z function used", etc.
The other ~57 XINDEX rules are **pattern rules** — they detect how
a token is *used*, not just whether the name appears. Examples:

- Rule 22: `KILL (X,Y)` — exclusive Kill (forbidden)
- Rule 23: `KILL` with no argument (forbidden)
- Rule 26: `NEW (X,Y)` or unargumented `NEW` (forbidden)
- Rule 33: `READ X` without a `:T` timeout (forbidden)
- Rule 47: lowercase commands (`write` instead of `WRITE`) (forbidden)
- Rule 60: `LOCK` without timeout (forbidden)

These need to look at usage context, not just names. The
[`m_standard.tools.lint_m`](../src/m_standard/tools/lint_m.py)
tool implements regex-based detectors for the most common pattern
rules. Run on M source files:

```bash
.venv/bin/python -m m_standard.tools.lint_m routine.m

# Or filter to specific severity:
.venv/bin/python -m m_standard.tools.lint_m --severity FS routine.m

# Or write findings to TSV:
.venv/bin/python -m m_standard.tools.lint_m --out findings.tsv routine.m
```

Output format: file:line:column with severity-prefixed rule number
and message. Exit code is non-zero if any F/S findings exist (so
the linter can gate CI for VistA-targeting projects).

**Coverage in v0.2:** rules 13, 19, 22, 23, 26, 33, 47, 60. The
linter is regex-based, not a real M parser — it'll miss subtle
patterns (matched parens across line breaks, indirection
resolution, comments inside strings) and will false-positive on
some edge cases. Treat findings as advisory.

For full M parsing, the right tool is [tree-sitter-m](../README.md)
(consumes the grammar surface). lint_m bridges the gap between
"data we have" and "tooling that exists today."

## Future work

- Add an "M-language linter" downstream tool that consumes
  `va-sac-compliance.json` and `integrated/va-sac-rules.tsv`
  to flag violations in actual VistA routine source. **Done in
  v0.2** as `m_standard.tools.lint_m` for 8 of the most common
  pattern rules.
- Extend the per-name overlay to operators and pattern codes once
  SAC's treatment of those is incorporated.
- Add a per-namespace exemption layer so the overlay can model
  XINDEX's exempt-namespace lists (X, Z, DI, DD, KMP — kernel
  internals that are exempt from many rules).
- Severity-tier filtering on the compliance output so consumers
  can ask "show me only F+S violations" vs "include W+I".

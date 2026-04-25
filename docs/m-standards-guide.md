# M-Standards-Guide

A human-readable reference to the M (MUMPS) programming language, drawn
from the integrated layer of [`m-standard`](../README.md). Every claim
in this guide cites a row in [`integrated/`](../integrated/) or
[`integrated/conflicts.tsv`](../integrated/conflicts.tsv); the prose
adds context, the data carries authority.

This document is a **reference**, not a tutorial. If you want to learn
M, read AnnoStd's introduction or YottaDB's *Acculturation Guide*.

## Conventions used in this guide

| Symbol | Meaning |
| --- | --- |
| `ansi` | The entry is part of the 1995 ANSI X11.1 standard, per AnnoStd. |
| `ydb-extension` | The entry is in YottaDB but not in AnnoStd. |
| `in_anno=true` | AnnoStd documents this entry (Edition 1995). |
| `in_ydb=true` | The YottaDB documentation corpus documents this entry. |
| `CONF-NNN` | A reconciliation conflict; full row in `conflicts.tsv`. |

The hierarchy that resolves disagreements is fixed: AnnoStd is normative
for "is X part of the standard"; YottaDB is authoritative for current
implementation detail. See [`docs/adr/001-two-source-hierarchy.md`](adr/001-two-source-hierarchy.md).

---

## 1. Commands

M's command set is small and fixed. The 1995 ANSI standard catalogues
about 25 commands (BREAK, CLOSE, DO, ELSE, FOR, GOTO, HALT, HANG, IF,
JOB, KILL, LOCK, MERGE, NEW, OPEN, QUIT, READ, SET, TCOMMIT, TRESTART,
TROLLBACK, TSTART, USE, VIEW, WRITE, XECUTE). YottaDB implements all of
these and adds the `Z*` extension family for engine-specific
operations. AnnoStd additionally documents a handful of commands from
sibling standards (Async I/O, events, routine load/save) which YottaDB
does not implement.

**Coverage:** [`integrated/commands.tsv`](../integrated/commands.tsv)
holds 64 commands.

| Subset | Count | Source signature |
| --- | --- | --- |
| In both AnnoStd and YDB (the working ANSI core) | 26 | `in_anno=true, in_ydb=true, standard_status=ansi` |
| AnnoStd-only (in standard, not in YDB) | 14 | `in_anno=true, in_ydb=false, standard_status=ansi`, conflict kind `existence` |
| YDB-only (vendor extensions) | 24 | `in_anno=false, in_ydb=true, standard_status=ydb-extension` |

**Where the sources disagree.** Of the 14 AnnoStd-only commands, the
common pattern is "ANSI standard but unimplemented by YottaDB" — every
row carries an `existence` conflict in `conflicts.tsv`. The most
notable groups:

- **Async I/O commands** (ABLOCK, ASSIGN, ASTART, ASTOP, AUNBLOCK).
  Documented in chapter 8.2 of the 1995 standard; not in modern YDB.
- **Event commands** (ESTART, ESTOP, ETRIGGER). Originally part of the
  1995 standard's event handling; YottaDB uses `$ETRAP` / `$ECODE`
  for error processing instead.
- **Routine I/O commands** (RLOAD, RSAVE) and KILL options
  (KSUBSCRIPTS, KVALUE) — features that were specified but not widely
  adopted.
- **THEN, Z** — corner cases of the 1995 grammar.

**Format strings.** `format` on each integrated row carries the
verbatim format string from the chosen authoritative source, in that
source's metalanguage. AnnoStd writes `B[REAK] postcond [ SP ]` while
YottaDB writes `B[REAK][:tvexpr] [expr[:tvexpr][,...]]`; both
describe the same syntax. v1.0 of `m-standard` does not normalise
between metalanguages — the format field is informational, not a
parse target. Use `abbreviation` (e.g. `B`) and `canonical_name`
(e.g. `BREAK`) for code generation.

---

## 2. Intrinsic functions

Functions in M are prefixed with `$`. The 1995 ANSI standard defines
about 22 intrinsic functions (`$ASCII`, `$CHAR`, `$DATA`, `$EXTRACT`,
`$FIND`, `$FNUMBER`, `$GET`, `$JUSTIFY`, `$LENGTH`, `$NAME`, `$NEXT`,
`$ORDER`, `$PIECE`, `$QLENGTH`, `$QSUBSCRIPT`, `$QUERY`, `$RANDOM`,
`$REVERSE`, `$SELECT`, `$STACK`, `$TEXT`, `$TRANSLATE`, `$VIEW`).
YottaDB adds `$INCREMENT` and a large `$Z*` family.

**Coverage:** [`integrated/intrinsic-functions.tsv`](../integrated/intrinsic-functions.tsv)
holds 66 functions.

| Subset | Count |
| --- | --- |
| In both | 22 |
| AnnoStd-only | 6 |
| YDB-only (mostly `$Z*`) | 38 |

**The 6 AnnoStd-only functions** are largely post-1995 MDC drafts that
AnnoStd records (e.g. `$DEXTRACT`, `$DPIECE`, `$MUMPS`) which
YottaDB never adopted. They appear with `existence` conflicts in
`conflicts.tsv`.

**Where to find what:** [`integrated/intrinsic-functions.json`](../integrated/intrinsic-functions.json)
is the typed surface for code generation; the JSON object's
`canonical_name` is the function name including the leading `$`.

---

## 3. Intrinsic special variables

Special variables (svns) are also `$`-prefixed but unlike functions they
take no arguments. The 1995 standard defines 21 svns including
`$DEVICE`, `$ECODE`, `$ESTACK`, `$ETRAP`, `$HOROLOG`, `$IO`, `$JOB`,
`$KEY`, `$PRINCIPAL`, `$QUIT`, `$REFERENCE`, `$STACK`, `$STORAGE`,
`$SYSTEM`, `$TEST`, `$TLEVEL`, `$TRESTART`, `$X`, `$Y`, plus the `$Z*`
prefix reserved for vendor extensions. YottaDB makes heavy use of that
prefix.

**Coverage:** [`integrated/intrinsic-special-variables.tsv`](../integrated/intrinsic-special-variables.tsv)
holds 66 svns.

| Subset | Count |
| --- | --- |
| In both | 16 |
| AnnoStd-only | 1 |
| YDB-only (`$Z*` and a few late additions) | 49 |

The single AnnoStd-only svn is a 1995-edition entry that YottaDB
either renamed or merged into another svn; see its
`conflict_id` row in `conflicts.tsv` for the resolution basis.

**A note on extraction quality.** AnnoStd renders svns differently
from functions: each svn page repeats the same overview heading
("Intrinsic special variable names") and embeds the syntax in a
two-column "Syntax / Definition" table rather than a free-form
paragraph. The extractor handles both shapes, but `format` for an
svn is just the abbreviation form (`$D[EVICE]`); there are no
parameters to record.

---

## 4. Operators

M operators fall into four classes (five if you count AnnoStd's
separate `string` class for concatenation). v1.0 reconciles 17
operator entries across both sources; 15 are present in both, 1 is
YDB-only (the unary NOT `'`, which AnnoStd happens to document under
`!` and `&` rather than as a standalone operator), and 1 is
AnnoStd-only (the underscore `_` concatenation operator, which YDB
catalogues under string-relational rather than as its own class —
recorded as conflict CONF-022).

**Coverage:** [`integrated/operators.tsv`](../integrated/operators.tsv)
holds 17 operator entries.

| Class | Operators | Notes |
| --- | --- | --- |
| Arithmetic | `+`  `-`  `*`  `**`  `/`  `\`  `#` | `**` is exponentiation; `\` is integer division; `#` is modulo. |
| Logical | `'`  `&`  `!` | Unary NOT; binary AND; binary OR (`!`). |
| Numeric relational | `<`  `>` | Equality is in the string-relational class. |
| String relational | `=`  `[`  `]`  `]]` | `[` is "contains"; `]` is "lexically follows"; `]]` is "subscript-collation follows". |

**M's no-precedence rule.** M evaluates expressions strictly
left-to-right with no operator precedence. Use parentheses to override
the order. This rule applies uniformly across all four operator
classes — there is no "arithmetic before logical" hierarchy as in C.

---

## 5. Pattern codes

Pattern codes are single-letter character classes used by the `?`
pattern-match operator. The 1995 ANSI standard defines seven:

| Code | Match |
| --- | --- |
| `A` | Alphabetic characters (upper or lower case). |
| `C` | Control characters (ASCII 0–31 and 127). |
| `E` | Any character. |
| `L` | Lower-case alphabetic characters (ASCII 97–122). |
| `N` | Digits 0–9 (ASCII 48–57). |
| `P` | Punctuation (ASCII 32–47, 58–64, 91–96, 123–126). |
| `U` | Upper-case alphabetic characters (ASCII 65–90). |

**Coverage:** [`integrated/pattern-codes.tsv`](../integrated/pattern-codes.tsv)
holds all seven, all `standard_status=ansi`. YottaDB allows the
underlying patcode definitions for `A`, `C`, `N`, `U`, `L`, `P` to be
extended at run time (see YottaDB's *Internationalization* chapter)
and accepts user-defined codes via the patcode table; v1.0 does not
catalogue user-defined extensions.

As with operators, AnnoStd's BNF rendering of pattern codes is
deferred to v0.2.

---

## 6. Errors

`integrated/errors.tsv` holds 1713 error entries from two disjoint
namespaces:

- **AnnoStd Annex B M-codes** (112 entries, `M1`–`M112`).
  `standard_status=ansi`, sourced from `pages/ab*.html`. The 1995
  ANSI standard catalogues codes M1–M75; codes above that are
  post-1995 MDC drafts that AnnoStd preserves.
- **YottaDB vendor mnemonics** (1601 entries). Uppercase
  alphanumeric tokens grouped loosely by subsystem
  (`ABNCOMPTINC`, `ZPRINTECVIO`, etc.), all flagged
  `ydb-extension`.

The two namespaces don't overlap — there's no mapping between
"M9 divide by zero" and YDB's `DIVZERO` (the symbolic name).
The integrated table records both verbatim so downstream tools can
choose which they care about.

The integrated table is most useful as an enumeration source for
linters and tooling that needs to recognise error names; the actual
human-readable explanation lives in the source file linked from
`anno_section` (for M-codes) or `ydb_section` (for vendor mnemonics).

---

## 7. Environment

Per spec §5.7, environment is the most heterogeneous concept family
— process model, lock semantics, transaction semantics, device I/O
parameters, namespace and routine resolution. Most of those slots
are populated by entries already catalogued elsewhere:

| Aspect | Where it lives |
| --- | --- |
| Lock semantics | LOCK in `commands.tsv` |
| Transaction semantics | TSTART, TCOMMIT, TROLLBACK, TRESTART in `commands.tsv` |
| Error handling | `$ETRAP`, `$ECODE`, `$ESTACK`, `$STACK` in `intrinsic-special-variables.tsv` |
| Device I/O parameters | `environment.tsv` (this section) |

**`integrated/environment.tsv` holds 74 device I/O parameters** —
the keyword arguments to OPEN/USE/CLOSE that control device state.
All sourced from YottaDB's `ProgrammersGuide/ioproc.rst`; AnnoStd's
device-parameter chapters are in BNF-railroad form and not
extracted in v1.0.

Examples: `APPEND`, `ATTACH`, `CANONICAL`, `CHSET`, `CONNECT`,
`CTRAP`, `DELIMITER`, `ECHO`, `EDITING`, `FIXED`, `RECORDSIZE`,
`STREAM`, `TYPEAHEAD`, `WIDTH`, `WRAP`, plus YottaDB-specific
`ZBFSIZE`, `ZDELAY`, `ZFF`, `ZIBFSIZE` (`Z*` prefix marked
`ydb-extension`). The full list lives in
[`integrated/environment.tsv`](../integrated/environment.tsv).

---

## 8. Reading the conflicts table

[`integrated/conflicts.tsv`](../integrated/conflicts.tsv) lists
every non-trivial reconciliation between the two sources. v1.0
contains 21 conflicts, all of kind `existence` — entries present in
AnnoStd but absent from YottaDB. There are zero `definition`
conflicts: every entry that exists in both sources agrees on
abbreviation and canonical name.

The `resolution_basis` column cites the AD that justified the
resolution; almost all v1.0 conflicts cite AD-01 because the only
disagreements are about presence in the standard, which AD-01
resolves by deferring to AnnoStd.

**Format-string differences are not conflicts.** AnnoStd's
metalanguage (`postcond`, `SP`) and YottaDB's (`[:tvexpr]`) describe
the same constructs in incompatible notations. v1.0 of the
reconciler does not flag these as conflicts because semantic
normalisation between the two metalanguages is out of scope. The
verbatim format from each source is preserved on the integrated
row's `format` field plus its `*_section` cross-references.

---

## 9. Citations

Every claim in this guide is a query against the integrated layer.
The data is the authority; the prose is convenience.

- For a concept family's flat facts, query the corresponding TSV
  (`commands.tsv`, `intrinsic-functions.tsv`, etc.) with `cut`,
  `awk`, `duckdb`, `pandas`, or any other rectangular-data tool.
- For typed code-generation surfaces, read the corresponding JSON
  (`commands.json`, etc.). Each JSON file pins
  `schema_version: "1"`; per ADR-005 breaking changes bump that
  version.
- For per-source isolation, read `per-source/anno/<concept>.tsv` or
  `per-source/ydb/<concept>.tsv`.
- For raw upstream context, follow `anno_section` (a
  `pages/aXXXXXX.html#section` reference into the local AnnoStd
  mirror) or `ydb_section` (a `<file>#<heading>` reference into the
  vendored YottaDB docs repo).

# Changelog

All notable changes to `m-standard` are recorded here.

The project follows two parallel version axes (per ADR-005):

- **Project version** (this file's headings): the m-standard release as a whole.
- **Schema version** (`schema_version` field in every `integrated/*.json`):
  the on-disk JSON contract that downstream consumers pin against. Bumped
  only on breaking changes — column removed/renamed/retyped, required
  field added, enum value removed.

Breaking schema changes are flagged with **[breaking]** in entries.

## [1.0.0] — 2026-04-25

First tagged release. Pipeline runs end-to-end (`make all`):
`sources/` → `per-source/` → `integrated/` (TSV + JSON) → CI validation.
All seven concept families from spec §5 produce an integrated table.

### Schema

- `schema_version: "1"` introduced and pinned for all integrated JSON files.

### Coverage

| Concept | YDB rows | AnnoStd rows | Both | Notes |
| --- | --- | --- | --- | --- |
| commands | 50 | 40 | 26 | |
| intrinsic-functions | 60 | 28 | 22 | |
| intrinsic-special-variables | 65 | 17 | 16 | |
| operators | 16 | 16 | 15 | Underscore (concatenation) is in AnnoStd's `string` class but YDB has no string class — recorded as conflict CONF-022. |
| pattern-codes | 7 | 0 | — | AnnoStd's patcode letters are in `Edition=examples` only, not 1995 main grammar (BL-010). |
| errors | 1601 | 112 | 0 | AnnoStd Annex B (M1–M112) and YDB vendor mnemonics use disjoint namespaces; integrated table is the union. |
| environment | 74 | 0 | — | Device I/O parameters from YDB ioproc.rst (BL-011). AnnoStd's BNF-form device chapters deferred. |

### Conflicts

22 reconciliation conflicts:
- 21 `kind=existence` (entries in AnnoStd's 1995 standard but not
  implemented by YottaDB — async I/O, events, RLOAD/RSAVE, etc.).
- 1 `kind=existence` for the underscore operator's class divergence
  between AnnoStd and YDB (CONF-022).

0 `kind=definition` conflicts.

### Source pins

- AnnoStd: `http://71.174.62.16/Demo/AnnoStd`, Edition 1995, crawled
  2026-04-25 (1399-file mirror under `sources/anno/site/`, gitignored
  pending licence verification — repopulate via `bash sources/anno/fetch.sh`).
- YottaDB documentation: `https://gitlab.com/YottaDB/DB/YDBDoc.git` at
  commit `25a97c4c8405bcccc85e7a4eadc4f91bd07b6de9` (2026-04-21,
  "[#470] Correct and update $ZYRELEASE documentation"). Vendored under
  `sources/ydb/repo/` (51 MB, GFDL-1.3).

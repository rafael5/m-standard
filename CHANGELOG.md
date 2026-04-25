# Changelog

All notable changes to `m-standard` are recorded here.

The project follows two parallel version axes (per ADR-005):

- **Project version** (this file's headings): the m-standard release as a whole.
- **Schema version** (`schema_version` field in every `integrated/*.json`):
  the on-disk JSON contract that downstream consumers pin against. Bumped
  only on breaking changes — column removed/renamed/retyped, required
  field added, enum value removed.

Breaking schema changes are flagged with **[breaking]** in entries.

## [Unreleased]

Initial public draft. Pipeline runs end-to-end (`make all`):
`sources/` → `per-source/` → `integrated/` (TSV + JSON) → CI validation.

### Schema

- `schema_version: "1"` introduced and pinned for all integrated JSON files.

### Coverage

| Concept | YDB rows | AnnoStd rows | Both | Notes |
| --- | --- | --- | --- | --- |
| commands | 50 | 40 | 26 | |
| intrinsic-functions | 60 | 28 | 22 | |
| intrinsic-special-variables | 65 | 17 | 16 | |
| operators | 16 | — | — | AnnoStd BNF deferred (BL-009) |
| pattern-codes | 7 | — | — | AnnoStd BNF deferred (BL-009) |
| errors | 1601 | — | — | ANSI M1–M75 in AnnoStd deferred (BL-009) |
| environment | — | — | — | Not extracted in v1.0 (BL-009) |

### Conflicts

21 reconciliation conflicts, all `kind=existence` (entries in AnnoStd's
1995 standard but not implemented by YottaDB). 0 `definition` conflicts.

### Source pins

- AnnoStd: `http://71.174.62.16/Demo/AnnoStd`, Edition 1995, crawled
  2026-04-25 (1399-file mirror under `sources/anno/site/`, gitignored
  pending licence verification — repopulate via `bash sources/anno/fetch.sh`).
- YottaDB documentation: `https://gitlab.com/YottaDB/DB/YDBDoc.git` at
  commit `25a97c4c8405bcccc85e7a4eadc4f91bd07b6de9` (2026-04-21,
  "[#470] Correct and update $ZYRELEASE documentation"). Vendored under
  `sources/ydb/repo/` (51 MB, GFDL-1.3).

# mappings/

Hand-curated cross-reference tables that aren't naturally derivable
from any single source's documentation. These tables enrich the
integrated layer at reconcile-time.

## Files

### `ydb-ansi-errors.tsv`

YottaDB error mnemonics → ANSI X11.1 error condition codes
(`M1`–`M75`+). The mapping enables portability tooling — code that
catches `$ECODE["DIVZERO"]` is YDB-specific; the equivalent
`$ECODE[",M9,"]` runs anywhere that implements the standard.

**Columns:**

| Column | Meaning |
| --- | --- |
| `ydb_mnemonic` | The YottaDB error mnemonic (e.g. `DIVZERO`). Must exist in `per-source/ydb/errors.tsv`. |
| `ansi_code` | The ANSI X11.1 error condition code (e.g. `M9`). Must exist in `per-source/anno/errors.tsv`. |
| `confidence` | One of `high` (description match + corroborating evidence), `medium` (description match alone), `low` (partial overlap; pending review). |
| `basis` | Free text citing the evidence for the mapping (description-text match, errproc.rst example pair, etc.). |

**Sources used to curate the mapping (v1.0):**

- AnnoStd Annex B descriptions for `M1`–`M75` and the post-1995
  draft codes `M76`–`M112` (in `per-source/anno/errors.tsv`).
- YDB `MessageRecovery/errors.rst` per-mnemonic descriptions
  (in `per-source/ydb/errors.tsv`).
- YDB `ProgrammersGuide/errproc.rst` worked examples that show
  `$ECODE` populated with both forms simultaneously,
  e.g. `,M6,Z150373850,` (M6 is the abstract code, Z… is the
  YDB-specific instance ID). These pairs are the strongest
  evidence — they're what the YDB runtime actually emits.

**Coverage and limits.** The v1.0 mapping is a starter, not
exhaustive. Of YottaDB's ~1601 mnemonics, only the small subset
that has a clean ANSI analogue is mapped (~25 high-confidence
entries; many more `medium`/`low` candidates pending verification).
The bulk of YDB's mnemonics are vendor extensions (device
subsystem, transaction internals, journaling, network, etc.) with
no ANSI equivalent and are correctly recorded as
`standard_status=ydb-extension` with no `ansi_code`.

**Validation.** The validation harness's mapping-integrity gate
checks that every `ydb_mnemonic` in this file exists in
`per-source/ydb/errors.tsv` and every `ansi_code` exists in
`per-source/anno/errors.tsv`. CI fails if a mapping references a
non-existent identifier (e.g. due to a YDB upgrade renaming a
mnemonic).

**How the mapping is consumed.** `reconcile.py` joins this file
into `integrated/errors.tsv`, adding an `ansi_code` column. Where
a YDB mnemonic has no ANSI analogue the column is empty.
Downstream tooling can then ask: "what's the portable form of
`DIVZERO`?" → `M9`.

## Adding new mappings

1. Verify both endpoints exist in the per-source TSVs:
   - `cut -f1 per-source/ydb/errors.tsv | grep -F MNEMONIC`
   - `cut -f1 per-source/anno/errors.tsv | grep -F Mxx`
2. Append a row with the cited basis. Mark `confidence=high` only
   when there's corroborating evidence beyond description matching
   (e.g. an errproc.rst worked example or a published mapping).
3. Run `make validate` — the mapping-integrity gate must pass.
4. Run `make reconcile` to regenerate `integrated/errors.tsv` with
   the new `ansi_code` cell populated.

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

## v0.2 seed contents and provenance

The current `mappings/va-sac.tsv` is a **v0.1 seed**, not the
authoritative SAC content. It contains a small set of widely-cited
SAC rules from public knowledge of VistA programming standards:

- `BREAK`, `ZINSERT`, `ZLOAD`, `ZSAVE`, `ZREMOVE` — debug commands
  conventionally forbidden in production code.
- `XECUTE`, `JOB`, `ZSYSTEM` — restricted/forbidden for security
  and concurrency reasons.
- `$ZA`, `$ZB`, `$ZIO` — vendor-specific I/O state ISVs that SAC
  conventionally forbids in favour of `$DEVICE` etc.
- `$ZSEARCH` — direct filesystem access SAC restricts in favour of
  FileMan APIs.

**These entries should be reviewed against the authoritative
SAC document.** The `sac_section` column for the seed entries
points at section ranges (e.g. "SAC §2.x") rather than specific
section numbers because the precise numbering varies by SAC
revision.

## How to populate from the authoritative SAC

The official SAC document is published by the VA M Programming
Standards Committee. It's available through OSEHRA / the VA's open
documentation channels. To populate this overlay:

1. Open the authoritative SAC PDF/HTML.
2. Find the "Allowed M Language Subset" section (varies by
   revision).
3. For each command/function/ISV mentioned, add a row to
   `mappings/va-sac.tsv` with the correct `sac_status` and
   `sac_section` (precise reference).
4. Run `make emit-sac` and review `integrated/va-sac-compliance.tsv`
   for portability concerns.
5. The `mapping-integrity` validation gate will fail if any
   `name` in the SAC overlay doesn't exist in the corresponding
   per-source TSV — useful for catching SAC references to
   commands that vendors removed.

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

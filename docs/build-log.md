# Build log

Chronological record of non-trivial issues encountered during
construction of `m-standard`. Entries follow the vista-meta `BL-NNN`
convention: short title, what we were doing, what went wrong (or what
required a non-obvious decision), how it was resolved.

Trivial fixes (typos, obvious renames, routine dependency bumps) do
not get an entry — they belong in commit messages, not here.

---

## BL-001 — Project bootstrapped from python template (2026-04-25)

**Phase:** A0 — repo skeleton.
**Context:** Copied `~/claude/templates/python` into the existing
`m-standard/` (which already held LICENSE and the spec draft), renamed
the package to `m_standard`, and rewrote the Makefile to use
`.venv/bin/` prefixes for every tool invocation.

**Why the Makefile rewrite:** the upstream template uses bare tool
names (`pytest`, `ruff`, `mypy`, `pre-commit`) which are hijacked by
the parent direnv's `VIRTUAL_ENV=/home/rafael/claude/.venv` and run
against the wrong packages. This is a known upstream-template bug
(captured in `~/claude/memory/feedback_python_template_bug.md`); fixed
locally on bootstrap.

**Outcome:** `make install` and `make test` run against this
project's `.venv/` as intended. No further action required for this
project; upstream template fix is tracked separately.

---

## BL-002 — AnnoStd is a JS app, not a static HTML tree (2026-04-25)

**Phase:** A0 — source acquisition.
**Context:** First run of `m_standard.tools.crawl_anno` against
`http://71.174.62.16/Demo/AnnoStd` returned a single file (the index)
and zero followed links. The spec described AnnoStd as "a static HTML
tree" — that turned out to be wrong.

**What it actually is:** A JavaScript single-page app. The index page
embeds a menu of ~452 page IDs, each surfaced as
`onclick="GetText('ShowPage', '<id>', '', '');"`. The JS function
`GetText()` issues `GET <base>/?Action=ShowPage&Edition=<edition>&Page=<id>`
and replaces the page body with the response. There are no per-page
HTML files to follow via plain `href`s.

**Fix:** Extended the crawler's link extractor to also parse
`onclick="GetText(...)"` calls and synthesise the equivalent dynamic
URL. Added URL canonicalisation so the seen-set correctly dedupes
query-string variants, and a path mapping that lands dynamic responses
under deterministic local names:
- `?Action=ShowPage&Page=a100001` → `pages/a100001.html`
- `?Action=ShowLiterature` → `literature.html`
- `?Action=ShowImplementation` → `implementation.html`
- `?Action=ShowQuickJump` → `quickjump.html`

Edition is configurable via `--edition` (default `1995`, the ANSI
X11.1-1995 standard pinned by the spec). The site also supports 1977,
1984, 1990, MDC, and `notes` editions; `notes` mode would be the source
to grow into for AD-02 (normative-vs-annotation separation), but is out
of scope for v1.0.

**License observation:** The standard text is © MUMPS Development
Committee, the annotations © Jacquard Systems Research / Ed de Moel.
The site states no explicit redistribution licence. The crawled mirror
is therefore *not* committed (kept gitignored; rebuild via
`bash sources/anno/fetch.sh`); only the manifest is tracked. The
analysis pipeline reads the local mirror regardless.

---

## BL-003 — Wrong YottaDB docs repo path in clone-ydb.sh (2026-04-25)

**Phase:** A0 — source acquisition.
**Context:** Initial `clone-ydb.sh` defaulted to
`https://gitlab.com/YottaDB/DOC/YDBDoc.git`, which doesn't exist —
GitLab returns a redirect-to-login that `git clone` reads as an auth
prompt. The repo is actually under the `YottaDB/DB/` subgroup
(alongside `YDB`, the database itself).

**Fix:** Updated default `UPSTREAM` in `tools/clone-ydb.sh` to
`https://gitlab.com/YottaDB/DB/YDBDoc.git`. Verified via the GitLab
public API (`/api/v4/groups/YottaDB%2FDB/projects`). HEAD at
`25a97c4c8405bcccc85e7a4eadc4f91bd07b6de9` (2026-04-21) is the pinned
commit for v1.0; `sources/ydb/manifest.tsv` records the SHA per row.

**License:** GNU Free Documentation License v1.3, no Invariant Sections,
no Cover Texts. Redistribution is permitted, so the cloned working tree
is committed under `sources/ydb/repo/`; only the embedded `.git/` is
gitignored (so the outer git repo is not confused by a nested git tree).

---

## BL-004 — Vendoring decision: strip inner .git/ before commit (2026-04-25)

**Phase:** A0 — source acquisition.
**Context:** When `git add sources/ydb/repo/` was run with the inner
`.git/` directory present, git treated the path as a gitlink (embedded
git repo) and would have stored only a pointer rather than the actual
files — losing the "self-contained offline replica" property the user
called out as the analysis foundation.

**Options considered:**
1. *Submodule* — spec-aligned ("`.git/` retained"), but requires
   `git submodule update --init` after every fresh clone of m-standard
   and still needs gitlab.com to be reachable then. Defeats the
   self-contained replica goal.
2. *Subtree* — vendors the bulk into m-standard's history, but adds
   tooling complexity for a hobbyist project.
3. *Strip `.git/` and commit working tree as plain files* — bulk lives
   in m-standard's history; pinned commit SHA is preserved per-row in
   `sources/ydb/manifest.tsv` so reproducibility is unchanged.

**Decision:** option 3. `tools/clone-ydb.sh` was updated to detect the
post-vendor state (no `.git/` in `repo/`) and, on update, clone fresh
into a temp directory at the new pin and `rsync --delete --exclude=.git`
the result onto `sources/ydb/repo/`. Spec §4.2 and AD-03 narrative were
updated to match. Trade-off accepted: `git pull` inside `repo/` no
longer works, but updates are an explicit `make sources-ydb` run with
a new `PIN_COMMIT`, which is more deliberate anyway.

**Size:** stripped working tree is 51 MB (vs 96 MB with `.git/`); 267 files.

---

## BL-005 — YDB commands extractor: format-intro string isn't uniform (2026-04-25)

**Phase:** A1 — per-source extraction.
**Context:** First pass of `extract_ydb.commands` got 44 of 50 command
sections in `ProgrammersGuide/commands.rst`. The 6 misses came from
real-world inconsistencies in the upstream prose:
- `MERGE`, `ZRUPDATE`, `ZYDECODE`, `ZYENCODE`: "The format of X command is:" (missing "the")
- `TRESTART`: "The format **for** the TRESTART command is:" (uses "for" not "of")
- `ZRUPDATE`, `ZTRIGGER`: format intro appears mid-paragraph, not at start of line

**Fix:** Loosened `_FORMAT_INTRO` to `r"The format (?:of|for) (?:the )?\S+ command is\s*:"`
and switched from `re.match` to `re.search`. The pattern is still anchored on
`command is:` so it can't false-match "the format of a YottaDB name" etc. that
appears in body prose. After the fix all 50 commands extracted.

---

## BL-006 — AnnoStd: section numbers reset per letter group (2026-04-25)

**Phase:** A1 — per-source extraction.
**Context:** When extracting AnnoStd commands, the same section number
(e.g. `8.2.10`) appears for multiple commands — `JOB` is "8.2.10" and
`ESTART` is also "8.2.10". This is a real organisational quirk of
AnnoStd, not an extraction bug: the section numbering resets within
the alphabetical groups of section 8.2 (Async commands `A*` get their
own 1..5 sequence; Event commands `E*` get 10..12; standard commands
get their own 1..N).

**Implication:** AnnoStd's section numbers are **not** unique
identifiers. `source_section` in the per-source TSV combines page ID +
section (`pages/a108036.html#8.2.10`) so the row key remains
unambiguous, but downstream consumers must not treat
`section_number` alone as a primary key for AnnoStd entries.

**Filter applied:** restricted page scan to `a*.html` (the language
standard pages) and section prefix `8.2.` (per-command definitions,
skipping 8.1 "general rules"). MWAPI commands from `f*.html` pages are
out of scope per spec §2 (deferred to v0.2).

---

## BL-007 — AnnoStd command pages: format style varies (BNF vs inline) (2026-04-25)

**Phase:** A1 — per-source extraction.
**Context:** Simple commands like BREAK render their syntax as an
inline first-row table cell `B[REAK] postcond …`, from which the
extractor recovers both the abbreviation (`B`) and the format string.
Complex commands like CLOSE render the syntax as a multi-table
railroad diagram in BNF (`closeargument ::= expr [ : deviceparameters ] | …`),
with no `C[LOSE]` form on the page. This means `abbreviation` is
empty for BNF-style commands in the AnnoStd per-source TSV.

**Decision:** Per AD-01, AnnoStd is normative for "is X part of the
standard"; YDB is authoritative for current implementation detail
including abbreviations. Empty `abbreviation` cells in
`per-source/anno/commands.tsv` are expected and will be filled by
joining against `per-source/ydb/commands.tsv` during A2 reconciliation.

---

## BL-008 — Some YDB function/ISV sections skip the format-intro sentence (2026-04-25)

**Phase:** A1 — per-source extraction.
**Context:** A handful of YDB function pages (`$ZYISSQLNULL`,
`$ZYSUFFIX`) and ISV pages (`$ZPIN`, `$ZPOUT`, `$ZYRELEASE`,
`$ZYSQLNULL`) skip the "The format … is:" sentence and jump straight
into the syntax block. The first-pass extractor missed these.

**Fix:** Added a fallback to `_find_format` — if no format-intro
sentence is present in the section, take the first ``.. code-block::``
whose content line looks like a format string (begins with ``$`` or
with an uppercase letter followed by ``[``). For ISVs specifically,
the format token is the leading ``$X[YYY]`` of the first description
paragraph; entries that genuinely don't follow that pattern are logged
and skipped (4 ISVs as of `25a97c4c`).

---

## BL-009 — A1 concept-family coverage matrix (2026-04-25)

**Phase:** A1 — per-source extraction.
**Context:** A1's exit criterion in the spec is "all seven concept
families extracted from both sources where present." Coverage as of
this commit:

| Concept                  | YDB extractor | YDB rows | AnnoStd extractor | AnnoStd rows | Notes |
|--------------------------|---------------|----------|--------------------|--------------|-------|
| Commands                 | ✓             | 50       | ✓                  | 40           | |
| Intrinsic functions      | ✓             | 60       | ✓                  | 28           | |
| Intrinsic special vars   | ✓             | 65       | ✓                  | 17           | |
| Operators                | ✓             | 16       | deferred           | 0            | AnnoStd renders operators as BNF railroad diagrams (chapters 7.2.1, 7.2.2) which need bespoke extraction; YDB has 4 clean RST grid tables. |
| Pattern codes            | ✓             | 7        | deferred           | 0            | Same — AnnoStd describes patcodes as BNF (`patcode ::= [ ' ] Y patnonY | …`) on a107199 rather than a code-letter table. |
| Errors                   | ✓             | 1601     | deferred           | 0            | YDB documents vendor mnemonics; ANSI M1–M75 set is in AnnoStd's chapter on conforming implementations and needs a separate extractor (deferred to v0.2). All YDB errors are tagged `ydb-extension`. |
| Environment              | deferred      | 0        | deferred           | 0            | Heterogeneous; per spec §5.7 the most divergent family. Deferred to v0.2. |

**Decision:** v1.0 ships 6/7 YDB concept families and 3/7 AnnoStd
concept families. The reconciler in A2 covers the 3 families where
both sources contribute (commands, functions, ISVs). YDB-only
families (operators, pattern codes, errors) flow through the
reconciler as `in_anno=false` rows, which is honest signalling for
downstream consumers. Environment and the BNF-form AnnoStd extractors
are tracked for v0.2.

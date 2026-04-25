# sources/ — offline local replicas

This tree holds the offline local replicas that drive every downstream
extraction and analysis step in `m-standard`. The pipeline never reaches
the live network at run time; the upstream is consulted only when a
snapshot is deliberately refreshed.

See `docs/spec.md` §4 for the policy in full.

## Layout

```
sources/
├── README.md                  # this file
├── anno/
│   ├── manifest.tsv           # URL -> local path -> sha256 -> fetched_at
│   ├── fetch.sh               # re-crawls the AnnoStd mirror from upstream
│   └── site/                  # crawled offline mirror of AnnoStd (gitignored until A0 license check)
└── ydb/
    ├── manifest.tsv           # includes upstream remote URL + pinned commit SHA
    ├── fetch.sh               # `git clone --depth=1` at the pinned commit
    └── repo/                  # full clone of the YottaDB documentation repository (gitignored until A0 license check)
```

## Acquisition

```bash
make sources       # both
make sources-anno  # AnnoStd only
make sources-ydb   # YottaDB docs clone only
```

`make sources-anno` runs the in-tree crawler
(`src/m_standard/tools/crawl_anno.py`) which mirrors the AnnoStd HTML
tree under `sources/anno/site/`, preserving the directory structure and
rewriting only what is required for the mirror to open and navigate
correctly from `file://` and via `make serve-anno`. Page bodies are
preserved byte-for-byte for extraction purposes.

`make sources-ydb` runs `tools/clone-ydb.sh`, which performs a `git
clone` of the YottaDB documentation source repository at the commit SHA
recorded in `sources/ydb/manifest.tsv` and then strips the inner `.git/`
so the working tree can be vendored as plain files. The pinned SHA is
preserved per-row in the manifest, so reproducibility holds without the
embedded git directory. Re-running the script with a new pin re-clones
into a temp directory and mirrors the result onto `sources/ydb/repo/`.

## Redistribution status (verified at Phase A0)

Each source has its own license. Where the licence permits redistribution,
the bulk content of the replica is committed directly so a fresh clone
is browseable / walkable offline with no network round-trip. Where the
licence does not (or where permission is unclear), only the
`manifest.tsv` + `fetch.sh` pair is tracked, and local users repopulate
the replica via `make sources`.

| Source  | Upstream                                          | Licence                                       | Redistributable? | Bulk committed? |
|---------|---------------------------------------------------|-----------------------------------------------|------------------|-----------------|
| AnnoStd | http://71.174.62.16/Demo/AnnoStd                  | © MUMPS Development Committee (standard text), © Jacquard Systems Research / Ed de Moel (annotations); no explicit redistribution licence stated on the site | **No** — assume not | No (gitignored; rebuild via `bash sources/anno/fetch.sh`) |
| YottaDB | https://gitlab.com/YottaDB/DB/YDBDoc.git          | GNU Free Documentation License v1.3 (per `repo/COPYING` + `repo/LICENSE.rst`) | **Yes** — GFDL §2 explicitly permits "copy and distribute"; no Invariant Sections, no Cover Texts | Yes (the cloned tree is committed) |

When the AnnoStd licence question is resolved (e.g. by direct
permission from the copyright holders), the gitignore entry for
`sources/anno/site/` can be dropped and the mirror committed alongside
the manifest in a follow-up.

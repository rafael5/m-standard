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
recorded in `sources/ydb/manifest.tsv`. The cloned tree retains its
`.git/` so the exact commit is reproducible and updates are a `git
pull`.

## Redistribution status (verified at Phase A0)

Each source has its own license. Until Phase A0 of the project explicitly
verifies redistribution rights, the bulk content of both replicas is
gitignored (see `.gitignore`) and only the `manifest.tsv` + `fetch.sh`
pair is tracked. Local users still get a fully reproducible build via
`make sources`.

When A0 confirms redistribution is permitted for a source, the relevant
ignore block in `.gitignore` is dropped and the local replica is
committed directly so a fresh clone is browseable / walkable offline
with no network round-trip.

| Source  | Upstream                            | Default policy assumption       | A0 verified? |
|---------|-------------------------------------|---------------------------------|--------------|
| AnnoStd | http://71.174.62.16/Demo/AnnoStd    | Mirroring historically encouraged | not yet |
| YottaDB | YottaDB documentation repo (GitLab) | Open-source, freely cloneable   | not yet |

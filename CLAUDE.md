# Claude project context — m-standard

## What this is
Reconciles the Annotated M Standard (AnnoStd) and the YottaDB
documentation corpus into a single citable, machine-readable reference
standard for the M (MUMPS) language. Outputs are TSV + JSON pairs under
`integrated/` plus a narrative under `docs/m-standards-guide.md`.

The full design and rationale are in `docs/spec.md`. ADRs in
`docs/adr/`.

## Where things live
- `src/m_standard/` — library + tools package. Anything importable.
- `src/m_standard/tools/` — pipeline stages (crawl, extract, reconcile,
  emit, validate). Each is invokable via `python -m
  m_standard.tools.<name>`.
- `tools/` — non-Python utilities (e.g. `clone-ydb.sh`).
- `sources/` — offline local replicas of the upstream sources. The
  pipeline reads only from here, never the network at run time.
- `per-source/`, `integrated/`, `schemas/` — pipeline outputs (committed
  artifacts).
- `tests/` — pytest, mirrors `src/m_standard/` structure.

## Pipeline (per spec §7)
```
sources/      ──extract──▶  per-source/<src>/*.tsv
                  └───reconcile──▶  integrated/*.tsv + conflicts.tsv
                       └────emit──▶  integrated/*.json
                            └────validate──▶  CI gates pass
```

## Hard rules
- **TDD.** Test first, confirm failure, then implement. Always.
- **No live network at pipeline run time.** Crawl/clone populates
  `sources/`; everything downstream reads from disk.
- **Reproducibility.** Every source file has a sha256 in
  `sources/<src>/manifest.tsv`. Every YDB-derived row carries the
  pinned commit SHA.
- **Provenance.** Every integrated row has `in_anno`/`in_ydb` flags +
  source section refs. No integrated row exists without at least one
  source attesting it.
- **Determinism.** `reconcile.py` is byte-deterministic — same inputs,
  same outputs.

## Toolchain
- Python ≥3.12, `uv`, ruff, mypy, pytest.
- `Makefile` uses `.venv/bin/` prefixes for every tool (parent direnv
  hijacks bare names — see `docs/build-log.md` BL-001).

## Conventions
- No `print()` in library code — use `logging.getLogger(__name__)`.
- BeautifulSoup attr access: cast with `str()` (mypy strict).
- Click group options before subcommand if Click is added later.
- YAML frontmatter: quote any value containing a colon.

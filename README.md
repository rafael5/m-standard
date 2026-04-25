# m-standard

A single, integrated, citable, machine-readable reference standard for the
M (MUMPS) programming language, synthesized by extracting and reconciling
two primary sources:

- The **Annotated M Standard** (X11.1-1995 / ISO 11756:1999) — captured as
  a crawled offline mirror of `http://71.174.62.16/Demo/AnnoStd`.
- The **YottaDB documentation corpus** — captured as a full `git clone` of
  YottaDB's documentation source repository on GitLab.

Both sources are held as offline local replicas under `sources/`, and those
replicas — not the live upstream — are the foundation for all extraction
and analysis.

The full design is in [`docs/spec.md`](docs/spec.md).

## Outputs

- `integrated/<concept>.tsv` — flat queryable facts (commands, intrinsic
  functions, intrinsic special variables, operators, pattern codes, errors,
  environment).
- `integrated/<concept>.json` — same entries with nested structure
  (argument grammars, parameter lists, error tables) suitable for code
  generation.
- `integrated/conflicts.tsv` — every non-trivial reconciliation between
  the two sources, with explicit resolution.
- `docs/m-standards-guide.md` — human-readable narrative reference.

Downstream consumers (e.g. `tree-sitter-m`, `vista-meta`) read the
integrated TSV+JSON pair at their own build time.

## Workflow

```bash
make install     # create .venv, install deps, install pre-commit hooks
make sources     # build both offline replicas (crawl AnnoStd, clone YDB docs)
make extract     # per-source TSVs from the replicas
make reconcile   # integrated TSVs + conflicts.tsv
make validate    # CI gates (manifests, provenance, schemas, round-trip)
make all         # everything end-to-end
make serve-anno  # browse the AnnoStd mirror at http://localhost:8765
make check       # lint + mypy + cov
```

## License

AGPL-3.0 — see [LICENSE](LICENSE). Source materials redistributed under
`sources/` are governed by their own licenses; see
[`sources/README.md`](sources/README.md).

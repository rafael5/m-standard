"""Pragmatic M standard emitter.

The pragmatic M standard is the cross-vendor language surface that
runs unmodified on both YottaDB and InterSystems IRIS. It's the
answer VistA developers actually need: "what M can I write that
runs on either engine without changes?"

Tier definitions:
- ``core`` — present in BOTH YDB and IRIS, regardless of AnnoStd
  presence. The pragmatic standard *is* this tier. Includes both
  the ANSI core (in_anno && in_ydb && in_iris) and the de-facto
  multi-vendor extensions (in_ydb && in_iris && !in_anno) like
  ZWRITE, $INCREMENT, $ZHOROLOG.
- ``ydb-only`` — YDB-specific; using these breaks IRIS portability.
- ``iris-only`` — IRIS-specific; using these breaks YDB portability.
- ``ansi-unimplemented`` — AnnoStd documents it but neither vendor
  implements it. Historical curiosities; do not use.

Per spec §10, this is one of m-standard's published outputs — see
``docs/pragmatic-m-standard.md`` for the full rationale and how
downstream tools should consume it.

Auto-derived from the integrated layer; nothing hand-curated.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

import jsonschema

log = logging.getLogger(__name__)

DEFAULT_INTEGRATED_DIR = Path("integrated")
DEFAULT_SCHEMA_PATH = Path("schemas") / "pragmatic-m-standard.schema.json"
DEFAULT_TSV_OUT = Path("integrated") / "pragmatic-m-standard.tsv"
DEFAULT_JSON_OUT = Path("integrated") / "pragmatic-m-standard.json"
SCHEMA_VERSION = "1"

_TSV_COLUMNS: tuple[str, ...] = (
    "concept",
    "name",
    "pragmatic_tier",
    "standard_status",
    "in_anno",
    "in_ydb",
    "in_iris",
    "anno_section",
    "ydb_section",
    "iris_section",
)

# Concepts whose entries get tiered by the YDB ∩ IRIS rule. Operators
# and pattern codes are too few + structurally different to warrant
# the same treatment in v0.2; errors live in a disjoint-namespaces
# world handled separately by the cross-vendor mappings.
_TIERED_CONCEPTS: tuple[tuple[str, str], ...] = (
    ("commands", "canonical_name"),
    ("intrinsic-functions", "canonical_name"),
    ("intrinsic-special-variables", "canonical_name"),
)

_DESCRIPTION = (
    "The pragmatic M standard: the language surface that runs "
    "unmodified on both YottaDB and InterSystems IRIS. Filter to "
    "pragmatic_tier='core' for the portable subset suitable for "
    "cross-engine VistA development."
)


def derive_tier(in_anno: bool, in_ydb: bool, in_iris: bool) -> str:
    """Map (in_anno, in_ydb, in_iris) to a pragmatic tier."""
    if in_ydb and in_iris:
        return "core"
    if in_ydb and not in_iris:
        return "ydb-only"
    if in_iris and not in_ydb:
        return "iris-only"
    if in_anno:
        return "ansi-unimplemented"
    # Defensive: shouldn't happen — every integrated row has at
    # least one source, enforced by the provenance gate.
    return "ansi-unimplemented"


def emit_pragmatic_standard(
    *,
    integrated_dir: Path,
    tsv_out: Path,
    json_out: Path,
    schema_path: Path,
) -> None:
    rows: list[dict] = []
    for concept, key_field in _TIERED_CONCEPTS:
        tsv = integrated_dir / f"{concept}.tsv"
        if not tsv.exists():
            continue
        for r in _read_tsv(tsv):
            in_anno = r.get("in_anno", "false").lower() == "true"
            in_ydb = r.get("in_ydb", "false").lower() == "true"
            in_iris = r.get("in_iris", "false").lower() == "true"
            rows.append({
                "concept": concept,
                "name": r[key_field],
                "pragmatic_tier": derive_tier(in_anno, in_ydb, in_iris),
                "standard_status": r.get("standard_status", ""),
                "in_anno": in_anno,
                "in_ydb": in_ydb,
                "in_iris": in_iris,
                "anno_section": r.get("anno_section", ""),
                "ydb_section": r.get("ydb_section", ""),
                "iris_section": r.get("iris_section", ""),
            })
    rows.sort(key=lambda r: (r["concept"], r["name"]))

    counts = {
        "core": 0,
        "ydb-only": 0,
        "iris-only": 0,
        "ansi-unimplemented": 0,
    }
    for r in rows:
        counts[r["pragmatic_tier"]] += 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "concept": "pragmatic-m-standard",
        "description": _DESCRIPTION,
        "counts": counts,
        "entries": rows,
    }
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)

    tsv_out.parent.mkdir(parents=True, exist_ok=True)
    with tsv_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_TSV_COLUMNS)
        for r in rows:
            writer.writerow([
                r["concept"], r["name"], r["pragmatic_tier"],
                r["standard_status"],
                "true" if r["in_anno"] else "false",
                "true" if r["in_ydb"] else "false",
                "true" if r["in_iris"] else "false",
                r["anno_section"], r["ydb_section"], r["iris_section"],
            ])

    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Emit the pragmatic M standard (YDB ∩ IRIS) tiered output."
    )
    parser.add_argument("--integrated", type=Path, default=DEFAULT_INTEGRATED_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--tsv-out", type=Path, default=DEFAULT_TSV_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    emit_pragmatic_standard(
        integrated_dir=args.integrated,
        tsv_out=args.tsv_out,
        json_out=args.json_out,
        schema_path=args.schema,
    )
    log.info("wrote %s + %s", args.tsv_out, args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

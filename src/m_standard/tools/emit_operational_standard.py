"""Operational M standard emitter.

The pragmatic standard answers "what runs on both engines?" — it's
a portability filter, mechanically derived. SAC answers "what
should we write in VistA?" — it's policy, optimising for security,
maintainability, and operational discipline. The two are
complementary, not redundant: the pragmatic standard ⊋ the
SAC-clean subset.

The operational M standard is the intersection — entries that
satisfy both axes:

    operational = (pragmatic_tier == "core")
                AND (sac_status NOT IN {forbidden, restricted})

That's the language surface a VistA developer can actually use:
guaranteed to run unmodified on YottaDB and IRIS, and guaranteed
to pass XINDEX SAC validation. Smaller than either parent
standard. The smallness is the cost of doing critical-system
development on heterogeneous engines.

Outputs:
- ``integrated/operational-m-standard.tsv`` — flat queryable list
- ``integrated/operational-m-standard.json`` — typed bundle with
  counts summary, gated by
  ``schemas/operational-m-standard.schema.json``

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
DEFAULT_SCHEMA_PATH = Path("schemas") / "operational-m-standard.schema.json"
DEFAULT_TSV_OUT = Path("integrated") / "operational-m-standard.tsv"
DEFAULT_JSON_OUT = Path("integrated") / "operational-m-standard.json"
SCHEMA_VERSION = "1"

_TSV_COLUMNS: tuple[str, ...] = (
    "concept",
    "name",
    "in_anno",
    "in_ydb",
    "in_iris",
    "anno_section",
    "ydb_section",
    "iris_section",
)


def derive_operational(*, pragmatic_tier: str, sac_status: str) -> bool:
    """True if the entry is in the operational subset.

    Operational = portable across both engines (pragmatic-core)
    AND not policy-blocked by SAC.
    """
    if pragmatic_tier != "core":
        return False
    return sac_status not in ("forbidden", "restricted")


def emit_operational_standard(
    *,
    integrated_dir: Path,
    tsv_out: Path,
    json_out: Path,
    schema_path: Path,
) -> None:
    pragmatic_path = integrated_dir / "pragmatic-m-standard.tsv"
    compliance_path = integrated_dir / "va-sac-compliance.tsv"
    if not pragmatic_path.exists():
        raise FileNotFoundError(
            f"{pragmatic_path} not found — run `make emit-pragmatic` first"
        )
    if not compliance_path.exists():
        raise FileNotFoundError(
            f"{compliance_path} not found — run `make emit-sac` first"
        )

    sac_by_key: dict[tuple[str, str], str] = {}
    for r in _read_tsv(compliance_path):
        sac_by_key[(r["concept"], r["name"])] = r.get("sac_status", "")

    rows: list[dict] = []
    pragmatic_core_total = 0
    pragmatic_blocked = 0
    for r in _read_tsv(pragmatic_path):
        if r["pragmatic_tier"] != "core":
            continue
        pragmatic_core_total += 1
        sac_status = sac_by_key.get((r["concept"], r["name"]), "")
        if not derive_operational(
            pragmatic_tier=r["pragmatic_tier"], sac_status=sac_status
        ):
            pragmatic_blocked += 1
            continue
        rows.append({
            "concept": r["concept"],
            "name": r["name"],
            "in_anno": r.get("in_anno", "false").lower() == "true",
            "in_ydb": r.get("in_ydb", "false").lower() == "true",
            "in_iris": r.get("in_iris", "false").lower() == "true",
            "anno_section": r.get("anno_section", ""),
            "ydb_section": r.get("ydb_section", ""),
            "iris_section": r.get("iris_section", ""),
        })
    rows.sort(key=lambda r: (r["concept"], r["name"]))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "concept": "operational-m-standard",
        "description": (
            "M language surface that runs on both YottaDB and IRIS AND "
            "passes VA SAC (XINDEX). Intersection of pragmatic standard "
            "and SAC-clean entries — the operational subset for VistA."
        ),
        "counts": {
            "operational": len(rows),
            "pragmatic_blocked_by_sac": pragmatic_blocked,
            "pragmatic_core_total": pragmatic_core_total,
        },
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
                r["concept"], r["name"],
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
        description="Emit operational M standard (pragmatic ∩ SAC-clean)."
    )
    parser.add_argument("--integrated", type=Path, default=DEFAULT_INTEGRATED_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--tsv-out", type=Path, default=DEFAULT_TSV_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    emit_operational_standard(
        integrated_dir=args.integrated,
        tsv_out=args.tsv_out,
        json_out=args.json_out,
        schema_path=args.schema,
    )
    log.info("wrote %s + %s", args.tsv_out, args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

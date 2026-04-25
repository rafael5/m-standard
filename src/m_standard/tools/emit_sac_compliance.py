"""VA SAC vs pragmatic M standard compliance emitter.

Joins the VA Standards and Conventions overlay (``mappings/va-sac.tsv``)
against the pragmatic M standard (``integrated/pragmatic-m-standard.tsv``)
to surface portability concerns for VistA developers.

Four concern categories per entry:

- ``aligned``: SAC and pragmatic agree (SAC permits a portable entry,
  or SAC forbids an unportable entry).
- ``sac_says_use_but_not_portable``: SAC permits/recommends but the
  entry isn't in pragmatic-core. VistA code following SAC literally
  would break on the missing engine.
- ``sac_says_avoid_but_portable``: SAC forbids/restricts but the entry
  IS pragmatic-core. SAC may be overly conservative.
- ``sac_silent_on_portable`` / ``sac_silent_on_unportable``: SAC
  doesn't mention the entry at all.

Per docs/va-sac-and-pragmatic-standard.md, this output is the
machine-checkable cross-reference between VistA's policy layer and
m-standard's data-driven portability tier. The SAC overlay file is
hand-curated; the join is automatic.
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
DEFAULT_MAPPINGS_DIR = Path("mappings")
DEFAULT_SCHEMA_PATH = Path("schemas") / "va-sac-compliance.schema.json"
DEFAULT_TSV_OUT = Path("integrated") / "va-sac-compliance.tsv"
DEFAULT_JSON_OUT = Path("integrated") / "va-sac-compliance.json"
SCHEMA_VERSION = "1"

_TSV_COLUMNS: tuple[str, ...] = (
    "concept",
    "name",
    "pragmatic_tier",
    "sac_status",
    "concern",
    "sac_section",
    "notes",
)


def classify_concern(sac_status: str, pragmatic_tier: str) -> str:
    """Map (sac_status, pragmatic_tier) → concern category."""
    is_core = pragmatic_tier == "core"
    if sac_status in ("permitted", "recommended"):
        return "aligned" if is_core else "sac_says_use_but_not_portable"
    if sac_status in ("forbidden", "restricted"):
        return "sac_says_avoid_but_portable" if is_core else "aligned"
    # SAC silent on this entry.
    return "sac_silent_on_portable" if is_core else "sac_silent_on_unportable"


def emit_sac_compliance(
    *,
    integrated_dir: Path,
    mappings_dir: Path,
    tsv_out: Path,
    json_out: Path,
    schema_path: Path,
) -> None:
    pragmatic_path = integrated_dir / "pragmatic-m-standard.tsv"
    if not pragmatic_path.exists():
        raise FileNotFoundError(
            f"pragmatic standard not found at {pragmatic_path} — "
            "run `make emit-pragmatic` first"
        )
    sac_by_key: dict[tuple[str, str], dict[str, str]] = {}
    sac_path = mappings_dir / "va-sac.tsv"
    if sac_path.exists():
        for r in _read_tsv(sac_path):
            key = (r["concept"], r["name"])
            sac_by_key[key] = r

    rows: list[dict] = []
    counts: dict[str, int] = {
        "aligned": 0,
        "sac_says_use_but_not_portable": 0,
        "sac_says_avoid_but_portable": 0,
        "sac_silent_on_portable": 0,
        "sac_silent_on_unportable": 0,
    }
    for r in _read_tsv(pragmatic_path):
        key = (r["concept"], r["name"])
        sac_row = sac_by_key.get(key)
        sac_status = sac_row.get("sac_status", "") if sac_row else ""
        sac_section = sac_row.get("sac_section", "") if sac_row else ""
        notes = sac_row.get("notes", "") if sac_row else ""
        concern = classify_concern(sac_status, r["pragmatic_tier"])
        counts[concern] += 1
        rows.append({
            "concept": r["concept"],
            "name": r["name"],
            "pragmatic_tier": r["pragmatic_tier"],
            "sac_status": sac_status,
            "concern": concern,
            "sac_section": sac_section,
            "notes": notes,
        })
    rows.sort(key=lambda r: (r["concept"], r["name"]))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "concept": "va-sac-compliance",
        "description": (
            "Cross-reference between VA Standards and Conventions and the "
            "pragmatic M standard. Filter to concern in "
            "[sac_says_use_but_not_portable, sac_says_avoid_but_portable] "
            "for portability gaps that VistA developers should review."
        ),
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
            writer.writerow([r[c] for c in _TSV_COLUMNS])

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
        description="Emit VA SAC vs pragmatic compliance view."
    )
    parser.add_argument("--integrated", type=Path, default=DEFAULT_INTEGRATED_DIR)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--tsv-out", type=Path, default=DEFAULT_TSV_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    emit_sac_compliance(
        integrated_dir=args.integrated,
        mappings_dir=args.mappings,
        tsv_out=args.tsv_out,
        json_out=args.json_out,
        schema_path=args.schema,
    )
    log.info("wrote %s + %s", args.tsv_out, args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

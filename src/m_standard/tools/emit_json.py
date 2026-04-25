"""TSV → JSON emitter for the integrated layer (spec §6.3 + §7.3).

Each integrated/<concept>.tsv produces an integrated/<concept>.json
file with the shape:

    {
      "schema_version": "1",
      "concept": "<name>",
      "entries": [ { ... }, ... ]
    }

Per AD-04 the JSON is the structured-detail surface (suitable for
code generation in tree-sitter-m); per AD-05 the schema_version field
is locked at "1" for v1.0 and bumped on breaking changes.

The emitter is the *only* place where TSV-to-JSON conversion happens,
so TSV/JSON consistency is structural, not aspirational. Output is
validated against schemas/<concept>.schema.json before write.

Type coercions vs the raw TSV strings:
- "true" / "false" -> JSON boolean (in_anno, in_ydb)
- empty conflict_id -> JSON null (so consumers can "if entry.conflict_id is None")
- All other fields stay strings (we don't yet parse format grammars,
  argument lists, etc. — the JSON file is a 1:1 typed mirror of the
  TSV with one nested-structure field reserved per spec for future
  enrichment).

Output is byte-deterministic: keys sorted within each entry, entries
sorted by primary key, indent=2, trailing newline.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

log = logging.getLogger(__name__)

DEFAULT_INTEGRATED_DIR = Path("integrated")
DEFAULT_SCHEMA_DIR = Path("schemas")
SCHEMA_VERSION = "1"

_BOOL_FIELDS = ("in_anno", "in_ydb")
_NULLABLE_FIELDS = ("conflict_id",)


@dataclass(frozen=True)
class ConceptSpec:
    name: str
    sort_key: str
    schema_basename: str


CONCEPTS: tuple[ConceptSpec, ...] = (
    ConceptSpec("commands", "canonical_name", "command.schema.json"),
    ConceptSpec(
        "intrinsic-functions", "canonical_name", "intrinsic-function.schema.json"
    ),
    ConceptSpec(
        "intrinsic-special-variables",
        "canonical_name",
        "intrinsic-special-variable.schema.json",
    ),
    ConceptSpec("operators", "symbol", "operator.schema.json"),
    ConceptSpec("pattern-codes", "code", "pattern-code.schema.json"),
    ConceptSpec("errors", "mnemonic", "error.schema.json"),
    ConceptSpec("environment", "name", "environment-entry.schema.json"),
)


def tsv_row_to_entry(row: dict[str, str]) -> dict[str, Any]:
    """Coerce a TSV row's string values into a JSON-typed entry."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k in _BOOL_FIELDS:
            out[k] = v.lower() == "true"
        elif k in _NULLABLE_FIELDS:
            out[k] = v if v else None
        else:
            out[k] = v
    return out


def emit_concept_json(
    *,
    tsv_path: Path,
    json_path: Path,
    concept: str,
    schema_path: Path,
) -> None:
    rows = _read_tsv(tsv_path)
    entries = [tsv_row_to_entry(r) for r in rows]
    sort_key = _sort_key_for(concept)
    entries.sort(key=lambda e: e.get(sort_key, ""))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "concept": concept,
        "entries": entries,
    }
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def emit_all(integrated_dir: Path, schema_dir: Path) -> None:
    """Emit JSON for every concept in CONCEPTS plus conflicts."""
    for spec in CONCEPTS:
        tsv = integrated_dir / f"{spec.name}.tsv"
        if not tsv.exists():
            log.info("skip %s: %s not found", spec.name, tsv)
            continue
        out = integrated_dir / f"{spec.name}.json"
        emit_concept_json(
            tsv_path=tsv,
            json_path=out,
            concept=spec.name,
            schema_path=schema_dir / spec.schema_basename,
        )
        log.info("wrote %s", out)

    conflicts_tsv = integrated_dir / "conflicts.tsv"
    if conflicts_tsv.exists():
        emit_concept_json(
            tsv_path=conflicts_tsv,
            json_path=integrated_dir / "conflicts.json",
            concept="conflicts",
            schema_path=schema_dir / "conflicts.schema.json",
        )
        log.info("wrote %s", integrated_dir / "conflicts.json")


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _sort_key_for(concept: str) -> str:
    for spec in CONCEPTS:
        if spec.name == concept:
            return spec.sort_key
    if concept == "conflicts":
        return "conflict_id"
    return "canonical_name"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Emit JSON per integrated TSV (validated against schemas/)."
    )
    parser.add_argument("--integrated", type=Path, default=DEFAULT_INTEGRATED_DIR)
    parser.add_argument("--schemas", type=Path, default=DEFAULT_SCHEMA_DIR)
    args = parser.parse_args(argv)

    emit_all(args.integrated, args.schemas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

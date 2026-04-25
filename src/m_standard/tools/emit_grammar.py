"""Grammar-surface emitter (spec §10.1).

Reads the integrated TSVs and produces a single
``integrated/grammar-surface.json`` containing exactly the
enumerations a grammar generator (``tree-sitter-m`` or any other
M-language parser builder) needs at build time:

- commands (with prefix-form expansion: BREAK with abbreviation B
  yields all_forms=[B, BR, BRE, BREA, BREAK])
- intrinsic_functions (same expansion: $ASCII / $A → all 5 prefix
  forms)
- intrinsic_special_variables (same)
- operators (symbol + class)
- pattern_codes (single-letter codes + descriptions)

Per AD-04, this file is the structured-detail surface for code
generation, sitting alongside the per-concept JSON files. Per AD-05
it carries ``schema_version: "1"`` and is gated by
``schemas/grammar-surface.schema.json``.

The emitter is byte-deterministic. Output is sorted within each
section by canonical name / symbol / code so a re-run produces a
byte-identical file.
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
DEFAULT_SCHEMA_PATH = Path("schemas") / "grammar-surface.schema.json"
DEFAULT_OUT_PATH = Path("integrated") / "grammar-surface.json"
SCHEMA_VERSION = "1"


def all_forms(canonical: str, abbreviation: str) -> list[str]:
    """Return every prefix-truncation form a parser must accept.

    M abbreviations are prefix-truncations: ``BREAK`` with
    abbreviation ``B`` is recognised as ``B``, ``BR``, ``BRE``,
    ``BREA``, or ``BREAK`` — any prefix at least as long as the
    abbreviation. The grammar surface explodes this so consumers
    don't reimplement the rule.

    - Empty abbreviation → ``[canonical]`` only.
    - Abbreviation == canonical → ``[canonical]`` only.
    - Abbreviation that isn't a prefix of canonical (data error) →
      defensive fallback ``[canonical]``.
    """
    if not canonical:
        return []
    if not abbreviation:
        return [canonical]
    abbrev_u = abbreviation.upper()
    canonical_u = canonical.upper()
    if not canonical_u.startswith(abbrev_u):
        return [canonical]
    n = len(abbreviation)
    if n >= len(canonical):
        return [canonical]
    # Preserve the canonical's casing in each prefix.
    return [canonical[:i] for i in range(n, len(canonical) + 1)]


def emit_grammar_surface(
    *,
    integrated_dir: Path,
    out: Path,
    schema_path: Path,
) -> None:
    payload: dict = {
        "schema_version": SCHEMA_VERSION,
        "concept": "grammar-surface",
        "commands": _named_tokens(integrated_dir / "commands.tsv"),
        "intrinsic_functions": _named_tokens(
            integrated_dir / "intrinsic-functions.tsv"
        ),
        "intrinsic_special_variables": _named_tokens(
            integrated_dir / "intrinsic-special-variables.tsv"
        ),
        "operators": _operators(integrated_dir / "operators.tsv"),
        "pattern_codes": _pattern_codes(integrated_dir / "pattern-codes.tsv"),
    }
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _named_tokens(tsv: Path) -> list[dict]:
    if not tsv.exists():
        return []
    out: list[dict] = []
    for row in _read_tsv(tsv):
        canonical = row["canonical_name"]
        abbreviation = row.get("abbreviation", "")
        out.append({
            "canonical": canonical,
            "abbreviation": abbreviation,
            "all_forms": all_forms(canonical, abbreviation),
            "standard_status": row.get("standard_status", ""),
        })
    out.sort(key=lambda e: e["canonical"])
    return out


def _operators(tsv: Path) -> list[dict]:
    if not tsv.exists():
        return []
    out: list[dict] = []
    for row in _read_tsv(tsv):
        out.append({
            "symbol": row["symbol"],
            "operator_class": row["operator_class"],
            "standard_status": row.get("standard_status", ""),
        })
    out.sort(key=lambda e: (e["operator_class"], e["symbol"]))
    return out


def _pattern_codes(tsv: Path) -> list[dict]:
    if not tsv.exists():
        return []
    out: list[dict] = []
    for row in _read_tsv(tsv):
        out.append({
            "code": row["code"],
            "description": row.get("description", ""),
            "standard_status": row.get("standard_status", ""),
        })
    out.sort(key=lambda e: e["code"])
    return out


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def emit_multi_vendor_extensions(integrated_dir: Path, out: Path) -> None:
    """Emit ``integrated/multi-vendor-extensions.tsv`` — entries present
    in BOTH YottaDB and IRIS but NOT in AnnoStd.

    These are the de facto extensions the M community has converged on
    without formal ANSI standardisation: TRY/CATCH-family commands,
    ``$INCREMENT``, the ``$Z*`` core (``$ZHOROLOG``, ``$ZTRAP``, ...),
    etc. The file is a curation worksheet — useful both for tooling
    that wants the broader "real-world ANSI core" and for any future
    M standards revision deciding what to formalise.

    Auto-derived from the integrated TSVs; nothing hand-curated here.
    """
    rows: list[dict[str, str]] = []
    for concept, key_field in (
        ("commands", "canonical_name"),
        ("intrinsic-functions", "canonical_name"),
        ("intrinsic-special-variables", "canonical_name"),
    ):
        tsv = integrated_dir / f"{concept}.tsv"
        if not tsv.exists():
            continue
        for r in _read_tsv(tsv):
            if r.get("standard_status") == "multi-vendor-ext":
                rows.append({
                    "concept": concept,
                    "name": r[key_field],
                    "ydb_section": r.get("ydb_section", ""),
                    "iris_section": r.get("iris_section", ""),
                })
    rows.sort(key=lambda r: (r["concept"], r["name"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(("concept", "name", "ydb_section", "iris_section"))
        for r in rows:
            writer.writerow([r["concept"], r["name"], r["ydb_section"],
                             r["iris_section"]])


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Emit grammar-surface.json from the integrated layer."
    )
    parser.add_argument("--integrated", type=Path, default=DEFAULT_INTEGRATED_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
    args = parser.parse_args(argv)

    emit_grammar_surface(
        integrated_dir=args.integrated, out=args.out, schema_path=args.schema
    )
    log.info("wrote %s", args.out)
    emit_multi_vendor_extensions(
        integrated_dir=args.integrated,
        out=args.integrated / "multi-vendor-extensions.tsv",
    )
    log.info("wrote %s/multi-vendor-extensions.tsv", args.integrated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

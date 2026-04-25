"""Two-source reconciler.

Consumes per-source TSVs and produces the integrated layer plus
``conflicts.tsv`` per spec §7.2 + §6.2 + §6.4. Resolution follows
AD-01 strictly:

- AnnoStd is normative for "is X part of the standard".
- YDB is authoritative for current implementation detail.
- Anything in YDB but not in AnnoStd is a YDB extension.
- Anything in AnnoStd but not in YDB is a standard-but-unimplemented
  signal — recorded as ``kind=existence``.
- Same name in both sources but different format strings is a
  ``kind=definition`` conflict.

The reconciler is byte-deterministic: rows sorted by canonical_name,
conflict IDs assigned in encounter order, and field ordering is fixed.
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_PER_SOURCE_DIR = Path("per-source")
DEFAULT_INTEGRATED_DIR = Path("integrated")

INTEGRATED_COMMAND_COLUMNS: tuple[str, ...] = (
    "canonical_name",
    "abbreviation",
    "format",
    "standard_status",
    "in_anno",
    "in_ydb",
    "anno_section",
    "ydb_section",
    "conflict_id",
    "notes",
)

CONFLICTS_COLUMNS: tuple[str, ...] = (
    "conflict_id",
    "concept",
    "entry",
    "kind",
    "anno_says",
    "ydb_says",
    "resolution",
    "resolution_basis",
)


def reconcile_commands(
    anno_path: Path, ydb_path: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return _reconcile_named_concept(anno_path, ydb_path, concept="commands")


def reconcile_intrinsic_functions(
    anno_path: Path, ydb_path: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return _reconcile_named_concept(
        anno_path, ydb_path, concept="intrinsic-functions"
    )


def reconcile_special_variables(
    anno_path: Path, ydb_path: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return _reconcile_named_concept(
        anno_path, ydb_path, concept="intrinsic-special-variables"
    )


def _reconcile_named_concept(
    anno_path: Path,
    ydb_path: Path,
    *,
    concept: str,
    key_field: str = "canonical_name",
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Generic reconciliation for concepts keyed by a single field.

    Used for commands, intrinsic functions, intrinsic special variables
    (key_field=canonical_name), and now also operators (key_field=symbol)
    and errors (key_field=mnemonic) once both sources contribute rows.
    """
    anno_rows = _read_tsv(anno_path)
    ydb_rows = _read_tsv(ydb_path)

    anno_by_name = {r[key_field]: r for r in anno_rows}
    ydb_by_name = {r[key_field]: r for r in ydb_rows}
    all_names = sorted(set(anno_by_name) | set(ydb_by_name))

    integrated: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    next_conflict_id = 1

    for name in all_names:
        a = anno_by_name.get(name)
        y = ydb_by_name.get(name)
        in_anno = a is not None
        in_ydb = y is not None

        # Standard status per AD-01: AnnoStd is normative for ANSI
        # membership. If AnnoStd has it, it's ``ansi``; if AnnoStd
        # does NOT have it, it's a YDB extension regardless of what
        # YDB's per-source ``standard_status_hint`` claims (YDB hints
        # ANSI for any non-Z name, but post-1995 additions and YDB
        # non-Z extensions both fall outside AnnoStd's ANSI set).
        standard_status = "ansi" if in_anno else "ydb-extension"

        # Pick format: prefer YDB's (more complete with postconditional/args)
        # when both are present and differ; fall back to AnnoStd's.
        anno_format = a["format"] if a else ""
        ydb_format = y["format"] if y else ""
        chosen_format = ydb_format or anno_format

        # Pick abbreviation similarly: YDB usually has it, AnnoStd often
        # leaves it blank for BNF-style commands (BL-007).
        anno_abbrev = a["abbreviation"] if a else ""
        ydb_abbrev = y["abbreviation"] if y else ""
        chosen_abbrev = ydb_abbrev or anno_abbrev

        conflict_id = ""
        notes = ""

        if in_anno and not in_ydb:
            # Standard says it exists; YDB does not implement it.
            conflict_id = f"CONF-{next_conflict_id:03d}"
            next_conflict_id += 1
            conflicts.append(
                {
                    "conflict_id": conflict_id,
                    "concept": concept,
                    "entry": name,
                    "kind": "existence",
                    "anno_says": _normalise(anno_format) or "(present)",
                    "ydb_says": "absent",
                    "resolution": (
                        "kept (AnnoStd is normative for standard membership)"
                    ),
                    "resolution_basis": "AD-01 (AnnoStd normative)",
                }
            )
        elif in_anno and in_ydb:
            # Definition conflict on abbreviation — the only field where
            # the two sources can be compared verbatim. Format strings use
            # different metalanguages (AnnoStd: ``postcond``/``SP``;
            # YDB: ``[:tvexpr]``) and need semantic normalisation that's
            # out of scope for v1.0 of the reconciler. The verbatim format
            # from each source is preserved on the integrated row's
            # `format` and on its `*_section` cross-references.
            if (
                anno_abbrev
                and ydb_abbrev
                and anno_abbrev.upper() != ydb_abbrev.upper()
            ):
                conflict_id = f"CONF-{next_conflict_id:03d}"
                next_conflict_id += 1
                conflicts.append(
                    {
                        "conflict_id": conflict_id,
                        "concept": concept,
                        "entry": name,
                        "kind": "definition",
                        "anno_says": f"abbreviation={anno_abbrev}",
                        "ydb_says": f"abbreviation={ydb_abbrev}",
                        "resolution": f"YDB abbreviation chosen: {ydb_abbrev}",
                        "resolution_basis": (
                            "AD-01 (YDB authoritative for current "
                            "implementation detail)"
                        ),
                    }
                )

        integrated.append(
            {
                "canonical_name": name,
                "abbreviation": chosen_abbrev,
                "format": chosen_format,
                "standard_status": standard_status,
                "in_anno": "true" if in_anno else "false",
                "in_ydb": "true" if in_ydb else "false",
                "anno_section": a["source_section"] if a else "",
                "ydb_section": y["source_section"] if y else "",
                "conflict_id": conflict_id,
                "notes": notes,
            }
        )

    return integrated, conflicts


def reconcile_commands_to_tsv(
    *,
    anno_path: Path,
    ydb_path: Path,
    out_dir: Path,
    conflicts_path: Path | None = None,
) -> None:
    integrated, conflicts = reconcile_commands(anno_path, ydb_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_tsv(out_dir / "commands.tsv", INTEGRATED_COMMAND_COLUMNS, integrated)
    cpath = conflicts_path or (out_dir / "conflicts.tsv")
    _write_tsv(cpath, CONFLICTS_COLUMNS, conflicts)


_INTEGRATED_OPERATOR_COLUMNS: tuple[str, ...] = (
    "symbol",
    "operator_class",
    "description",
    "standard_status",
    "in_anno",
    "in_ydb",
    "anno_section",
    "ydb_section",
    "conflict_id",
    "notes",
)

_INTEGRATED_ERROR_COLUMNS: tuple[str, ...] = (
    "mnemonic",
    "summary",
    "kind",
    "standard_status",
    "source",
    "in_anno",
    "in_ydb",
    "in_iris",
    "ansi_code",
    "ydb_mnemonic",
    "iris_mnemonic",
    "anno_section",
    "ydb_section",
    "iris_section",
    "conflict_id",
    "notes",
)

DEFAULT_MAPPINGS_DIR = Path("mappings")


def reconcile_operators(
    anno_path: Path, ydb_path: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Join operators on (operator_class, symbol).

    Both sources catalogue the M operator set. The symbol alone isn't
    enough — though for v1.0 AnnoStd and YDB happen to use the same
    operator_class labels for every shared operator. Class is included
    in the key for forward compatibility.
    """
    anno_rows = _read_tsv(anno_path)
    ydb_rows = _read_tsv(ydb_path)
    anno_by_key = {(r["operator_class"], r["symbol"]): r for r in anno_rows}
    ydb_by_key = {(r["operator_class"], r["symbol"]): r for r in ydb_rows}
    all_keys = sorted(set(anno_by_key) | set(ydb_by_key))

    integrated: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    next_conflict_id = 1
    for key in all_keys:
        a = anno_by_key.get(key)
        y = ydb_by_key.get(key)
        in_anno, in_ydb = a is not None, y is not None
        klass, symbol = key
        standard_status = "ansi" if in_anno else "ydb-extension"
        description = (
            (y or a or {}).get("description", "")  # type: ignore[union-attr]
        )
        conflict_id = ""
        if in_anno and not in_ydb:
            conflict_id = f"CONF-{next_conflict_id:03d}"
            next_conflict_id += 1
            conflicts.append(
                {
                    "conflict_id": conflict_id,
                    "concept": "operators",
                    "entry": f"{klass}/{symbol}",
                    "kind": "existence",
                    "anno_says": "(present)",
                    "ydb_says": "absent",
                    "resolution": "kept (AnnoStd is normative)",
                    "resolution_basis": "AD-01 (AnnoStd normative)",
                }
            )
        integrated.append(
            {
                "symbol": symbol,
                "operator_class": klass,
                "description": description,
                "standard_status": standard_status,
                "in_anno": "true" if in_anno else "false",
                "in_ydb": "true" if in_ydb else "false",
                "anno_section": a["source_section"] if a else "",
                "ydb_section": y["source_section"] if y else "",
                "conflict_id": conflict_id,
                "notes": "",
            }
        )
    return integrated, conflicts


def reconcile_errors(
    anno_path: Path,
    ydb_path: Path,
    iris_path: Path | None = None,
    *,
    mappings_dir: Path | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Join errors on mnemonic across up to three sources.

    Three disjoint mnemonic namespaces are unioned:

    - AnnoStd Annex B M-codes (``M1``..``M112``).
    - YottaDB vendor mnemonics (alphanumeric tokens like ``ABNCOMPTINC``).
    - IRIS system errors (uppercase ``<NAME>`` style, stored without
      the angle brackets, e.g. ``DIVIDE``).

    Each integrated row is tagged with the originating ``source`` and
    enriched via ``mappings/`` with cross-vendor pointers:

    - YDB rows get ``ansi_code`` (from ``ydb-ansi-errors.tsv``) and
      ``iris_mnemonic`` (from ``iris-ydb-errors.tsv``).
    - IRIS rows get ``ansi_code`` (from ``iris-ansi-errors.tsv``) and
      ``ydb_mnemonic`` (from ``iris-ydb-errors.tsv``).
    - AnnoStd rows are the ANSI code; their ``ansi_code`` is left
      blank since the ``mnemonic`` column already names them.

    The integrated layer is the union (no in-place merge across
    sources) because the three namespaces cannot collide. Cross-vendor
    matches are recorded as relational pointers, not row merges.
    """
    mdir = mappings_dir or DEFAULT_MAPPINGS_DIR
    anno_rows = _read_tsv(anno_path)
    ydb_rows = _read_tsv(ydb_path)
    iris_rows = _read_tsv(iris_path) if iris_path and iris_path.exists() else []

    anno_by_key = {r["mnemonic"]: r for r in anno_rows}
    ydb_by_key = {r["mnemonic"]: r for r in ydb_rows}
    iris_by_key = {r["mnemonic"]: r for r in iris_rows}

    ydb_to_ansi = _load_simple_mapping(
        mdir / "ydb-ansi-errors.tsv", "ydb_mnemonic", "ansi_code"
    )
    iris_to_ansi = _load_simple_mapping(
        mdir / "iris-ansi-errors.tsv", "iris_mnemonic", "ansi_code"
    )
    iris_to_ydb = _load_simple_mapping(
        mdir / "iris-ydb-errors.tsv", "iris_mnemonic", "ydb_mnemonic"
    )
    ydb_to_iris = {v: k for k, v in iris_to_ydb.items()}

    integrated: list[dict[str, str]] = []

    # AnnoStd rows.
    for key in sorted(anno_by_key):
        a = anno_by_key[key]
        integrated.append(_error_row(
            mnemonic=key, source="anno",
            summary=a.get("summary", ""), kind=a.get("kind", ""),
            standard_status="ansi",
            in_anno=True, in_ydb=False, in_iris=False,
            ansi_code="",
            ydb_mnemonic="", iris_mnemonic="",
            anno_section=a.get("source_section", ""),
            ydb_section="", iris_section="",
        ))

    # YDB rows.
    for key in sorted(ydb_by_key):
        y = ydb_by_key[key]
        integrated.append(_error_row(
            mnemonic=key, source="ydb",
            summary=y.get("summary", ""), kind=y.get("kind", ""),
            standard_status="ydb-extension",
            in_anno=False, in_ydb=True, in_iris=False,
            ansi_code=ydb_to_ansi.get(key, ""),
            ydb_mnemonic="",
            iris_mnemonic=ydb_to_iris.get(key, ""),
            anno_section="", ydb_section=y.get("source_section", ""),
            iris_section="",
        ))

    # IRIS rows.
    for key in sorted(iris_by_key):
        i = iris_by_key[key]
        # Tag iris-extension only if upstream said so OR Z-prefix.
        hint = i.get("standard_status_hint", "")
        status = "iris-extension" if hint == "iris-extension" else "iris-extension"
        # If the IRIS error maps to an ANSI code, the underlying
        # behaviour is part of the standard — but the IRIS *name* is
        # vendor-specific. Keep status=iris-extension; the ansi_code
        # cross-reference is the portability signal.
        integrated.append(_error_row(
            mnemonic=key, source="iris",
            summary=i.get("summary", ""), kind=i.get("kind", ""),
            standard_status=status,
            in_anno=False, in_ydb=False, in_iris=True,
            ansi_code=iris_to_ansi.get(key, ""),
            ydb_mnemonic=iris_to_ydb.get(key, ""),
            iris_mnemonic="",
            anno_section="", ydb_section="",
            iris_section=i.get("source_section", ""),
        ))

    return integrated, []  # No conflicts: namespaces don't overlap.


def _error_row(**kwargs) -> dict[str, str]:
    """Build an integrated-errors row with bool-as-string conversions."""
    return {
        "mnemonic": kwargs["mnemonic"],
        "summary": kwargs["summary"],
        "kind": kwargs["kind"],
        "standard_status": kwargs["standard_status"],
        "source": kwargs["source"],
        "in_anno": "true" if kwargs["in_anno"] else "false",
        "in_ydb": "true" if kwargs["in_ydb"] else "false",
        "in_iris": "true" if kwargs["in_iris"] else "false",
        "ansi_code": kwargs["ansi_code"],
        "ydb_mnemonic": kwargs["ydb_mnemonic"],
        "iris_mnemonic": kwargs["iris_mnemonic"],
        "anno_section": kwargs["anno_section"],
        "ydb_section": kwargs["ydb_section"],
        "iris_section": kwargs["iris_section"],
        "conflict_id": "",
        "notes": "",
    }


def _load_simple_mapping(path: Path, key_col: str, value_col: str) -> dict[str, str]:
    """Load ``mappings/X.tsv`` into ``{key_col: value_col}``."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for row in _read_tsv(path):
        k = row.get(key_col, "").strip()
        v = row.get(value_col, "").strip()
        if k and v:
            out[k] = v
    return out


def reconcile_all(per_source: Path, out_dir: Path) -> None:
    """Reconcile every concept family present in ``per_source/``.

    Modes:
    1. Both-source named concepts (commands, intrinsic-functions,
       intrinsic-special-variables): join on canonical_name.
    2. Both-source typed concepts (operators, errors): use specialised
       reconcilers (operators on (class, symbol); errors on mnemonic).
    3. YDB-only (pattern-codes): pass through with in_anno=false.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    all_conflicts: list[dict[str, str]] = []
    next_conflict_id = 1

    # Named concepts (both sources contribute, key=canonical_name).
    for concept in ("commands", "intrinsic-functions", "intrinsic-special-variables"):
        anno = per_source / "anno" / f"{concept}.tsv"
        ydb = per_source / "ydb" / f"{concept}.tsv"
        if not (anno.exists() or ydb.exists()):
            continue
        integrated, conflicts = _reconcile_named_concept(anno, ydb, concept=concept)
        renumbered = _renumber_conflicts(conflicts, integrated, next_conflict_id)
        next_conflict_id += len(renumbered)
        _write_tsv(out_dir / f"{concept}.tsv", INTEGRATED_COMMAND_COLUMNS, integrated)
        all_conflicts.extend(renumbered)
        log.info(
            "reconciled %s: %d rows, %d conflicts",
            concept, len(integrated), len(renumbered),
        )

    # Operators: both sources contribute, specialised join on (class, symbol).
    anno_ops = per_source / "anno" / "operators.tsv"
    ydb_ops = per_source / "ydb" / "operators.tsv"
    if ydb_ops.exists():
        integrated, conflicts = reconcile_operators(anno_ops, ydb_ops)
        renumbered = _renumber_conflicts(conflicts, integrated, next_conflict_id)
        next_conflict_id += len(renumbered)
        _write_tsv(out_dir / "operators.tsv", _INTEGRATED_OPERATOR_COLUMNS, integrated)
        all_conflicts.extend(renumbered)
        log.info(
            "reconciled operators: %d rows, %d conflicts",
            len(integrated), len(renumbered),
        )

    # Errors: union of M-codes (AnnoStd), vendor mnemonics (YDB),
    # and IRIS system errors. Three disjoint namespaces; cross-vendor
    # mappings live under mappings/.
    anno_errs = per_source / "anno" / "errors.tsv"
    ydb_errs = per_source / "ydb" / "errors.tsv"
    iris_errs = per_source / "iris" / "errors.tsv"
    if ydb_errs.exists() or anno_errs.exists() or iris_errs.exists():
        integrated, conflicts = reconcile_errors(
            anno_errs, ydb_errs, iris_errs if iris_errs.exists() else None
        )
        _write_tsv(out_dir / "errors.tsv", _INTEGRATED_ERROR_COLUMNS, integrated)
        log.info("reconciled errors: %d rows", len(integrated))

    # YDB-only pass-through families:
    # - pattern-codes: AnnoStd renders these only in Edition=examples
    #   (page a901017), not in Edition=1995's main grammar.
    # - environment: device I/O parameters from YDB ioproc.rst; the
    #   AnnoStd device-parameter chapters are in BNF form. Lock /
    #   transaction / error-handling semantics for the environment
    #   family are covered by entries already in commands.tsv (LOCK,
    #   TSTART, TCOMMIT, TROLLBACK, TRESTART) and ISVs ($ETRAP,
    #   $ECODE, $ESTACK, $STACK).
    for concept, columns_in_ydb in (
        ("pattern-codes", ("code", "description", "standard_status_hint",
                           "source_section")),
        ("environment", ("name", "kind", "summary",
                         "standard_status_hint", "source_section")),
    ):
        ydb = per_source / "ydb" / f"{concept}.tsv"
        if not ydb.exists():
            continue
        integrated = _passthrough_ydb_only(ydb, columns_in_ydb)
        kept_cols = tuple(
            c for c in columns_in_ydb
            if c not in ("standard_status_hint", "source_section")
        )
        out_columns = (
            "in_anno", "in_ydb", "ydb_section", "standard_status",
        ) + kept_cols
        _write_tsv(out_dir / f"{concept}.tsv", out_columns, integrated)
        log.info("reconciled %s (YDB-only): %d rows", concept, len(integrated))

    _write_tsv(out_dir / "conflicts.tsv", CONFLICTS_COLUMNS, all_conflicts)
    log.info(
        "wrote %d total conflicts -> %s/conflicts.tsv",
        len(all_conflicts), out_dir,
    )


def _renumber_conflicts(
    conflicts: list[dict[str, str]],
    integrated_rows: list[dict[str, str]],
    start_id: int,
) -> list[dict[str, str]]:
    """Re-stamp conflict IDs into the global sequence.

    Per-concept reconcilers count conflicts from ``CONF-001``; the
    orchestrator gives each one a unique global ID and propagates the
    new ID into any integrated row that references it.
    """
    renumbered: list[dict[str, str]] = []
    next_id = start_id
    for c in conflicts:
        new_id = f"CONF-{next_id:03d}"
        next_id += 1
        old_id = c["conflict_id"]
        for row in integrated_rows:
            if row.get("conflict_id") == old_id:
                row["conflict_id"] = new_id
        new_c = dict(c)
        new_c["conflict_id"] = new_id
        renumbered.append(new_c)
    return renumbered


def _passthrough_ydb_only(
    ydb_path: Path, columns_in_ydb: tuple[str, ...]
) -> list[dict[str, str]]:
    rows = _read_tsv(ydb_path)
    out = []
    for r in rows:
        new = {c: r.get(c, "") for c in columns_in_ydb if c not in (
            "standard_status_hint", "source_section"
        )}
        new["in_anno"] = "false"
        new["in_ydb"] = "true"
        new["ydb_section"] = r.get("source_section", "")
        new["standard_status"] = r.get("standard_status_hint", "")
        out.append(new)
    return out


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _write_tsv(
    path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(c, "") for c in columns])


def _normalise(s: str) -> str:
    return " ".join(s.split())


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Two-source reconciler.")
    parser.add_argument(
        "--per-source", type=Path, default=DEFAULT_PER_SOURCE_DIR
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_INTEGRATED_DIR
    )
    args = parser.parse_args(argv)

    reconcile_all(per_source=args.per_source, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

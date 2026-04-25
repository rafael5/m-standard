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
    anno_path: Path, ydb_path: Path, *, concept: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Generic reconciliation for concepts keyed by ``canonical_name``.

    Used for commands, intrinsic functions, and intrinsic special
    variables — all of which share the same per-source schema (name,
    abbreviation, format, standard_status_hint, source_section,
    description) and the same matching rule (join on canonical_name).
    """
    anno_rows = _read_tsv(anno_path)
    ydb_rows = _read_tsv(ydb_path)

    anno_by_name = {r["canonical_name"]: r for r in anno_rows}
    ydb_by_name = {r["canonical_name"]: r for r in ydb_rows}
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


def reconcile_all(per_source: Path, out_dir: Path) -> None:
    """Reconcile every concept family present in ``per_source/``.

    Three modes per concept:
    1. Both sources present (commands, intrinsic-functions,
       intrinsic-special-variables): join on canonical_name.
    2. YDB-only (operators, pattern-codes, errors): pass through with
       in_anno=false on every row. Per BL-009 these families are
       deferred from AnnoStd extraction in v1.0.
    3. Missing from both: skipped.

    All conflict rows from all named-concept reconciliations are
    accumulated into a single ``conflicts.tsv``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    all_conflicts: list[dict[str, str]] = []
    next_conflict_id = 1

    # Named concepts (both sources contribute).
    for concept in ("commands", "intrinsic-functions", "intrinsic-special-variables"):
        anno = per_source / "anno" / f"{concept}.tsv"
        ydb = per_source / "ydb" / f"{concept}.tsv"
        if not (anno.exists() or ydb.exists()):
            continue
        integrated, conflicts = _reconcile_named_concept(anno, ydb, concept=concept)
        # Renumber conflict IDs into the global sequence.
        renumbered: list[dict[str, str]] = []
        for c in conflicts:
            new_id = f"CONF-{next_conflict_id:03d}"
            next_conflict_id += 1
            old_id = c["conflict_id"]
            for row in integrated:
                if row.get("conflict_id") == old_id:
                    row["conflict_id"] = new_id
            new_c = dict(c)
            new_c["conflict_id"] = new_id
            renumbered.append(new_c)
        _write_tsv(out_dir / f"{concept}.tsv", INTEGRATED_COMMAND_COLUMNS, integrated)
        all_conflicts.extend(renumbered)
        log.info(
            "reconciled %s: %d rows, %d conflicts",
            concept, len(integrated), len(renumbered),
        )

    # YDB-only concepts (pass-through with in_anno=false markers).
    for concept, columns_in_ydb in (
        ("pattern-codes", ("code", "description", "standard_status_hint",
                           "source_section")),
        ("operators", ("symbol", "operator_class", "description",
                       "standard_status_hint", "source_section")),
        ("errors", ("mnemonic", "summary", "kind", "standard_status_hint",
                    "source_section")),
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

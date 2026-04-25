"""Tests for the two-source reconciler.

The reconciler joins per-source TSVs by canonical_name and produces an
integrated TSV plus rows in conflicts.tsv. Per AD-01:

- AnnoStd is normative for "is X part of the standard".
- YDB is authoritative for current implementation detail.
- Anything in YDB but not in AnnoStd is a YDB extension.
- Anything in AnnoStd but not in YDB is a *standard-but-unimplemented*
  signal — recorded as a conflict with kind=existence.
- Same name in both, divergent abbreviation or format, is a conflict
  with kind=definition.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.reconcile import reconcile_commands


def _write(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""))


ANNO_HEADER = (
    "canonical_name\tabbreviation\tsection_number\tformat\t"
    "standard_status_hint\tsource_section\tdescription"
)
YDB_HEADER = (
    "canonical_name\tabbreviation\tformat\tstandard_status_hint\t"
    "source_section\tdescription"
)


def _setup(tmp_path: Path, anno_rows: list[str], ydb_rows: list[str]) -> tuple[Path, Path]:
    anno = tmp_path / "per-source" / "anno" / "commands.tsv"
    ydb = tmp_path / "per-source" / "ydb" / "commands.tsv"
    _write(anno, ANNO_HEADER, anno_rows)
    _write(ydb, YDB_HEADER, ydb_rows)
    return anno, ydb


def test_reconcile_commands_present_in_both_sources(tmp_path: Path) -> None:
    anno, ydb = _setup(
        tmp_path,
        anno_rows=[
            "BREAK\tB\t8.2.1\tB[REAK] postcond\tansi\tpages/a108024.html#8.2.1\tBreak provides..."
        ],
        ydb_rows=[
            "BREAK\tB\tB[REAK][:tvexpr] [expr[:tvexpr][,...]]\tansi\tProgrammersGuide/commands.rst#Break\tThe BREAK..."
        ],
    )
    integrated, conflicts = reconcile_commands(anno_path=anno, ydb_path=ydb)
    by_name = {r["canonical_name"]: r for r in integrated}
    assert by_name["BREAK"]["in_anno"] == "true"
    assert by_name["BREAK"]["in_ydb"] == "true"
    assert by_name["BREAK"]["standard_status"] == "ansi"
    # Abbreviation comes from the source that has it (both agree here).
    assert by_name["BREAK"]["abbreviation"] == "B"
    # No conflict because the entry exists in both with no contradictions.
    assert by_name["BREAK"]["conflict_id"] == ""
    assert conflicts == []


def test_reconcile_commands_ydb_only_is_extension(tmp_path: Path) -> None:
    anno, ydb = _setup(
        tmp_path,
        anno_rows=[],
        ydb_rows=[
            "ZBREAK\tZB\tZB[REAK][:tvexpr]\tydb-extension\tProgrammersGuide/commands.rst#ZBREAK\tInsert temp BREAK"
        ],
    )
    integrated, conflicts = reconcile_commands(anno_path=anno, ydb_path=ydb)
    by_name = {r["canonical_name"]: r for r in integrated}
    assert by_name["ZBREAK"]["in_anno"] == "false"
    assert by_name["ZBREAK"]["in_ydb"] == "true"
    assert by_name["ZBREAK"]["standard_status"] == "ydb-extension"
    assert by_name["ZBREAK"]["conflict_id"] == ""
    # Z-extension presence in YDB without AnnoStd is expected, not a
    # conflict.
    assert conflicts == []


def test_reconcile_commands_anno_only_is_existence_conflict(tmp_path: Path) -> None:
    anno, ydb = _setup(
        tmp_path,
        anno_rows=[
            "ABLOCK\tAB\t8.2.1\tAB[LOCK]\tansi\tpages/a108019.html#8.2.1\tAsync block."
        ],
        ydb_rows=[],
    )
    integrated, conflicts = reconcile_commands(anno_path=anno, ydb_path=ydb)
    by_name = {r["canonical_name"]: r for r in integrated}
    assert by_name["ABLOCK"]["in_anno"] == "true"
    assert by_name["ABLOCK"]["in_ydb"] == "false"
    assert by_name["ABLOCK"]["standard_status"] == "ansi"  # AnnoStd says so
    assert by_name["ABLOCK"]["conflict_id"] != ""
    # And there's a conflict row for it.
    assert len(conflicts) == 1
    assert conflicts[0]["kind"] == "existence"
    assert conflicts[0]["entry"] == "ABLOCK"
    assert conflicts[0]["resolution_basis"].startswith("AD-01")


def test_reconcile_commands_definition_conflict_on_abbreviation(
    tmp_path: Path,
) -> None:
    """A real definition conflict: the two sources disagree on the
    canonical abbreviation. This is rare in practice but exactly what
    the conflict mechanism is for. Format strings differ between every
    pair of sources because the two corpora use different metalanguages
    (AnnoStd: ``postcond``/``SP``; YDB: ``[:tvexpr]``); v1.0 does not
    flag those as conflicts because semantic normalisation between the
    two metalanguages is out of scope."""
    anno, ydb = _setup(
        tmp_path,
        anno_rows=[
            "READ\tR\t8.2.17\tR[EAD] (glvn)\tansi\tpages/a108045.html#8.2.17\tRead."
        ],
        ydb_rows=[
            # YDB disagrees on abbreviation (RD vs R) — synthetic case.
            "READ\tRD\tRD[EAD][:tvexpr] glvn[,...]\tansi\tProgrammersGuide/commands.rst#READ\tThe READ command..."
        ],
    )
    integrated, conflicts = reconcile_commands(anno_path=anno, ydb_path=ydb)
    by_name = {r["canonical_name"]: r for r in integrated}
    assert by_name["READ"]["conflict_id"] != ""
    assert any(c["kind"] == "definition" for c in conflicts)


def test_reconcile_commands_does_not_flag_metalanguage_format_diffs(
    tmp_path: Path,
) -> None:
    """When AnnoStd writes ``postcond`` and YDB writes ``[:tvexpr]``,
    the strings differ verbatim but mean the same thing. v1.0 of the
    reconciler does not flag these as conflicts."""
    anno, ydb = _setup(
        tmp_path,
        anno_rows=[
            "READ\tR\t8.2.17\tR[EAD] postcond (glvn)\tansi\tanno_ref\tRead."
        ],
        ydb_rows=[
            "READ\tR\tR[EAD][:tvexpr] glvn[,...]\tansi\tydb_ref\tThe READ command..."
        ],
    )
    integrated, conflicts = reconcile_commands(anno_path=anno, ydb_path=ydb)
    by_name = {r["canonical_name"]: r for r in integrated}
    assert by_name["READ"]["conflict_id"] == ""
    assert conflicts == []


def test_reconcile_is_deterministic(tmp_path: Path) -> None:
    anno, ydb = _setup(
        tmp_path,
        anno_rows=[
            "BREAK\tB\t8.2.1\tB[REAK]\tansi\tanno_ref\td1",
            "ABLOCK\tAB\t8.2.1\tAB[LOCK]\tansi\tanno_ref\td2",
        ],
        ydb_rows=[
            "BREAK\tB\tB[REAK]\tansi\tydb_ref\td1",
            "ZBREAK\tZB\tZB[REAK]\tydb-extension\tydb_ref\td2",
        ],
    )
    integrated_a, conflicts_a = reconcile_commands(anno_path=anno, ydb_path=ydb)
    integrated_b, conflicts_b = reconcile_commands(anno_path=anno, ydb_path=ydb)
    assert integrated_a == integrated_b
    assert conflicts_a == conflicts_b


def test_reconcile_writes_integrated_and_conflicts_tsvs(tmp_path: Path) -> None:
    from m_standard.tools.reconcile import reconcile_commands_to_tsv

    anno, ydb = _setup(
        tmp_path,
        anno_rows=[
            "BREAK\tB\t8.2.1\tB[REAK]\tansi\tanno_ref\tDescription."
        ],
        ydb_rows=[
            "BREAK\tB\tB[REAK]\tansi\tydb_ref\tDescription."
        ],
    )
    out_dir = tmp_path / "integrated"
    reconcile_commands_to_tsv(
        anno_path=anno,
        ydb_path=ydb,
        out_dir=out_dir,
    )
    assert (out_dir / "commands.tsv").exists()
    assert (out_dir / "conflicts.tsv").exists()
    rows = (out_dir / "commands.tsv").read_text().splitlines()
    header = rows[0].split("\t")
    assert "in_anno" in header
    assert "in_ydb" in header
    assert "standard_status" in header
    assert "conflict_id" in header

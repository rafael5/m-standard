"""Tests for the grammar-surface emitter (spec §10.1).

The grammar surface is the bundle that ``tree-sitter-m`` (and any
other consumer that needs to recognise M tokens) reads at build
time. It's derived deterministically from the integrated layer; no
extra hand-curation involved.

The key transformation is **abbreviation prefix expansion**: M
commands like ``BREAK`` accept any prefix of the canonical name
that's at least as long as the abbreviation. ``BREAK`` with
abbreviation ``B`` admits ``B``, ``BR``, ``BRE``, ``BREA``, ``BREAK``.
The grammar consumer needs the full set, not just the canonical
name + shortest abbreviation.
"""

from __future__ import annotations

import json
from pathlib import Path

from m_standard.tools.emit_grammar import (
    all_forms,
    emit_grammar_surface,
)


def test_all_forms_expands_command(tmp_path: Path) -> None:
    """B[REAK] admits 5 forms: B, BR, BRE, BREA, BREAK."""
    assert all_forms("BREAK", "B") == ["B", "BR", "BRE", "BREA", "BREAK"]


def test_all_forms_expands_function() -> None:
    """$A[SCII] admits $A, $AS, $ASC, $ASCI, $ASCII."""
    assert all_forms("$ASCII", "$A") == [
        "$A", "$AS", "$ASC", "$ASCI", "$ASCII",
    ]


def test_all_forms_no_abbreviation_returns_canonical_only() -> None:
    """Some AnnoStd entries have no abbreviation recorded."""
    assert all_forms("BREAK", "") == ["BREAK"]


def test_all_forms_abbreviation_equals_canonical() -> None:
    """ELSE with abbreviation E[LSE] but if abbreviation==canonical."""
    assert all_forms("ELSE", "ELSE") == ["ELSE"]


def test_all_forms_abbreviation_not_a_prefix_returns_canonical_only() -> None:
    """Defensive: if data is wonky, fall back to canonical."""
    assert all_forms("BREAK", "Q") == ["BREAK"]


def test_all_forms_z_extension() -> None:
    """ZB[REAK] admits ZB, ZBR, ZBRE, ZBREA, ZBREAK."""
    assert all_forms("ZBREAK", "ZB") == [
        "ZB", "ZBR", "ZBRE", "ZBREA", "ZBREAK",
    ]


def _write_tsv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""))


CMD_HEADER = (
    "canonical_name\tabbreviation\tformat\tstandard_status\t"
    "in_anno\tin_ydb\tin_iris\tanno_section\tydb_section\t"
    "iris_section\tconflict_id\tnotes"
)
FN_HEADER = CMD_HEADER  # same shape
ISV_HEADER = CMD_HEADER
OP_HEADER = (
    "symbol\toperator_class\tdescription\tstandard_status\t"
    "in_anno\tin_ydb\tanno_section\tydb_section\tconflict_id\tnotes"
)
PATCODE_HEADER = (
    "in_anno\tin_ydb\tydb_section\tstandard_status\tcode\tdescription"
)


def _scaffold_integrated(tmp_path: Path) -> Path:
    integrated = tmp_path / "integrated"
    _write_tsv(
        integrated / "commands.tsv", CMD_HEADER,
        [
            "BREAK\tB\tFMT\tansi\ttrue\ttrue\ttrue\ta\ty\ti\t\t",
            "ZBREAK\tZB\tFMT\tydb-extension\tfalse\ttrue\tfalse\t\ty\t\t\t",
        ],
    )
    _write_tsv(
        integrated / "intrinsic-functions.tsv", FN_HEADER,
        ["$ASCII\t$A\tFMT\tansi\ttrue\ttrue\ttrue\ta\ty\ti\t\t"],
    )
    _write_tsv(
        integrated / "intrinsic-special-variables.tsv", ISV_HEADER,
        ["$DEVICE\t$D\tFMT\tansi\ttrue\ttrue\ttrue\ta\ty\ti\t\t"],
    )
    _write_tsv(
        integrated / "operators.tsv", OP_HEADER,
        ["+\tarithmetic\tdesc\tansi\ttrue\ttrue\ta\ty\t\t"],
    )
    _write_tsv(
        integrated / "pattern-codes.tsv", PATCODE_HEADER,
        ["false\ttrue\ty\tansi\tA\tdesc"],
    )
    return integrated


def test_emit_grammar_surface_writes_single_json(tmp_path: Path) -> None:
    integrated = _scaffold_integrated(tmp_path)
    out = tmp_path / "grammar-surface.json"
    schema = Path("schemas") / "grammar-surface.schema.json"
    emit_grammar_surface(integrated_dir=integrated, out=out, schema_path=schema)
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1"
    assert data["concept"] == "grammar-surface"
    assert {"commands", "intrinsic_functions", "intrinsic_special_variables",
            "operators", "pattern_codes"} <= set(data.keys())


def test_emit_grammar_surface_expands_all_forms(tmp_path: Path) -> None:
    integrated = _scaffold_integrated(tmp_path)
    out = tmp_path / "grammar-surface.json"
    schema = Path("schemas") / "grammar-surface.schema.json"
    emit_grammar_surface(integrated_dir=integrated, out=out, schema_path=schema)
    data = json.loads(out.read_text())
    by_name = {c["canonical"]: c for c in data["commands"]}
    assert by_name["BREAK"]["all_forms"] == ["B", "BR", "BRE", "BREA", "BREAK"]
    assert by_name["BREAK"]["abbreviation"] == "B"
    assert by_name["BREAK"]["standard_status"] == "ansi"


def test_emit_grammar_surface_carries_standard_status(tmp_path: Path) -> None:
    integrated = _scaffold_integrated(tmp_path)
    out = tmp_path / "grammar-surface.json"
    schema = Path("schemas") / "grammar-surface.schema.json"
    emit_grammar_surface(integrated_dir=integrated, out=out, schema_path=schema)
    data = json.loads(out.read_text())
    by_name = {c["canonical"]: c for c in data["commands"]}
    assert by_name["ZBREAK"]["standard_status"] == "ydb-extension"
    assert by_name["BREAK"]["standard_status"] == "ansi"


def test_emit_grammar_surface_is_deterministic(tmp_path: Path) -> None:
    integrated = _scaffold_integrated(tmp_path)
    schema = Path("schemas") / "grammar-surface.schema.json"
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    emit_grammar_surface(integrated_dir=integrated, out=out_a, schema_path=schema)
    emit_grammar_surface(integrated_dir=integrated, out=out_b, schema_path=schema)
    assert out_a.read_bytes() == out_b.read_bytes()


def test_emit_grammar_surface_orders_within_each_section(tmp_path: Path) -> None:
    """Within each concept section, entries are sorted by canonical name."""
    integrated = _scaffold_integrated(tmp_path)
    schema = Path("schemas") / "grammar-surface.schema.json"
    out = tmp_path / "grammar-surface.json"
    emit_grammar_surface(integrated_dir=integrated, out=out, schema_path=schema)
    data = json.loads(out.read_text())
    canonicals = [c["canonical"] for c in data["commands"]]
    assert canonicals == sorted(canonicals)

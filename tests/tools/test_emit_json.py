"""Tests for the TSV → JSON emitter (spec §6.3 + §7.3).

The emitter reads each integrated TSV and writes a corresponding JSON
file containing schema_version + concept + entries[]. Strings like
"true"/"false" become real booleans; empty conflict_id becomes null.
Output validates against the schema in schemas/.
"""

from __future__ import annotations

import json
from pathlib import Path

from m_standard.tools.emit_json import (
    emit_concept_json,
    tsv_row_to_entry,
)


def _write_tsv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""))


_HEADER = (
    "canonical_name\tabbreviation\tformat\tstandard_status\t"
    "in_anno\tin_ydb\tanno_section\tydb_section\tconflict_id\tnotes"
)


def test_tsv_row_to_entry_typed_conversions() -> None:
    row = {
        "canonical_name": "BREAK",
        "abbreviation": "B",
        "format": "B[REAK][:tvexpr]",
        "standard_status": "ansi",
        "in_anno": "true",
        "in_ydb": "true",
        "anno_section": "pages/a108024.html#8.2.1",
        "ydb_section": "ProgrammersGuide/commands.rst#Break",
        "conflict_id": "",
        "notes": "",
    }
    entry = tsv_row_to_entry(row)
    # Booleans are typed.
    assert entry["in_anno"] is True
    assert entry["in_ydb"] is True
    # Empty conflict_id becomes null (not empty string).
    assert entry["conflict_id"] is None
    # Other strings pass through verbatim.
    assert entry["canonical_name"] == "BREAK"
    assert entry["abbreviation"] == "B"


def test_tsv_row_to_entry_preserves_conflict_id_when_present() -> None:
    row = {
        "canonical_name": "ABLOCK",
        "abbreviation": "AB",
        "format": "AB[LOCK]",
        "standard_status": "ansi",
        "in_anno": "true",
        "in_ydb": "false",
        "anno_section": "pages/a108019.html#8.2.1",
        "ydb_section": "",
        "conflict_id": "CONF-001",
        "notes": "",
    }
    entry = tsv_row_to_entry(row)
    assert entry["conflict_id"] == "CONF-001"
    assert entry["in_ydb"] is False


def test_emit_concept_json_writes_schema_versioned_file(tmp_path: Path) -> None:
    tsv = tmp_path / "commands.tsv"
    _write_tsv(
        tsv, _HEADER,
        ["BREAK\tB\tB[REAK][:tvexpr]\tansi\ttrue\ttrue\tanno_ref\tydb_ref\t\t"],
    )
    out = tmp_path / "commands.json"
    schema = Path("schemas") / "command.schema.json"
    emit_concept_json(
        tsv_path=tsv,
        json_path=out,
        concept="commands",
        schema_path=schema,
    )
    data = json.loads(out.read_text())
    assert data["schema_version"] == "1"
    assert data["concept"] == "commands"
    assert isinstance(data["entries"], list)
    assert data["entries"][0]["canonical_name"] == "BREAK"
    assert data["entries"][0]["in_anno"] is True


def test_emit_concept_json_validates_against_schema(tmp_path: Path) -> None:
    """Emitter raises a clear error when the output would not validate."""
    import pytest

    tsv = tmp_path / "commands.tsv"
    _write_tsv(
        tsv, _HEADER,
        # Corrupt: standard_status not in enum.
        ["BREAK\tB\tFMT\tnot-a-real-status\ttrue\ttrue\ta\tb\t\t"],
    )
    out = tmp_path / "commands.json"
    schema = Path("schemas") / "command.schema.json"
    with pytest.raises(Exception) as exc:
        emit_concept_json(
            tsv_path=tsv,
            json_path=out,
            concept="commands",
            schema_path=schema,
        )
    assert "standard_status" in str(exc.value) or "enum" in str(exc.value)


def test_emit_concept_json_one_entry_per_tsv_row(tmp_path: Path) -> None:
    tsv = tmp_path / "commands.tsv"
    _write_tsv(
        tsv, _HEADER,
        [
            "BREAK\tB\tB[REAK]\tansi\ttrue\ttrue\ta\tb\t\t",
            "ZBREAK\tZB\tZB[REAK]\tydb-extension\tfalse\ttrue\t\tb\t\t",
        ],
    )
    out = tmp_path / "commands.json"
    schema = Path("schemas") / "command.schema.json"
    emit_concept_json(
        tsv_path=tsv,
        json_path=out,
        concept="commands",
        schema_path=schema,
    )
    data = json.loads(out.read_text())
    assert len(data["entries"]) == 2
    names = [e["canonical_name"] for e in data["entries"]]
    assert names == sorted(names)


def test_emit_concept_json_is_deterministic(tmp_path: Path) -> None:
    tsv = tmp_path / "commands.tsv"
    _write_tsv(
        tsv, _HEADER,
        [
            "BREAK\tB\tB[REAK]\tansi\ttrue\ttrue\ta\tb\t\t",
            "DO\tD\tD[O]\tansi\ttrue\ttrue\ta\tb\t\t",
        ],
    )
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    schema = Path("schemas") / "command.schema.json"
    emit_concept_json(tsv_path=tsv, json_path=out_a, concept="commands",
                      schema_path=schema)
    emit_concept_json(tsv_path=tsv, json_path=out_b, concept="commands",
                      schema_path=schema)
    assert out_a.read_bytes() == out_b.read_bytes()

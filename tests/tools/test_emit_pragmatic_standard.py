"""Tests for the pragmatic-M-standard emitter.

The pragmatic standard is the tiered output answering:
"what M language surface can a VistA developer write that runs
unmodified on both YottaDB and InterSystems IRIS?"

Tiers per concept entry:
- ``core``: present in BOTH YDB and IRIS — safe for cross-engine
  VistA development, regardless of AnnoStd presence.
- ``ydb-only``: present in YDB, absent in IRIS — avoid for
  IRIS-targeting code; use a cross-vendor analogue if one exists.
- ``iris-only``: present in IRIS, absent in YDB — avoid for
  YDB-targeting code.
- ``ansi-unimplemented``: AnnoStd documents it but neither vendor
  implements it (existence conflicts) — historical; do not use.
"""

from __future__ import annotations

import json
from pathlib import Path

from m_standard.tools.emit_pragmatic_standard import (
    derive_tier,
    emit_pragmatic_standard,
)


def test_derive_tier_core_when_both_implementations(tmp_path: Path) -> None:
    """Both vendors → core, regardless of AnnoStd presence."""
    assert derive_tier(in_anno=True,  in_ydb=True,  in_iris=True)  == "core"
    assert derive_tier(in_anno=False, in_ydb=True,  in_iris=True)  == "core"


def test_derive_tier_vendor_only(tmp_path: Path) -> None:
    assert derive_tier(in_anno=True,  in_ydb=True,  in_iris=False) == "ydb-only"
    assert derive_tier(in_anno=False, in_ydb=True,  in_iris=False) == "ydb-only"
    assert derive_tier(in_anno=True,  in_ydb=False, in_iris=True)  == "iris-only"
    assert derive_tier(in_anno=False, in_ydb=False, in_iris=True)  == "iris-only"


def test_derive_tier_ansi_unimplemented(tmp_path: Path) -> None:
    """In standard, neither vendor implements it."""
    assert derive_tier(in_anno=True, in_ydb=False, in_iris=False) == "ansi-unimplemented"


def _write_tsv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""))


CMD_HEADER = (
    "canonical_name\tabbreviation\tformat\tstandard_status\t"
    "in_anno\tin_ydb\tin_iris\tanno_section\tydb_section\t"
    "iris_section\tconflict_id\tnotes"
)


def _scaffold(tmp_path: Path) -> Path:
    integrated = tmp_path / "integrated"
    _write_tsv(
        integrated / "commands.tsv", CMD_HEADER,
        [
            # Core: BREAK in all three sources.
            "BREAK\tB\tFMT\tansi\ttrue\ttrue\ttrue\ta\ty\ti\t\t",
            # Core (multi-vendor de-facto): ZWRITE in YDB+IRIS, not Anno.
            "ZWRITE\tZWR\tFMT\tmulti-vendor-ext\tfalse\ttrue\ttrue\t\ty\ti\t\t",
            # YDB-only: ZTRIGGER.
            "ZTRIGGER\tZTR\tFMT\tydb-extension\tfalse\ttrue\tfalse\t\ty\t\t\t",
            # IRIS-only: CATCH.
            "CATCH\t\tFMT\tiris-extension\tfalse\tfalse\ttrue\t\t\ti\t\t",
            # Standard but unimplemented: ABLOCK.
            "ABLOCK\tAB\tFMT\tansi\ttrue\tfalse\tfalse\ta\t\t\tCONF-001\t",
        ],
    )
    _write_tsv(
        integrated / "intrinsic-functions.tsv", CMD_HEADER,
        ["$ASCII\t$A\tFMT\tansi\ttrue\ttrue\ttrue\ta\ty\ti\t\t"],
    )
    _write_tsv(
        integrated / "intrinsic-special-variables.tsv", CMD_HEADER,
        ["$DEVICE\t$D\tFMT\tansi\ttrue\ttrue\ttrue\ta\ty\ti\t\t"],
    )
    return integrated


def test_emit_pragmatic_standard_writes_tsv_and_json(tmp_path: Path) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "pragmatic-m-standard.schema.json"
    tsv_out = tmp_path / "pragmatic.tsv"
    json_out = tmp_path / "pragmatic.json"
    emit_pragmatic_standard(
        integrated_dir=integrated,
        tsv_out=tsv_out,
        json_out=json_out,
        schema_path=schema,
    )
    rows = tsv_out.read_text().splitlines()
    assert rows[0].split("\t") == [
        "concept", "name", "pragmatic_tier", "standard_status",
        "in_anno", "in_ydb", "in_iris",
        "anno_section", "ydb_section", "iris_section",
    ]
    data = json.loads(json_out.read_text())
    assert data["schema_version"] == "1"
    assert data["concept"] == "pragmatic-m-standard"


def test_emit_pragmatic_standard_classifies_each_entry(tmp_path: Path) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "pragmatic-m-standard.schema.json"
    tsv_out = tmp_path / "pragmatic.tsv"
    json_out = tmp_path / "pragmatic.json"
    emit_pragmatic_standard(
        integrated_dir=integrated,
        tsv_out=tsv_out,
        json_out=json_out,
        schema_path=schema,
    )
    data = json.loads(json_out.read_text())
    by_name = {e["name"]: e for e in data["entries"]}
    assert by_name["BREAK"]["pragmatic_tier"] == "core"
    assert by_name["ZWRITE"]["pragmatic_tier"] == "core"
    assert by_name["ZTRIGGER"]["pragmatic_tier"] == "ydb-only"
    assert by_name["CATCH"]["pragmatic_tier"] == "iris-only"
    assert by_name["ABLOCK"]["pragmatic_tier"] == "ansi-unimplemented"


def test_emit_pragmatic_standard_summarises_counts(tmp_path: Path) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "pragmatic-m-standard.schema.json"
    json_out = tmp_path / "pragmatic.json"
    emit_pragmatic_standard(
        integrated_dir=integrated,
        tsv_out=tmp_path / "pragmatic.tsv",
        json_out=json_out,
        schema_path=schema,
    )
    data = json.loads(json_out.read_text())
    assert data["counts"]["core"] >= 4  # BREAK, ZWRITE, $ASCII, $DEVICE
    assert data["counts"]["ydb-only"] >= 1
    assert data["counts"]["iris-only"] >= 1
    assert data["counts"]["ansi-unimplemented"] >= 1


def test_emit_pragmatic_standard_is_deterministic(tmp_path: Path) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "pragmatic-m-standard.schema.json"
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    emit_pragmatic_standard(
        integrated_dir=integrated, tsv_out=tmp_path / "ta.tsv",
        json_out=a, schema_path=schema,
    )
    emit_pragmatic_standard(
        integrated_dir=integrated, tsv_out=tmp_path / "tb.tsv",
        json_out=b, schema_path=schema,
    )
    assert a.read_bytes() == b.read_bytes()

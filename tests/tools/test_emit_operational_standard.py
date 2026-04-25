"""Tests for the operational M standard emitter.

The operational standard is the intersection: portable across both
engines (pragmatic-core) AND not blocked by VA policy (SAC-clean).
It's what VistA developers can actually write — both technically
runs everywhere AND passes XINDEX.
"""

from __future__ import annotations

import json
from pathlib import Path

from m_standard.tools.emit_operational_standard import (
    derive_operational,
    emit_operational_standard,
)


def test_derive_operational_includes_portable_and_sac_silent() -> None:
    """Pragmatic-core + SAC silent (XINDEX doesn't mention) = operational."""
    assert derive_operational(pragmatic_tier="core", sac_status="") is True


def test_derive_operational_includes_portable_and_sac_permitted() -> None:
    assert derive_operational(pragmatic_tier="core", sac_status="permitted") is True
    assert derive_operational(pragmatic_tier="core", sac_status="recommended") is True


def test_derive_operational_excludes_portable_but_sac_blocks() -> None:
    """Portable but SAC bans for policy reasons = NOT operational."""
    assert derive_operational(pragmatic_tier="core", sac_status="forbidden") is False
    assert derive_operational(pragmatic_tier="core", sac_status="restricted") is False


def test_derive_operational_excludes_unportable() -> None:
    """Vendor-specific entries are never operational regardless of SAC."""
    assert derive_operational(pragmatic_tier="ydb-only", sac_status="") is False
    assert derive_operational(pragmatic_tier="iris-only", sac_status="permitted") is False
    assert derive_operational(
        pragmatic_tier="ansi-unimplemented", sac_status=""
    ) is False


def _write_tsv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""))


def _scaffold(tmp_path: Path) -> Path:
    integrated = tmp_path / "integrated"
    _write_tsv(
        integrated / "pragmatic-m-standard.tsv",
        "concept\tname\tpragmatic_tier\tstandard_status\t"
        "in_anno\tin_ydb\tin_iris\tanno_section\tydb_section\tiris_section",
        [
            "commands\tDO\tcore\tansi\ttrue\ttrue\ttrue\ta\ty\ti",
            "commands\tBREAK\tcore\tansi\ttrue\ttrue\ttrue\ta\ty\ti",
            "commands\tZWRITE\tcore\tmulti-vendor-ext\tfalse\ttrue\ttrue\t\ty\ti",
            "commands\tCATCH\tiris-only\tiris-extension\tfalse\tfalse\ttrue\t\t\ti",
            "commands\tABLOCK\tansi-unimplemented\tansi\ttrue\tfalse\tfalse\ta\t\t",
        ],
    )
    _write_tsv(
        integrated / "va-sac-compliance.tsv",
        "concept\tname\tpragmatic_tier\tsac_status\tconcern\tsac_section\tnotes",
        [
            "commands\tDO\tcore\t\tsac_silent_on_portable\t\t",
            "commands\tBREAK\tcore\tforbidden\tsac_says_avoid_but_portable\tXINDEX rule 25\tBreak.",
            "commands\tZWRITE\tcore\tforbidden\tsac_says_avoid_but_portable\tXINDEX rule 2\tZ command.",
            "commands\tCATCH\tiris-only\t\tsac_silent_on_unportable\t\t",
            "commands\tABLOCK\tansi-unimplemented\t\tsac_silent_on_unportable\t\t",
        ],
    )
    return integrated


def test_emit_operational_standard_filters_to_pragmatic_and_sac_clean(
    tmp_path: Path,
) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "operational-m-standard.schema.json"
    tsv_out = tmp_path / "op.tsv"
    json_out = tmp_path / "op.json"
    emit_operational_standard(
        integrated_dir=integrated,
        tsv_out=tsv_out,
        json_out=json_out,
        schema_path=schema,
    )
    data = json.loads(json_out.read_text())
    names = sorted(e["name"] for e in data["entries"])
    # Only DO is operational: portable + SAC-silent.
    # BREAK and ZWRITE: portable but SAC-forbidden → excluded.
    # CATCH, ABLOCK: not portable → excluded.
    assert names == ["DO"]


def test_emit_operational_standard_summarises_counts(tmp_path: Path) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "operational-m-standard.schema.json"
    json_out = tmp_path / "op.json"
    emit_operational_standard(
        integrated_dir=integrated,
        tsv_out=tmp_path / "op.tsv",
        json_out=json_out,
        schema_path=schema,
    )
    data = json.loads(json_out.read_text())
    assert data["counts"]["operational"] == 1
    assert data["counts"]["pragmatic_blocked_by_sac"] == 2
    # Total intake from pragmatic = 3 core + 1 iris-only + 1 anno-unimp = 5
    assert data["counts"]["pragmatic_core_total"] == 3


def test_emit_operational_standard_writes_tsv_columns(tmp_path: Path) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "operational-m-standard.schema.json"
    tsv_out = tmp_path / "op.tsv"
    emit_operational_standard(
        integrated_dir=integrated,
        tsv_out=tsv_out,
        json_out=tmp_path / "op.json",
        schema_path=schema,
    )
    rows = tsv_out.read_text(encoding="utf-8").splitlines()
    assert rows[0].split("\t") == [
        "concept", "name", "in_anno", "in_ydb", "in_iris",
        "anno_section", "ydb_section", "iris_section",
    ]


def test_emit_operational_standard_is_deterministic(tmp_path: Path) -> None:
    integrated = _scaffold(tmp_path)
    schema = Path("schemas") / "operational-m-standard.schema.json"
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    emit_operational_standard(
        integrated_dir=integrated, tsv_out=tmp_path / "ta.tsv",
        json_out=a, schema_path=schema,
    )
    emit_operational_standard(
        integrated_dir=integrated, tsv_out=tmp_path / "tb.tsv",
        json_out=b, schema_path=schema,
    )
    assert a.read_bytes() == b.read_bytes()

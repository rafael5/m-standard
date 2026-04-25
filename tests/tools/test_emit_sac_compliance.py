"""Tests for the SAC-vs-pragmatic compliance emitter.

The compliance emitter joins the VA Standards and Conventions
overlay (``mappings/va-sac.tsv``) against the pragmatic M standard
(``integrated/pragmatic-m-standard.tsv``) to surface four
portability concerns:

- ``sac_says_use_but_not_portable``: SAC permits/recommends an
  entry that pragmatic-core doesn't include (one engine doesn't
  have it). VistA code following SAC literally would break on
  the missing engine.
- ``sac_says_avoid_but_portable``: SAC forbids an entry that's in
  pragmatic-core. Possibly SAC is overly conservative or the
  entry was added to both engines after SAC was written.
- ``sac_silent_on_portable``: SAC doesn't mention an entry that's
  pragmatic-core. Probably safe but unguided.
- ``aligned``: SAC and pragmatic agree.
"""

from __future__ import annotations

import json
from pathlib import Path

from m_standard.tools.emit_sac_compliance import (
    classify_concern,
    emit_sac_compliance,
)


def test_classify_concern_aligned() -> None:
    """SAC permits a portable entry — fully aligned."""
    assert classify_concern("permitted", "core") == "aligned"
    assert classify_concern("recommended", "core") == "aligned"
    # SAC forbids an unportable entry — also aligned.
    assert classify_concern("forbidden", "ydb-only") == "aligned"
    assert classify_concern("forbidden", "iris-only") == "aligned"


def test_classify_concern_sac_says_use_but_not_portable() -> None:
    """SAC permits/recommends but the entry isn't portable."""
    assert classify_concern("permitted", "ydb-only") == "sac_says_use_but_not_portable"
    assert classify_concern("permitted", "iris-only") == "sac_says_use_but_not_portable"
    assert classify_concern("recommended", "ydb-only") == "sac_says_use_but_not_portable"


def test_classify_concern_sac_says_avoid_but_portable() -> None:
    """SAC forbids/restricts an entry that's in pragmatic-core."""
    assert classify_concern("forbidden", "core") == "sac_says_avoid_but_portable"
    assert classify_concern("restricted", "core") == "sac_says_avoid_but_portable"


def test_classify_concern_sac_silent() -> None:
    """No SAC entry — silent on the question."""
    assert classify_concern("", "core") == "sac_silent_on_portable"
    assert classify_concern("", "ydb-only") == "sac_silent_on_unportable"


def _write_tsv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""))


def _scaffold(tmp_path: Path) -> tuple[Path, Path]:
    integrated = tmp_path / "integrated"
    _write_tsv(
        integrated / "pragmatic-m-standard.tsv",
        "concept\tname\tpragmatic_tier\tstandard_status\t"
        "in_anno\tin_ydb\tin_iris\tanno_section\tydb_section\tiris_section",
        [
            "commands\tBREAK\tcore\tansi\ttrue\ttrue\ttrue\ta\ty\ti",
            "commands\tZTRIGGER\tydb-only\tydb-extension\tfalse\ttrue\tfalse\t\ty\t",
            "commands\tCATCH\tiris-only\tiris-extension\tfalse\tfalse\ttrue\t\t\ti",
            "commands\tZWRITE\tcore\tmulti-vendor-ext\tfalse\ttrue\ttrue\t\ty\ti",
        ],
    )
    mappings = tmp_path / "mappings"
    _write_tsv(
        mappings / "va-sac.tsv",
        "concept\tname\tsac_status\tsac_section\tnotes",
        [
            "commands\tBREAK\tpermitted\tSAC §1.2\tStandard.",
            "commands\tZTRIGGER\tpermitted\tSAC §X\tHypothetical: SAC permits a YDB-only feature.",
            "commands\tZWRITE\tforbidden\tSAC §3.4\tHypothetical: SAC forbids a portable feature.",
            # CATCH not mentioned by SAC.
        ],
    )
    return integrated, mappings


def test_emit_sac_compliance_writes_tsv_and_json(tmp_path: Path) -> None:
    integrated, mappings = _scaffold(tmp_path)
    schema = Path("schemas") / "va-sac-compliance.schema.json"
    tsv_out = tmp_path / "compliance.tsv"
    json_out = tmp_path / "compliance.json"
    emit_sac_compliance(
        integrated_dir=integrated,
        mappings_dir=mappings,
        tsv_out=tsv_out,
        json_out=json_out,
        schema_path=schema,
    )
    rows = tsv_out.read_text().splitlines()
    assert rows[0].split("\t") == [
        "concept", "name", "pragmatic_tier", "sac_status",
        "concern", "sac_section", "notes",
    ]
    data = json.loads(json_out.read_text())
    assert data["schema_version"] == "1"
    assert data["concept"] == "va-sac-compliance"


def test_emit_sac_compliance_classifies_each_entry(tmp_path: Path) -> None:
    integrated, mappings = _scaffold(tmp_path)
    schema = Path("schemas") / "va-sac-compliance.schema.json"
    json_out = tmp_path / "compliance.json"
    emit_sac_compliance(
        integrated_dir=integrated,
        mappings_dir=mappings,
        tsv_out=tmp_path / "compliance.tsv",
        json_out=json_out,
        schema_path=schema,
    )
    data = json.loads(json_out.read_text())
    by_name = {(e["concept"], e["name"]): e for e in data["entries"]}
    assert by_name[("commands", "BREAK")]["concern"] == "aligned"
    assert (
        by_name[("commands", "ZTRIGGER")]["concern"]
        == "sac_says_use_but_not_portable"
    )
    assert (
        by_name[("commands", "ZWRITE")]["concern"]
        == "sac_says_avoid_but_portable"
    )
    assert (
        by_name[("commands", "CATCH")]["concern"] == "sac_silent_on_unportable"
    )


def test_emit_sac_compliance_summarises_concerns(tmp_path: Path) -> None:
    integrated, mappings = _scaffold(tmp_path)
    schema = Path("schemas") / "va-sac-compliance.schema.json"
    json_out = tmp_path / "compliance.json"
    emit_sac_compliance(
        integrated_dir=integrated,
        mappings_dir=mappings,
        tsv_out=tmp_path / "compliance.tsv",
        json_out=json_out,
        schema_path=schema,
    )
    data = json.loads(json_out.read_text())
    assert data["counts"]["aligned"] >= 1
    assert data["counts"]["sac_says_use_but_not_portable"] >= 1
    assert data["counts"]["sac_says_avoid_but_portable"] >= 1


def test_emit_sac_compliance_works_with_empty_sac(tmp_path: Path) -> None:
    """Pipeline must still produce output when SAC overlay is empty.

    A fresh m-standard install with mappings/va-sac.tsv as just a
    header line should produce a compliance file with everything
    classified as `sac_silent_on_*`.
    """
    integrated, _ = _scaffold(tmp_path)
    mappings = tmp_path / "mappings"
    _write_tsv(
        mappings / "va-sac.tsv",
        "concept\tname\tsac_status\tsac_section\tnotes",
        [],
    )
    schema = Path("schemas") / "va-sac-compliance.schema.json"
    json_out = tmp_path / "compliance.json"
    emit_sac_compliance(
        integrated_dir=integrated,
        mappings_dir=mappings,
        tsv_out=tmp_path / "compliance.tsv",
        json_out=json_out,
        schema_path=schema,
    )
    data = json.loads(json_out.read_text())
    for e in data["entries"]:
        assert e["concern"].startswith("sac_silent_on_")

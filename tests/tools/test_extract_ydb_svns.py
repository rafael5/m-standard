"""Tests for YDB ISV extraction.

YDB's ``ProgrammersGuide/isv.rst`` differs from commands/functions: each
ISV section has no "The format … is:" sentence — the format token
``$X[YYY]`` appears at the start of the first description paragraph.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_ydb import (
    extract_special_variables,
    write_special_variables_tsv,
)

RST = """\
==============
8. Special Variables
==============

This chapter describes intrinsic special variables (ISVs).

-----------
$DEVICE
-----------

$D[EVICE] reflects the status of the current device.

-----------
$ZAUDIT
-----------

$ZAUD[IT] holds an audit log identifier.

-----------
Trigger ISVs
-----------

This is a group heading; it should be skipped because it is not a
single ISV name.
"""


def _write(tmp_path: Path) -> Path:
    src = tmp_path / "isv.rst"
    src.write_text(RST)
    return src


def test_extract_special_variables_skips_non_dollar_headings(tmp_path: Path) -> None:
    svns = extract_special_variables(_write(tmp_path))
    assert sorted(s.canonical_name for s in svns) == ["$DEVICE", "$ZAUDIT"]


def test_extract_special_variables_records_format_and_abbrev(tmp_path: Path) -> None:
    by_name = {s.canonical_name: s for s in extract_special_variables(_write(tmp_path))}
    assert by_name["$DEVICE"].abbreviation == "$D"
    assert by_name["$DEVICE"].format == "$D[EVICE]"
    assert by_name["$ZAUDIT"].abbreviation == "$ZAUD"


def test_extract_special_variables_marks_z_extensions(tmp_path: Path) -> None:
    by_name = {s.canonical_name: s for s in extract_special_variables(_write(tmp_path))}
    assert by_name["$DEVICE"].standard_status_hint == "ansi"
    assert by_name["$ZAUDIT"].standard_status_hint == "ydb-extension"


def test_extract_special_variables_writes_tsv(tmp_path: Path) -> None:
    out = tmp_path / "isv.tsv"
    write_special_variables_tsv(extract_special_variables(_write(tmp_path)), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("canonical_name\t")
    assert len(rows) == 1 + 2

"""Tests for the YDB environment (device I/O parameter) extractor."""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_ydb import (
    extract_environment,
    write_environment_tsv,
)

RST = """\
=================
9. I/O Processing
=================

----------------------------
USE Device Parameters
----------------------------

Some prose describing USE parameters.

~~~~~~~~~~~~~
APPEND
~~~~~~~~~~~~~

APPEND opens an existing sequential file for appending.

~~~~~~~~~~~~~
CHSET
~~~~~~~~~~~~~

CHSET specifies the character set for the device.

~~~~~~~~~~~~~
$IO
~~~~~~~~~~~~~

$IO is an ISV; should not appear in environment.tsv.

~~~~~~~~~~~~~
ZBFSIZE
~~~~~~~~~~~~~

ZBFSIZE is a YDB-specific buffer-size parameter.

~~~~~~~~~~~~~~~~~~~~~~~
Direct Mode Editing
~~~~~~~~~~~~~~~~~~~~~~~

Utility heading; should not appear in environment.tsv.
"""


def _write(tmp_path: Path) -> Path:
    src = tmp_path / "ioproc.rst"
    src.write_text(RST)
    return src


def test_extract_environment_finds_device_parameters(tmp_path: Path) -> None:
    entries = extract_environment(_write(tmp_path))
    assert sorted(e.name for e in entries) == ["APPEND", "CHSET", "ZBFSIZE"]


def test_extract_environment_skips_isvs_and_utility_headings(tmp_path: Path) -> None:
    names = {e.name for e in extract_environment(_write(tmp_path))}
    assert "$IO" not in names  # ISV — already in intrinsic-special-variables.tsv
    assert "Direct Mode Editing" not in names  # Utility heading


def test_extract_environment_z_prefix_is_extension(tmp_path: Path) -> None:
    by_name = {e.name: e for e in extract_environment(_write(tmp_path))}
    assert by_name["APPEND"].standard_status_hint == "ansi"
    assert by_name["CHSET"].standard_status_hint == "ansi"
    assert by_name["ZBFSIZE"].standard_status_hint == "ydb-extension"


def test_extract_environment_writes_tsv(tmp_path: Path) -> None:
    out = tmp_path / "environment.tsv"
    write_environment_tsv(extract_environment(_write(tmp_path)), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("name\t")
    assert len(rows) == 1 + 3

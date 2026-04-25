"""Tests for IRIS system-error extraction.

The IRIS system-error reference (KEY=RERR_system) renders each error
as a 2-cell table row: ``[<NAME>, description]``. Names are wrapped
in angle brackets, e.g. ``<DIVIDE>``, ``<UNDEFINED>``.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_iris import (
    extract_errors,
    write_errors_tsv,
)

# Synthetic shape mirroring sources/iris/site/RERR_system.html.
PAGE = b"""<html><body>
<h1>System Error Messages</h1>
<table>
<tr><td>&lt;DIVIDE&gt;</td><td>Divide by zero attempted.</td></tr>
<tr><td>&lt;UNDEFINED&gt;</td><td>Reference to a local or global variable that is not defined.</td></tr>
<tr><td>&lt;ZDIVIDE&gt;</td><td>An IRIS-specific extension error.</td></tr>
</table>
</body></html>
"""


def _make_pages(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    site.mkdir(parents=True)
    (site / "RERR_system.html").write_bytes(PAGE)
    return site


def test_extract_errors_strips_angle_brackets(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    errors = extract_errors(site)
    names = sorted(e.mnemonic for e in errors)
    assert names == ["DIVIDE", "UNDEFINED", "ZDIVIDE"]


def test_extract_errors_records_summary(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {e.mnemonic: e for e in extract_errors(site)}
    assert by_name["DIVIDE"].summary == "Divide by zero attempted."
    assert "not defined" in by_name["UNDEFINED"].summary


def test_extract_errors_marks_z_prefix_as_iris_extension(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {e.mnemonic: e for e in extract_errors(site)}
    assert by_name["DIVIDE"].standard_status_hint == "ansi"
    assert by_name["UNDEFINED"].standard_status_hint == "ansi"
    assert by_name["ZDIVIDE"].standard_status_hint == "iris-extension"


def test_extract_errors_records_source_section(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {e.mnemonic: e for e in extract_errors(site)}
    assert "RERR_system.html" in by_name["DIVIDE"].source_section


def test_extract_errors_writes_tsv(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    out = tmp_path / "errors.tsv"
    write_errors_tsv(extract_errors(site), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("mnemonic\t")
    assert len(rows) == 1 + 3

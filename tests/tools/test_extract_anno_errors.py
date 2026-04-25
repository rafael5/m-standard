"""Tests for AnnoStd appendix-B (M-code) error extraction."""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_anno import extract_errors, write_errors_tsv

PAGE_M1 = b"""<table>nav</table>
<table>
<tr><td>M1</td><td>naked indicator undefined</td></tr>
</table>
"""

PAGE_M9 = b"""<table>nav</table>
<table>
<tr><td>M9</td><td>divide by zero</td></tr>
</table>
"""

# Annex-B index page that just lists Mn codes in prose; no per-error table.
PAGE_INDEX = b"""<table>nav</table>
<h3>Annex B (informative) Error code translations</h3>
<p>M1 , M2 , M3 , M4 , ... , M75 .</p>
"""


def _make_pages(tmp_path: Path) -> Path:
    pages = tmp_path / "site" / "pages"
    pages.mkdir(parents=True)
    (pages / "ab00001.html").write_bytes(PAGE_M1)
    (pages / "ab00009.html").write_bytes(PAGE_M9)
    (pages / "ab00000.html").write_bytes(PAGE_INDEX)
    return tmp_path / "site"


def test_extract_errors_one_per_page(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    errors = extract_errors(site)
    assert sorted(e.mnemonic for e in errors) == ["M1", "M9"]


def test_extract_errors_records_summary(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_mnem = {e.mnemonic: e for e in extract_errors(site)}
    assert by_mnem["M1"].summary == "naked indicator undefined"
    assert by_mnem["M9"].summary == "divide by zero"


def test_extract_errors_marks_status_ansi(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    for e in extract_errors(site):
        assert e.standard_status_hint == "ansi"


def test_extract_errors_records_source_section(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_mnem = {e.mnemonic: e for e in extract_errors(site)}
    assert "ab00001.html" in by_mnem["M1"].source_section


def test_extract_errors_writes_tsv(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    out = tmp_path / "errors.tsv"
    write_errors_tsv(extract_errors(site), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("mnemonic\t")
    assert len(rows) == 1 + 2

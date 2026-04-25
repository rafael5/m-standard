"""Tests for AnnoStd intrinsic-special-variable extraction.

In AnnoStd, every svn page shares the same h3 heading
("7.1.4.10 Intrinsic special variable names svn") and presents one svn
in a Syntax/Definition table:

    <h3>7.1.4.10 Intrinsic special variable names svn</h3>
    <table>
      <tr><td>Syntax</td><td>Definition</td></tr>
      <tr><td>$D[EVICE]</td><td>$Device reflects the status...</td>...</tr>
    </table>

The page ID, not the section number, is the unique identifier.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_anno import (
    extract_special_variables,
    write_special_variables_tsv,
)

PAGE_DEVICE = b"""<table>nav</table>
<h3>7.1.4.10 <span>Intrinsic special variable names svn</span></h3>
<table>
<tr><td>Syntax</td><td>Definition</td></tr>
<tr>
<td>$D[EVICE]</td>
<td>$Device reflects the status of the current device.</td>
<td></td><td>|</td><td>M</td>
</tr>
</table>
<table>nav-footer</table>
"""

PAGE_HOROLOG = b"""<table>nav</table>
<h3>7.1.4.10 <span>Intrinsic special variable names svn</span></h3>
<table>
<tr><td>Syntax</td><td>Definition</td></tr>
<tr>
<td>$H[OROLOG]</td>
<td>$Horolog gives date and time with one access.</td>
</tr>
</table>
"""

PAGE_NOT_AN_SVN = b"""<table>nav</table>
<h3>7.1.5.1 <span>$ASCII</span></h3>
<p>$A[SCII] ( expr )</p>
"""


def _make_pages(tmp_path: Path) -> Path:
    pages = tmp_path / "site" / "pages"
    pages.mkdir(parents=True)
    (pages / "a107058.html").write_bytes(PAGE_DEVICE)
    (pages / "a107062.html").write_bytes(PAGE_HOROLOG)
    (pages / "a107084.html").write_bytes(PAGE_NOT_AN_SVN)
    return tmp_path / "site"


def test_extract_special_variables_one_per_page(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    svns = extract_special_variables(site)
    assert sorted(s.canonical_name for s in svns) == ["$DEVICE", "$HOROLOG"]


def test_extract_special_variables_records_format_and_abbrev(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {s.canonical_name: s for s in extract_special_variables(site)}
    assert by_name["$DEVICE"].format == "$D[EVICE]"
    assert by_name["$DEVICE"].abbreviation == "$D"
    assert by_name["$HOROLOG"].format == "$H[OROLOG]"
    assert by_name["$HOROLOG"].abbreviation == "$H"


def test_extract_special_variables_records_definition(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {s.canonical_name: s for s in extract_special_variables(site)}
    assert by_name["$DEVICE"].description.startswith("$Device reflects")


def test_extract_special_variables_records_source_section(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {s.canonical_name: s for s in extract_special_variables(site)}
    # source_section uses page path because section number isn't unique
    assert "pages/a107058.html" in by_name["$DEVICE"].source_section


def test_extract_special_variables_writes_tsv(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    out = tmp_path / "isv.tsv"
    write_special_variables_tsv(extract_special_variables(site), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("canonical_name\t")
    assert len(rows) == 1 + 2

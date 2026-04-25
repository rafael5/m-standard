"""Tests for AnnoStd intrinsic-function extraction.

AnnoStd function pages (section 7.1.5.x in the 1995 ANSI standard) have
the format in the first ``<p>`` after the ``<h3>``, not in a table:

    <h3>7.1.5.1 $ASCII</h3>
    <p>$A[SCII] ( expr )</p>
    <p>This form produces an integer value …</p>
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_anno import (
    AnnoFunction,
    extract_intrinsic_functions,
    write_intrinsic_functions_tsv,
)

PAGE_ASCII = b"""<table>nav</table>
<h3>7.1.5.1 <span>$ASCII</span></h3>
<p>$A[SCII] ( expr )</p>
<p>This form produces an integer value as follows:</p>
<p>$A[SCII] ( expr , intexpr )</p>
<table>nav-footer</table>
"""

PAGE_DATA = b"""<table>nav</table>
<h3>7.1.5.3 <span>$DATA</span></h3>
<p>$D[ATA] ( glvn )</p>
<p>The $DATA function returns information about the current state of glvn.</p>
"""

PAGE_NOT_A_FUNCTION = b"""<table>nav</table>
<h3>7.1.4.10 <span>Intrinsic special variable names svn</span></h3>
<table><tr><td>Syntax</td><td>Definition</td></tr></table>
"""


def _make_pages(tmp_path: Path) -> Path:
    pages = tmp_path / "site" / "pages"
    pages.mkdir(parents=True)
    (pages / "a107084.html").write_bytes(PAGE_ASCII)
    (pages / "a107086.html").write_bytes(PAGE_DATA)
    (pages / "a107047.html").write_bytes(PAGE_NOT_A_FUNCTION)
    return tmp_path / "site"


def test_extract_intrinsic_functions_filters_to_section_7_1_5(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    funcs = extract_intrinsic_functions(site)
    assert sorted(f.canonical_name for f in funcs) == ["$ASCII", "$DATA"]


def test_extract_intrinsic_functions_pulls_format_from_first_p(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {f.canonical_name: f for f in extract_intrinsic_functions(site)}
    assert by_name["$ASCII"].format == "$A[SCII] ( expr )"
    assert by_name["$ASCII"].abbreviation == "$A"
    assert by_name["$DATA"].format == "$D[ATA] ( glvn )"
    assert by_name["$DATA"].abbreviation == "$D"


def test_extract_intrinsic_functions_finds_description_after_format(
    tmp_path: Path,
) -> None:
    site = _make_pages(tmp_path)
    by_name = {f.canonical_name: f for f in extract_intrinsic_functions(site)}
    assert by_name["$ASCII"].description.startswith(
        "This form produces an integer value"
    )
    assert by_name["$DATA"].description.startswith("The $DATA function returns")


def test_extract_intrinsic_functions_marks_status_ansi(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    for f in extract_intrinsic_functions(site):
        assert f.standard_status_hint == "ansi"


def test_extract_intrinsic_functions_records_source_section(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {f.canonical_name: f for f in extract_intrinsic_functions(site)}
    assert by_name["$ASCII"].source_section == "pages/a107084.html#7.1.5.1"


def test_extract_intrinsic_functions_writes_tsv(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    out = tmp_path / "intrinsic-functions.tsv"
    write_intrinsic_functions_tsv(extract_intrinsic_functions(site), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].split("\t") == [
        "canonical_name",
        "abbreviation",
        "section_number",
        "format",
        "standard_status_hint",
        "source_section",
        "description",
    ]
    assert len(rows) == 1 + 2


def test_anno_function_dataclass_is_frozen() -> None:
    import dataclasses

    assert dataclasses.is_dataclass(AnnoFunction)

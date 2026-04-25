"""Tests for AnnoStd operator extraction.

AnnoStd renders operators across five chapter-7.2.x pages. Some have
clean per-operator tables (arithmetic); others embed the symbols in
prose (concatenation, numeric, string, logical).
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_anno import (
    extract_operators,
    write_operators_tsv,
)

PAGE_ARITHMETIC = b"""<table>nav</table>
<h3>7.2.1.2 Arithmetic binary operators</h3>
<p>The binary operators + - * / \\ # ** are called the arithmetic binary operators.</p>
<table>
<tr><td>+</td><td>produces the algebraic sum.</td></tr>
<tr><td>-</td><td>produces the algebraic difference.</td></tr>
<tr><td>*</td><td>produces the algebraic product.</td></tr>
</table>
"""

PAGE_CONCAT = b"""<table>nav</table>
<h3>7.2.1.1 Concatenation operator</h3>
<p>The underscore symbol _ is the concatenation operator.</p>
"""

PAGE_NUMERIC = b"""<table>nav</table>
<h3>7.2.2.2 Numeric relations</h3>
<p>The inequalities &gt; and &lt; operate on the numeric interpretations.</p>
"""

PAGE_STRING = b"""<table>nav</table>
<h3>7.2.2.3 String relations</h3>
<p>The relations = ] [ and ]] do not imply any numeric interpretation.</p>
"""

PAGE_LOGICAL = b"""<table>nav</table>
<h3>7.2.2.4 Logical operator logicalop</h3>
<p>The operators ! and &amp; are called logical operators.</p>
"""


def _make_pages(tmp_path: Path) -> Path:
    pages = tmp_path / "site" / "pages"
    pages.mkdir(parents=True)
    (pages / "a107192.html").write_bytes(PAGE_CONCAT)
    (pages / "a107193.html").write_bytes(PAGE_ARITHMETIC)
    (pages / "a107196.html").write_bytes(PAGE_NUMERIC)
    (pages / "a107197.html").write_bytes(PAGE_STRING)
    (pages / "a107198.html").write_bytes(PAGE_LOGICAL)
    return tmp_path / "site"


def test_extract_operators_arithmetic_uses_table_when_present(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_sym = {(o.operator_class, o.symbol) for o in extract_operators(site)}
    assert ("arithmetic", "+") in by_sym
    assert ("arithmetic", "-") in by_sym
    assert ("arithmetic", "*") in by_sym


def test_extract_operators_pulls_symbols_from_prose(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_sym = {(o.operator_class, o.symbol) for o in extract_operators(site)}
    assert ("string-relational", "[") in by_sym
    assert ("string-relational", "]") in by_sym
    assert ("string-relational", "]]") in by_sym
    assert ("string-relational", "=") in by_sym
    assert ("numeric-relational", ">") in by_sym
    assert ("numeric-relational", "<") in by_sym
    assert ("logical", "!") in by_sym
    assert ("logical", "&") in by_sym
    assert ("string", "_") in by_sym


def test_extract_operators_marks_status_ansi(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    for o in extract_operators(site):
        assert o.standard_status_hint == "ansi"


def test_extract_operators_writes_tsv(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    out = tmp_path / "operators.tsv"
    write_operators_tsv(extract_operators(site), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    header = rows[0].split("\t")
    assert "symbol" in header
    assert "operator_class" in header

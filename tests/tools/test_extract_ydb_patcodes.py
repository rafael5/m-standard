"""Tests for YDB pattern-code extraction.

Pattern codes live in ``ProgrammersGuide/langfeat.rst`` as an RST grid
table introduced by "The pattern codes are:".
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_ydb import extract_pattern_codes

RST = """\
==============
5. Language features
==============

Some prose.

The pattern codes are:

+----------+----------------------------------------+
| Code     | Description                            |
+==========+========================================+
| A        | alphabetic characters upper or lower   |
+----------+----------------------------------------+
| N        | digits 0-9, ASCII 48-57                |
+----------+----------------------------------------+
| U        | upper-case alphabetic characters       |
+----------+----------------------------------------+

YottaDB also accepts ...
"""


def _write(tmp_path: Path) -> Path:
    src = tmp_path / "langfeat.rst"
    src.write_text(RST)
    return src


def test_extract_pattern_codes_finds_each_row(tmp_path: Path) -> None:
    codes = extract_pattern_codes(_write(tmp_path))
    assert sorted(c.code for c in codes) == ["A", "N", "U"]


def test_extract_pattern_codes_records_description(tmp_path: Path) -> None:
    by_code = {c.code: c for c in extract_pattern_codes(_write(tmp_path))}
    assert by_code["A"].description.startswith("alphabetic characters")
    assert "digits 0-9" in by_code["N"].description


def test_extract_pattern_codes_marks_status_ansi(tmp_path: Path) -> None:
    """Standard pattern codes A C E L N P U are ANSI; others are extensions."""
    for c in extract_pattern_codes(_write(tmp_path)):
        assert c.standard_status_hint == "ansi"

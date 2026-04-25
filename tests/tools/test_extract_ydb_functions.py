"""Tests for YDB intrinsic-function extraction.

Synthetic RST fixture mirrors ``ProgrammersGuide/functions.rst``:
chapter heading with =, per-function headings with -, format intro
sentence, code-block with the format string.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_ydb import (
    YdbFunction,
    extract_intrinsic_functions,
    write_intrinsic_functions_tsv,
)

RST = """\
.. ###############################################################
.. # Copyright stuff.
.. ###############################################################

==============
7. Functions
==============

This chapter describes intrinsic functions implemented in YottaDB.

-----------
$ASCII()
-----------

Returns the integer ASCII code for a character in the given string.

The format for the $ASCII function is:

.. code-block:: none

   $A[SCII](expr[,intexpr])

* The expression is the source string.

-----------
$ZASCII()
-----------

YottaDB extension of $ASCII for byte values.

The format for the $ZASCII function is:

.. code-block:: none

   $ZA[SCII](expr[,intexpr])
"""


def _write(tmp_path: Path) -> Path:
    src = tmp_path / "functions.rst"
    src.write_text(RST)
    return src


def test_extract_intrinsic_functions_finds_each_section(tmp_path: Path) -> None:
    funcs = extract_intrinsic_functions(_write(tmp_path))
    assert [f.canonical_name for f in funcs] == ["$ASCII", "$ZASCII"]


def test_extract_intrinsic_functions_records_format_and_abbrev(tmp_path: Path) -> None:
    funcs = extract_intrinsic_functions(_write(tmp_path))
    by_name = {f.canonical_name: f for f in funcs}
    assert by_name["$ASCII"].abbreviation == "$A"
    assert by_name["$ASCII"].format == "$A[SCII](expr[,intexpr])"
    assert by_name["$ZASCII"].abbreviation == "$ZA"


def test_extract_intrinsic_functions_marks_z_extensions(tmp_path: Path) -> None:
    funcs = extract_intrinsic_functions(_write(tmp_path))
    by_name = {f.canonical_name: f for f in funcs}
    assert by_name["$ASCII"].standard_status_hint == "ansi"
    assert by_name["$ZASCII"].standard_status_hint == "ydb-extension"


def test_extract_intrinsic_functions_writes_tsv(tmp_path: Path) -> None:
    out = tmp_path / "intrinsic-functions.tsv"
    write_intrinsic_functions_tsv(extract_intrinsic_functions(_write(tmp_path)), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].split("\t") == [
        "canonical_name",
        "abbreviation",
        "format",
        "standard_status_hint",
        "source_section",
        "description",
    ]
    assert len(rows) == 1 + 2


def test_ydb_function_dataclass_is_frozen() -> None:
    import dataclasses

    assert dataclasses.is_dataclass(YdbFunction)
    fields = {f.name for f in dataclasses.fields(YdbFunction)}
    assert "canonical_name" in fields
    assert "format" in fields

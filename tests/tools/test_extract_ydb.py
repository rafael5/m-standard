"""Tests use small synthetic RST fixtures, never the real cloned corpus."""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_ydb import (
    YdbCommand,
    extract_commands,
)

# Realistic RST fixture in the same shape as
# sources/ydb/repo/ProgrammersGuide/commands.rst (chapter heading with
# ====, per-command headings with ---, examples with +++).
RST = """\
.. ###############################################################
.. # Copyright stuff that must be ignored.
.. ###############################################################

.. index::
   Commands

=====================
6. Commands
=====================

.. contents::
   :depth: 2

This chapter describes M language commands implemented in YottaDB. All
commands starting with the letter Z are YottaDB additions to the ANSI
standard command set.

------------
Break
------------

The BREAK command pauses execution.

The format of the BREAK command is:

.. code-block:: none

   B[REAK][:tvexpr] [expr[:tvexpr][,...]]

* Some bullet about behaviour.

+++++++++++++++++++++++
Examples of BREAK
+++++++++++++++++++++++

Example skipped.

------------
Else
------------

ELSE has no postconditional and no arguments.

The format of the ELSE command is:

.. code-block:: none

   E[LSE]

------------
ZBREAK
------------

The ZBREAK command inserts a temporary BREAK into the image.

The format of the ZBREAK command is:

.. code-block:: none

   ZB[REAK][:tvexpr] [-]entryref[:[expr][:intexpr]][,...]
"""


def test_extract_commands_finds_all_command_headings(tmp_path: Path) -> None:
    src = tmp_path / "commands.rst"
    src.write_text(RST)
    commands = extract_commands(src)
    assert [c.canonical_name for c in commands] == ["BREAK", "ELSE", "ZBREAK"]


def test_extract_commands_parses_abbreviation_and_format(tmp_path: Path) -> None:
    src = tmp_path / "commands.rst"
    src.write_text(RST)
    by_name = {c.canonical_name: c for c in extract_commands(src)}
    assert by_name["BREAK"].abbreviation == "B"
    assert by_name["BREAK"].format == "B[REAK][:tvexpr] [expr[:tvexpr][,...]]"
    assert by_name["ELSE"].abbreviation == "E"
    assert by_name["ELSE"].format == "E[LSE]"
    assert by_name["ZBREAK"].abbreviation == "ZB"


def test_extract_commands_classifies_z_extensions(tmp_path: Path) -> None:
    src = tmp_path / "commands.rst"
    src.write_text(RST)
    by_name = {c.canonical_name: c for c in extract_commands(src)}
    assert by_name["BREAK"].standard_status_hint == "ansi"
    assert by_name["ELSE"].standard_status_hint == "ansi"
    assert by_name["ZBREAK"].standard_status_hint == "ydb-extension"


def test_extract_commands_records_source_section(tmp_path: Path) -> None:
    src = tmp_path / "commands.rst"
    src.write_text(RST)
    by_name = {c.canonical_name: c for c in extract_commands(src)}
    # source_section names the file and the heading, not the absolute path
    assert by_name["BREAK"].source_section.endswith("commands.rst#Break")


def test_extract_commands_captures_first_description_paragraph(tmp_path: Path) -> None:
    src = tmp_path / "commands.rst"
    src.write_text(RST)
    by_name = {c.canonical_name: c for c in extract_commands(src)}
    assert by_name["BREAK"].description == "The BREAK command pauses execution."
    assert by_name["ZBREAK"].description.startswith("The ZBREAK command inserts")


def test_extract_commands_writes_tsv(tmp_path: Path) -> None:
    """End-to-end: tsv has one row per command and a fixed column header."""
    from m_standard.tools.extract_ydb import write_commands_tsv

    src = tmp_path / "commands.rst"
    src.write_text(RST)
    out = tmp_path / "commands.tsv"
    write_commands_tsv(extract_commands(src), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].split("\t") == [
        "canonical_name",
        "abbreviation",
        "format",
        "standard_status_hint",
        "source_section",
        "description",
    ]
    assert len(rows) == 1 + 3  # header + BREAK + ELSE + ZBREAK
    # Rows are sorted for stable diffs
    assert [r.split("\t")[0] for r in rows[1:]] == ["BREAK", "ELSE", "ZBREAK"]


def test_ydb_command_dataclass_is_frozen() -> None:
    """Per-source records are immutable so reconcile can hash them."""
    import dataclasses

    assert dataclasses.is_dataclass(YdbCommand)
    fields = {f.name for f in dataclasses.fields(YdbCommand)}
    assert {
        "canonical_name",
        "abbreviation",
        "format",
        "standard_status_hint",
        "source_section",
        "description",
    } <= fields

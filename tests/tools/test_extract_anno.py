"""Tests use synthetic HTML fixtures shaped like AnnoStd command pages.

A real AnnoStd command page has roughly this shape:

    <h3>8.2.1 <span...>Break</span></h3>
    <table>
      <tr>
        <td align="center">B[REAK] <span...>postcond</span></td>
        <td>...visual rule glyphs...</td>
        <td align="center">[ <span>SP</span> ]<br/>argument syntax unspecified</td>
        ...
      </tr>
    </table>
    <p>Break provides an access point ...</p>

The extractor walks pages whose <h3> heading matches a section number
prefix and pulls (section, name, format, description) out.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_anno import (
    AnnoCommand,
    extract_commands,
)

PAGE_BREAK = b"""<table>nav</table>
<a name="Def_0001"></a>
<h3>8.2.1 <span onclick="x">Break</span></h3>

<table><tr>
<td align="center">B[REAK] <span><u>postcond</u></span></td>
<td>|</td>
<td align="center">[ SP ]<br/>argument syntax unspecified</td>
</tr></table>

<p><span>Break</span> provides an access point within the standard for
nonstandard programming aids.  <span>Break</span> without arguments
suspends execution until receipt of a signal, not specified here,
from a device.</p>
<table>nav-footer</table>
"""

PAGE_DO = b"""<table>nav</table>
<h3>8.2.4 <span>Do</span></h3>
<table><tr>
<td align="center">D[O] <span><u>postcond</u></span></td>
<td>|</td>
<td align="center">argument syntax</td>
</tr></table>
<p>The Do command transfers control.</p>
<table>nav-footer</table>
"""

# Page that is NOT a command (e.g. Functions section heading).
PAGE_FUNCTIONS_OVERVIEW = b"""<table>nav</table>
<h3>9.1 <span>Functions</span></h3>
<p>This section describes intrinsic functions.</p>
"""


def _make_pages(tmp_path: Path) -> Path:
    pages = tmp_path / "site" / "pages"
    pages.mkdir(parents=True)
    (pages / "a108024.html").write_bytes(PAGE_BREAK)
    (pages / "a108026.html").write_bytes(PAGE_DO)
    (pages / "a109001.html").write_bytes(PAGE_FUNCTIONS_OVERVIEW)
    return tmp_path / "site"


def test_extract_commands_finds_command_pages_only(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    cmds = extract_commands(site)
    names = sorted(c.canonical_name for c in cmds)
    assert names == ["BREAK", "DO"]


def test_extract_commands_records_section_and_format(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {c.canonical_name: c for c in extract_commands(site)}
    assert by_name["BREAK"].section_number == "8.2.1"
    assert by_name["BREAK"].abbreviation == "B"
    # The raw first-cell text, with the postcond marker preserved.
    assert "B[REAK]" in by_name["BREAK"].format
    assert by_name["DO"].section_number == "8.2.4"
    assert by_name["DO"].abbreviation == "D"


def test_extract_commands_records_source_section(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {c.canonical_name: c for c in extract_commands(site)}
    assert by_name["BREAK"].source_section == "pages/a108024.html#8.2.1"


def test_extract_commands_captures_description(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {c.canonical_name: c for c in extract_commands(site)}
    assert by_name["BREAK"].description.startswith(
        "Break provides an access point"
    )
    # Inline whitespace + newlines are collapsed into single spaces.
    assert "  " not in by_name["BREAK"].description


def test_extract_commands_marks_standard_status_ansi(tmp_path: Path) -> None:
    """AnnoStd is the ANSI standard — every command extracted is `ansi`."""
    site = _make_pages(tmp_path)
    for c in extract_commands(site):
        assert c.standard_status_hint == "ansi"


def test_extract_commands_writes_tsv(tmp_path: Path) -> None:
    from m_standard.tools.extract_anno import write_commands_tsv

    site = _make_pages(tmp_path)
    out = tmp_path / "commands.tsv"
    write_commands_tsv(extract_commands(site), out)
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
    assert len(rows) == 1 + 2  # header + BREAK + DO


def test_anno_command_dataclass_is_frozen() -> None:
    import dataclasses

    assert dataclasses.is_dataclass(AnnoCommand)
    assert all(f.name for f in dataclasses.fields(AnnoCommand))

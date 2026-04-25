"""Tests for IRIS RCOS entry extraction (commands, functions, svns).

IRIS RCOS pages share a uniform shape:
- h1 id="RCOS_<prefix><name>" with text like "BREAK (ObjectScript)" or
  "$ASCII (ObjectScript)" or "$DEVICE (ObjectScript)".
- A "Synopsis" section with the syntax form in a <pre> or code block.
- A "Description" section with prose.

Extractor splits per RCOS_c<x>, RCOS_f<x>, RCOS_v<x>, RCOS_cz<x>
filename prefixes.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_iris import (
    extract_commands,
    extract_intrinsic_functions,
    extract_special_variables,
)

PAGE_BREAK = b"""<html><body>
<article>
<h1 id="RCOS_cbreak">BREAK (ObjectScript)</h1>
<section><h2><span role="heading">Synopsis</span></h2>
<pre>BREAK:pc

BREAK:pc extend

BREAK:pc flag</pre>
</section>
<section><h2><span role="heading">Description</span></h2>
<p>The BREAK command pauses execution of the routine.</p>
</section>
</article>
</body></html>
"""

PAGE_CATCH = b"""<html><body>
<article>
<h1 id="RCOS_ccatch">CATCH (ObjectScript)</h1>
<section><h2><span role="heading">Synopsis</span></h2>
<pre>CATCH [exception-arg] {
  ...
}</pre>
</section>
<section><h2><span role="heading">Description</span></h2>
<p>The CATCH command begins a CATCH block of an error handler.</p>
</section>
</article>
</body></html>
"""

PAGE_ASCII = b"""<html><body>
<article>
<h1 id="RCOS_fascii">$ASCII (ObjectScript)</h1>
<section><h2><span role="heading">Synopsis</span></h2>
<pre>$ASCII(string,position)
$A(string,position)</pre>
</section>
<section><h2><span role="heading">Description</span></h2>
<p>$ASCII returns the integer ASCII code value of the indicated character.</p>
</section>
</article>
</body></html>
"""

PAGE_DEVICE = b"""<html><body>
<article>
<h1 id="RCOS_vdevice">$DEVICE (ObjectScript)</h1>
<section><h2><span role="heading">Synopsis</span></h2>
<pre>$DEVICE</pre>
</section>
<section><h2><span role="heading">Description</span></h2>
<p>The $DEVICE special variable contains the status of the current device.</p>
</section>
</article>
</body></html>
"""

PAGE_ZBREAK = b"""<html><body>
<article>
<h1 id="RCOS_czbreak">ZBREAK (ObjectScript)</h1>
<section><h2><span role="heading">Synopsis</span></h2>
<pre>ZBREAK [breakargument [,...]]</pre>
</section>
<section><h2><span role="heading">Description</span></h2>
<p>The ZBREAK command sets a debug breakpoint.</p>
</section>
</article>
</body></html>
"""

# Index-page-style file that should be SKIPPED (no per-entry content).
PAGE_TOC = b"""<html><body>
<article>
<h1 id="RCOS_COMMANDS">ObjectScript Commands</h1>
<p>This page lists the commands.</p>
</article>
</body></html>
"""


def _make_pages(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    site.mkdir(parents=True)
    (site / "RCOS_cbreak.html").write_bytes(PAGE_BREAK)
    (site / "RCOS_ccatch.html").write_bytes(PAGE_CATCH)
    (site / "RCOS_fascii.html").write_bytes(PAGE_ASCII)
    (site / "RCOS_vdevice.html").write_bytes(PAGE_DEVICE)
    (site / "RCOS_czbreak.html").write_bytes(PAGE_ZBREAK)
    (site / "RCOS_COMMANDS.html").write_bytes(PAGE_TOC)
    return site


def test_extract_commands_finds_per_entry_pages_only(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    cmds = extract_commands(site)
    names = sorted(c.canonical_name for c in cmds)
    # Includes RCOS_c* and RCOS_cz* (Z-commands).
    # Excludes RCOS_COMMANDS (TOC), RCOS_f*, RCOS_v*.
    assert names == ["BREAK", "CATCH", "ZBREAK"]


def test_extract_commands_marks_z_extensions(tmp_path: Path) -> None:
    """Extractor uses simple Z-prefix heuristic for the hint.
    The reconciler reclassifies non-Z entries that aren't in AnnoStd
    as iris-extension per AD-01 (so CATCH ends up iris-extension in
    the integrated layer; here we only assert the per-source hint)."""
    site = _make_pages(tmp_path)
    by_name = {c.canonical_name: c for c in extract_commands(site)}
    assert by_name["BREAK"].standard_status_hint == "ansi"
    assert by_name["CATCH"].standard_status_hint == "ansi"  # Reconciler will fix
    assert by_name["ZBREAK"].standard_status_hint == "iris-extension"


def test_extract_commands_records_synopsis_and_description(
    tmp_path: Path,
) -> None:
    site = _make_pages(tmp_path)
    by_name = {c.canonical_name: c for c in extract_commands(site)}
    assert "BREAK:pc" in by_name["BREAK"].format
    assert by_name["BREAK"].description.startswith("The BREAK command pauses")


def test_extract_intrinsic_functions(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    funcs = extract_intrinsic_functions(site)
    names = sorted(f.canonical_name for f in funcs)
    assert names == ["$ASCII"]
    assert funcs[0].format.startswith("$ASCII(string")
    assert funcs[0].standard_status_hint == "ansi"


def test_extract_special_variables(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    svns = extract_special_variables(site)
    names = sorted(s.canonical_name for s in svns)
    assert names == ["$DEVICE"]
    assert svns[0].format == "$DEVICE"
    assert svns[0].standard_status_hint == "ansi"


def test_extract_records_source_section(tmp_path: Path) -> None:
    site = _make_pages(tmp_path)
    by_name = {c.canonical_name: c for c in extract_commands(site)}
    assert "RCOS_cbreak.html" in by_name["BREAK"].source_section


def test_extract_writes_tsv(tmp_path: Path) -> None:
    from m_standard.tools.extract_iris import write_commands_tsv

    site = _make_pages(tmp_path)
    out = tmp_path / "commands.tsv"
    write_commands_tsv(extract_commands(site), out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("canonical_name\t")
    assert len(rows) == 1 + 3

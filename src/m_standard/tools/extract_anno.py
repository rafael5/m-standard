"""Per-source extractor for the AnnoStd local mirror.

Reads ``sources/anno/site/`` (the offline mirror produced by
``crawl_anno``) and writes raw per-source TSVs under
``per-source/anno/``. Per spec §6.1, output is deliberately raw —
verbatim facts from the source's own organisation, with minimal
interpretation. Reconciliation across sources happens elsewhere.

Page shape (per page in ``site/pages/aXXXXXX.html``):
    <h3>SECTION_NUMBER <span...>NAME</span></h3>
    <table><tr>... format cells ...</tr></table>
    <p>...description paragraph...</p>

The chapter prefix in ``SECTION_NUMBER`` identifies the concept family:
    - ``8.x.y`` — Commands
    - ``9.x.y`` — Functions   (extractor for these comes later)
    - ``10.x.y`` — Special variables  (later)
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from dataclasses import dataclass, fields
from pathlib import Path
from warnings import filterwarnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# AnnoStd pages are XHTML 1.0 served as text/html; bs4's lxml HTML parser
# handles them correctly but emits a noisy warning on every page.
filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

log = logging.getLogger(__name__)

DEFAULT_SITE = Path("sources/anno/site")
DEFAULT_OUT_DIR = Path("per-source/anno")

# Commands live under chapter 8 of ANSI X11.1-1995. The "8.2." subsection
# (section 8 = "Commands", subsection 2 = "Command definitions" per page
# a108018) is what separates per-command definitions from chapter 8.1
# ("General command rules" — spaces, comments, etc.). Pages whose ID does
# not start with `a` are from sibling standards (e.g. `f` = MWAPI Window
# API, X11.6) which are explicitly out of scope for v0.1 (see spec §2).
_COMMAND_SECTION_PREFIX = "8.2."
# Intrinsic functions live under section 7.1.5 of ANSI X11.1-1995.
_FUNCTION_SECTION_PREFIX = "7.1.5."
# Intrinsic special variables live under section 7.1.4 of ANSI X11.1-1995.
# Every svn page shares the section "7.1.4.10" overview heading and
# carries one svn in a Syntax/Definition table; the page ID is the unique
# key (see BL-006-style organisation).
_SVN_SECTION_PREFIX = "7.1.4."
# Operator pages live under sections 7.2.1.x (binary operators) and
# 7.2.2.x (truth/relation/logical operators) of ANSI X11.1-1995.
_OPERATOR_SECTION_PREFIXES = ("7.2.1.", "7.2.2.")
# Standard-mandated error codes live under Annex B (pages ``ab*.html``).
_ERROR_PAGE_PREFIX = "ab"
_LANGUAGE_PAGE_PREFIX = "a"

_SECTION_HEADING = re.compile(
    r"^(?P<sec>\d+(?:\.\d+)+)\s+(?P<name>\$?[A-Z][A-Za-z%]*)$"
)
_ABBREV = re.compile(r"^(\$?[A-Za-z]+)\[")

_COMMAND_COLUMNS: tuple[str, ...] = (
    "canonical_name",
    "abbreviation",
    "section_number",
    "format",
    "standard_status_hint",
    "source_section",
    "description",
)


@dataclass(frozen=True)
class AnnoEntry:
    """Shared shape for command/function/svn rows from AnnoStd pages."""

    canonical_name: str
    abbreviation: str
    section_number: str
    format: str
    standard_status_hint: str
    source_section: str
    description: str


# Backwards-compatible per-concept aliases so test code stays expressive.
AnnoCommand = AnnoEntry
AnnoFunction = AnnoEntry


def extract_commands(site_dir: Path) -> list[AnnoEntry]:
    return _walk_pages(
        site_dir,
        section_prefix=_COMMAND_SECTION_PREFIX,
        format_from="table",
    )


def extract_intrinsic_functions(site_dir: Path) -> list[AnnoEntry]:
    """Walk function pages (section 7.1.5.x) and pull format from the first <p>."""
    return _walk_pages(
        site_dir,
        section_prefix=_FUNCTION_SECTION_PREFIX,
        format_from="paragraph",
    )


def write_commands_tsv(entries: list[AnnoEntry], out: Path) -> None:
    _write_entries_tsv(entries, out)


def write_intrinsic_functions_tsv(entries: list[AnnoEntry], out: Path) -> None:
    _write_entries_tsv(entries, out)


def write_special_variables_tsv(entries: list[AnnoEntry], out: Path) -> None:
    _write_entries_tsv(entries, out)


def extract_special_variables(site_dir: Path) -> list[AnnoEntry]:
    """Walk svn pages and pull each Syntax/Definition table entry."""
    pages_dir = site_dir / "pages"
    if not pages_dir.is_dir():
        return []
    out: list[AnnoEntry] = []
    for page in sorted(pages_dir.glob(f"{_LANGUAGE_PAGE_PREFIX}*.html")):
        entry = _extract_svn_page(page)
        if entry is not None:
            out.append(entry)
    out.sort(key=lambda e: e.canonical_name)
    return out


def _extract_svn_page(page: Path) -> AnnoEntry | None:
    soup = BeautifulSoup(page.read_bytes(), "lxml")
    h3 = soup.find("h3")
    if h3 is None:
        return None
    heading_text = _normspace(h3.get_text(separator=" "))
    match = _SECTION_HEADING.match(heading_text)
    section = match.group("sec") if match else heading_text.split(" ", 1)[0]
    if not section.startswith(_SVN_SECTION_PREFIX):
        return None
    # Find the first table whose first data row's first cell starts with `$`.
    for table in h3.find_all_next("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue
            first = _normspace(cells[0].get_text(separator=" "))
            if first.startswith("$") and "[" in first:
                fmt = first
                desc = (
                    _normspace(cells[1].get_text(separator=" "))
                    if len(cells) > 1
                    else ""
                )
                rel = page.relative_to(page.parent.parent).as_posix()
                return AnnoEntry(
                    canonical_name=_canonical_from_svn_format(fmt),
                    abbreviation=_abbreviation_from_format(fmt),
                    section_number=section,
                    format=fmt,
                    standard_status_hint="ansi",
                    source_section=f"{rel}#{section}",
                    description=desc,
                )
    return None


def _canonical_from_svn_format(fmt: str) -> str:
    """`$D[EVICE]` -> `$DEVICE`."""
    match = re.match(r"^(\$[A-Za-z]+)(?:\[([A-Za-z]*)\])?", fmt)
    if not match:
        return fmt
    return (match.group(1) + (match.group(2) or "")).upper()


# ---------- Errors (Annex B, pages ab*.html) -------------------------------

_ERROR_COLUMNS: tuple[str, ...] = (
    "mnemonic",
    "summary",
    "kind",
    "standard_status_hint",
    "source_section",
)


@dataclass(frozen=True)
class AnnoError:
    mnemonic: str
    summary: str
    kind: str
    standard_status_hint: str
    source_section: str


def extract_errors(site_dir: Path) -> list[AnnoError]:
    """Walk ab*.html appendix-B pages and pull each Mnnnn definition.

    Each per-error page (ab00001..ab00075-ish) contains a single
    ``<table><tr><td>M<n></td><td>summary</td></tr></table>``. The
    Annex-B index page (ab00000) lists all codes in prose only and is
    skipped here. All entries are tagged ``ansi`` because Annex B is
    part of the 1995 standard.
    """
    pages_dir = site_dir / "pages"
    if not pages_dir.is_dir():
        return []
    out: list[AnnoError] = []
    for page in sorted(pages_dir.glob(f"{_ERROR_PAGE_PREFIX}*.html")):
        entry = _extract_error_page(page)
        if entry is not None:
            out.append(entry)
    out.sort(key=lambda e: (len(e.mnemonic), e.mnemonic))  # M1, M2, ..., M75
    return out


def write_errors_tsv(errors: list[AnnoError], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_ERROR_COLUMNS)
        for err in errors:
            writer.writerow([getattr(err, c) for c in _ERROR_COLUMNS])


_OPERATOR_COLUMNS: tuple[str, ...] = (
    "symbol",
    "operator_class",
    "description",
    "standard_status_hint",
    "source_section",
)

# Map AnnoStd section prefixes to the operator class they document.
_OPERATOR_CLASS_BY_SECTION: tuple[tuple[str, str, str], ...] = (
    ("7.2.1.1", "string", "concatenation"),
    ("7.2.1.2", "arithmetic", "arithmetic-binary"),
    ("7.2.2.2", "numeric-relational", "numeric"),
    ("7.2.2.3", "string-relational", "string"),
    ("7.2.2.4", "logical", "logical"),
)
# Symbols permitted in M operators. Multi-character operators (``]]`` and
# ``**``) are matched first by trying the longest forms before single
# chars; runs of these chars in source-text constitute candidate symbols.
_OPERATOR_SYMBOL_CHARS = "+-*/\\#=<>'!&[]_"


@dataclass(frozen=True)
class AnnoOperator:
    symbol: str
    operator_class: str
    description: str
    standard_status_hint: str
    source_section: str


def extract_operators(site_dir: Path) -> list[AnnoOperator]:
    """Walk the chapter-7.2.x operator pages and recover symbol lists.

    Two patterns are handled:
    - **Per-operator table** (chapter 7.2.1.2 arithmetic): one
      ``[symbol, description]`` row per operator. Pulled directly.
    - **Prose listing** (concatenation, numeric, string, logical):
      the first paragraph after the heading lists the operators
      inline, e.g. ``"The relations = ] [ and ]] do not imply..."``.
      Extracted by tokenising on operator-character runs.
    """
    pages_dir = site_dir / "pages"
    if not pages_dir.is_dir():
        return []
    out: list[AnnoOperator] = []
    for page in sorted(pages_dir.glob(f"{_LANGUAGE_PAGE_PREFIX}*.html")):
        out.extend(_extract_operators_page(page))
    out.sort(key=lambda o: (o.operator_class, o.symbol))
    return out


def write_operators_tsv(ops: list[AnnoOperator], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_OPERATOR_COLUMNS)
        for op in ops:
            writer.writerow([getattr(op, c) for c in _OPERATOR_COLUMNS])


def _extract_operators_page(page: Path) -> list[AnnoOperator]:
    soup = BeautifulSoup(page.read_bytes(), "lxml")
    h3 = soup.find("h3")
    if h3 is None:
        return []
    heading = _normspace(h3.get_text(separator=" "))
    section_match = _SECTION_HEADING.match(heading)
    if section_match:
        section = section_match.group("sec")
    else:
        # Some operator pages have multi-word names that don't fit the
        # SECTION_HEADING regex (e.g. "7.2.2.4 Logical operator logicalop").
        # Pull the section number off the front directly.
        section = heading.split(" ", 1)[0]

    klass = _operator_class_for(section)
    if klass is None:
        return []

    rel = page.relative_to(page.parent.parent).as_posix()
    src = f"{rel}#{section}"
    out: list[AnnoOperator] = []
    seen: set[str] = set()

    # Path 1: per-operator table.
    for table in h3.find_all_next("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            sym = _normspace(cells[0].get_text(separator=" "))
            if sym and _looks_like_operator(sym) and sym not in seen:
                out.append(
                    AnnoOperator(
                        symbol=sym,
                        operator_class=klass,
                        description=_normspace(
                            cells[1].get_text(separator=" ")
                        ),
                        standard_status_hint="ansi",
                        source_section=src,
                    )
                )
                seen.add(sym)
        if out:
            break  # Stop after the first table that yielded operators.

    # Path 2: prose extraction from the first descriptive paragraph.
    if not out:
        first_p = h3.find_next("p")
        if first_p is not None:
            prose = _normspace(first_p.get_text(separator=" "))
            for sym in _operator_symbols_in_prose(prose):
                if sym not in seen:
                    out.append(
                        AnnoOperator(
                            symbol=sym,
                            operator_class=klass,
                            description=prose,
                            standard_status_hint="ansi",
                            source_section=src,
                        )
                    )
                    seen.add(sym)

    return out


def _operator_class_for(section: str) -> str | None:
    for prefix, klass, _label in _OPERATOR_CLASS_BY_SECTION:
        if section == prefix or section.startswith(prefix + "."):
            return klass
    return None


def _looks_like_operator(s: str) -> bool:
    if not s:
        return False
    return all(ch in _OPERATOR_SYMBOL_CHARS for ch in s) and len(s) <= 3


def _operator_symbols_in_prose(prose: str) -> list[str]:
    """Pull standalone operator-character runs out of a sentence.

    Matches runs of characters from ``_OPERATOR_SYMBOL_CHARS`` that are
    surrounded by whitespace or sentence punctuation, so unrelated uses
    of these characters inside identifiers don't trigger false matches.
    """
    pattern = re.compile(
        rf"(?:^|[\s,;()])([{re.escape(_OPERATOR_SYMBOL_CHARS)}]{{1,3}})"
        rf"(?=[\s,;.()]|$)"
    )
    out: list[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(prose):
        sym = match.group(1)
        # Skip pure-punctuation matches that aren't real operators
        # (e.g. lone ``,`` or ``;``).
        if sym in seen or sym in (".", ","):
            continue
        if not _looks_like_operator(sym):
            continue
        out.append(sym)
        seen.add(sym)
    return out


def _extract_error_page(page: Path) -> AnnoError | None:
    soup = BeautifulSoup(page.read_bytes(), "lxml")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            first = _normspace(cells[0].get_text(separator=" "))
            if re.fullmatch(r"M\d{1,3}", first):
                rel = page.relative_to(page.parent.parent).as_posix()
                return AnnoError(
                    mnemonic=first,
                    summary=_normspace(cells[1].get_text(separator=" ")),
                    kind="",
                    standard_status_hint="ansi",
                    source_section=f"{rel}#{first}",
                )
    return None


def _walk_pages(
    site_dir: Path, *, section_prefix: str, format_from: str
) -> list[AnnoEntry]:
    pages_dir = site_dir / "pages"
    if not pages_dir.is_dir():
        return []
    out: list[AnnoEntry] = []
    for page in sorted(pages_dir.glob(f"{_LANGUAGE_PAGE_PREFIX}*.html")):
        entry = _extract_one(page, section_prefix, format_from)
        if entry is not None:
            out.append(entry)
    out.sort(key=lambda e: e.canonical_name)
    return out


def _write_entries_tsv(entries: list[AnnoEntry], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_COMMAND_COLUMNS)
        for entry in entries:
            writer.writerow([getattr(entry, c) for c in _COMMAND_COLUMNS])
    assert {f.name for f in fields(AnnoEntry)} >= set(_COMMAND_COLUMNS)


def _extract_one(
    page: Path, section_prefix: str, format_from: str
) -> AnnoEntry | None:
    soup = BeautifulSoup(page.read_bytes(), "lxml")
    h3 = soup.find("h3")
    if h3 is None:
        return None
    heading_text = _normspace(h3.get_text(separator=" "))
    match = _SECTION_HEADING.match(heading_text)
    if not match:
        return None
    section = match.group("sec")
    if not section.startswith(section_prefix):
        return None
    name = match.group("name").upper()

    if format_from == "paragraph":
        fmt = _format_from_first_paragraph(h3)
        description = _description_after_format_paragraph(h3)
    else:
        fmt = _format_from_first_table(h3)
        description = _first_description_paragraph(h3)
    abbrev = _abbreviation_from_format(fmt)

    rel = page.relative_to(page.parent.parent).as_posix()
    return AnnoEntry(
        canonical_name=name,
        abbreviation=abbrev,
        section_number=section,
        format=fmt,
        standard_status_hint="ansi",
        source_section=f"{rel}#{section}",
        description=description,
    )


def _format_from_first_paragraph(h3) -> str:
    p = h3.find_next("p")
    if p is None:
        return ""
    return _normspace(p.get_text(separator=" "))


def _description_after_format_paragraph(h3) -> str:
    """Description = the paragraph immediately after the format paragraph."""
    first = h3.find_next("p")
    if first is None:
        return ""
    second = first.find_next("p")
    if second is None:
        return ""
    return _normspace(second.get_text(separator=" "))


def _format_from_first_table(h3) -> str:
    """Read the first table after the heading and return its first row text."""
    table = h3.find_next("table")
    if table is None:
        return ""
    first_row = table.find("tr")
    if first_row is None:
        return ""
    cells = [_normspace(td.get_text(separator=" ")) for td in first_row.find_all("td")]
    cells = [c for c in cells if c and not _is_diagram_glyph(c)]
    return " ".join(cells)


def _is_diagram_glyph(cell: str) -> bool:
    """True if a cell is purely visual (railroad-diagram pipe/dash glyphs)."""
    glyphs = set("|│─-")
    return all(ch in glyphs or ch.isspace() for ch in cell)


def _abbreviation_from_format(fmt: str) -> str:
    match = _ABBREV.match(fmt)
    return match.group(1) if match else ""


def _first_description_paragraph(h3) -> str:
    """Find the first <p> after the format table that isn't navigation."""
    p = h3.find_next("p")
    if p is None:
        return ""
    return _normspace(p.get_text(separator=" "))


def _normspace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Extract per-source TSVs from the AnnoStd local mirror."
    )
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    if not args.site.is_dir():
        log.error("site dir not found: %s — run `make sources-anno` first", args.site)
        return 1

    commands = extract_commands(args.site)
    write_commands_tsv(commands, args.out_dir / "commands.tsv")
    log.info("wrote %d commands -> %s/commands.tsv", len(commands), args.out_dir)

    functions = extract_intrinsic_functions(args.site)
    write_intrinsic_functions_tsv(functions, args.out_dir / "intrinsic-functions.tsv")
    log.info(
        "wrote %d intrinsic functions -> %s/intrinsic-functions.tsv",
        len(functions),
        args.out_dir,
    )

    svns = extract_special_variables(args.site)
    write_special_variables_tsv(
        svns, args.out_dir / "intrinsic-special-variables.tsv"
    )
    log.info(
        "wrote %d ISVs -> %s/intrinsic-special-variables.tsv",
        len(svns),
        args.out_dir,
    )

    operators = extract_operators(args.site)
    write_operators_tsv(operators, args.out_dir / "operators.tsv")
    log.info("wrote %d operators -> %s/operators.tsv", len(operators), args.out_dir)

    errors = extract_errors(args.site)
    write_errors_tsv(errors, args.out_dir / "errors.tsv")
    log.info("wrote %d errors -> %s/errors.tsv", len(errors), args.out_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Per-source extractor for the YottaDB documentation corpus.

Reads the local clone under ``sources/ydb/repo/`` and writes raw
per-source TSVs under ``per-source/ydb/``. Per spec §6.1 + §7.1, the
extractor is deliberately conservative: it pulls structured facts from
the source's own organisation and records them verbatim, with minimal
interpretation. Reconciliation across sources happens elsewhere.

Heading hierarchy in ``ProgrammersGuide/commands.rst``:
    ``=`` chapter (``6. Commands``)
    ``-`` per-command section (50 commands in v0.1: ``Break``, ``Close``,
        ``Do``, …, plus all ``Z*`` extensions)
    ``+`` examples
    ``~`` keyword/parameter sub-sections

The extractor walks for ``-``-underlined headings, skips the chapter
heading, and pulls the first ``.. code-block::`` after the
"The format of the X command is:" sentence as the format string. The
abbreviation is derived from the leading bracket convention
(``B[REAK]`` → ``B``).
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from dataclasses import dataclass, fields
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_REPO = Path("sources/ydb/repo")
DEFAULT_OUT_DIR = Path("per-source/ydb")

_HEADING_RULE = re.compile(r"^([-=+~^\"])\1{2,}$")
_DASH_RULE = re.compile(r"^-{3,}$")
# A single regex matches the format-intro for both commands and functions.
# Real upstream variants observed (BL-005, BL-008):
#   "The format of the BREAK command is:"          (canonical command)
#   "The format of MERGE command is:"              (missing "the")
#   "The format for the TRESTART command is:"      ("for" not "of")
#   "Publishes... The format of the ZRUPDATE command is:"  (mid-line)
#   "The format for the $ASCII function is:"       (canonical function)
# Anchored on "(command|function) is:" so it cannot match unrelated uses
# of "the format of …" elsewhere in prose.
_FORMAT_INTRO = re.compile(
    r"The format (?:of|for) (?:the )?\S+ (?:command|function) is\s*:",
    re.IGNORECASE,
)
_CODE_BLOCK = re.compile(r"^\.\. code-block::")
_ABBREV = re.compile(r"^(\$?[A-Za-z]+)\[")

_ENTRY_COLUMNS: tuple[str, ...] = (
    "canonical_name",
    "abbreviation",
    "format",
    "standard_status_hint",
    "source_section",
    "description",
)
_COMMAND_COLUMNS = _ENTRY_COLUMNS  # legacy alias retained for clarity


@dataclass(frozen=True)
class YdbEntry:
    """Shared shape for command/function/svn rows from the YDB docs."""

    canonical_name: str
    abbreviation: str
    format: str
    standard_status_hint: str
    source_section: str
    description: str


# Backwards-compatible aliases. Concept-specific names keep test code
# expressive without paying for a second dataclass per concept.
YdbCommand = YdbEntry
YdbFunction = YdbEntry


def extract_commands(commands_rst: Path) -> list[YdbEntry]:
    """Extract one entry per ``-``-underlined command heading."""
    return _extract_dash_sections(commands_rst, what="command", z_marker="Z")


def extract_intrinsic_functions(functions_rst: Path) -> list[YdbEntry]:
    """Extract one entry per ``-``-underlined function heading.

    Function headings in YDB look like ``$ASCII()`` or ``$ZBIT Functions``;
    we drop the trailing ``()`` to recover the canonical name. Z-prefix
    detection works on the symbol after ``$``.
    """
    return _extract_dash_sections(functions_rst, what="function", z_marker="$Z")


def extract_special_variables(isv_rst: Path) -> list[YdbEntry]:
    """Extract one entry per ``-``-underlined ISV heading in isv.rst.

    Unlike commands and functions, ISV sections do not contain a
    ``The format … is:`` sentence. The abbreviation form (``$D[EVICE]``)
    appears at the start of the first description paragraph, so we
    parse it from there. Headings that don't look like a single ISV
    name (e.g. ``Trigger ISVs`` group heading) are skipped.
    """
    text = isv_rst.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = _relative_label(isv_rst)
    out: list[YdbEntry] = []

    for start, end, heading in _iter_dash_sections(lines):
        if not heading.startswith("$"):
            continue
        body = lines[start + 2 : end]
        first_para = _first_paragraph(body)
        match = re.match(r"^(\$[A-Za-z]+)(?:\[([A-Za-z]*)\])?", first_para)
        if not match:
            log.warning("no $-form found in first paragraph for ISV %r", heading)
            continue
        abbrev = match.group(1)
        canonical = (abbrev + (match.group(2) or "")).upper()
        # Capture the inline format token verbatim (e.g. "$D[EVICE]").
        fmt_token_match = re.match(r"^(\$[A-Za-z]+(?:\[[A-Za-z]*\])?)", first_para)
        fmt = fmt_token_match.group(1) if fmt_token_match else abbrev
        out.append(
            YdbEntry(
                canonical_name=canonical,
                abbreviation=abbrev,
                format=fmt,
                standard_status_hint=_standard_status(canonical, "$Z"),
                source_section=f"{rel}#{heading}",
                description=first_para,
            )
        )
    out.sort(key=lambda e: e.canonical_name)
    return out


def write_special_variables_tsv(svns: list[YdbEntry], out: Path) -> None:
    _write_entries_tsv(svns, out)


def write_commands_tsv(commands: list[YdbEntry], out: Path) -> None:
    _write_entries_tsv(commands, out)


def write_intrinsic_functions_tsv(functions: list[YdbEntry], out: Path) -> None:
    _write_entries_tsv(functions, out)


def _extract_dash_sections(
    rst_path: Path, *, what: str, z_marker: str
) -> list[YdbEntry]:
    text = rst_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = _relative_label(rst_path)
    out: list[YdbEntry] = []

    for start, end, heading in _iter_dash_sections(lines):
        body = lines[start + 2 : end]
        fmt = _find_format(body)
        if not fmt:
            log.warning("no format string found for %s %r", what, heading)
            continue
        canonical = _canonical_from_format(fmt, want_dollar=(what == "function")) or (
            heading.rstrip("()").upper()
        )
        out.append(
            YdbEntry(
                canonical_name=canonical,
                abbreviation=_abbreviation_from_format(fmt),
                format=fmt,
                standard_status_hint=_standard_status(canonical, z_marker),
                source_section=f"{rel}#{heading}",
                description=_first_paragraph(body),
            )
        )
    out.sort(key=lambda e: e.canonical_name)
    return out


def _write_entries_tsv(entries: list[YdbEntry], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_ENTRY_COLUMNS)
        for entry in entries:
            writer.writerow([getattr(entry, c) for c in _ENTRY_COLUMNS])
    assert {f.name for f in fields(YdbEntry)} >= set(_ENTRY_COLUMNS)


def _standard_status(canonical: str, z_marker: str) -> str:
    return (
        "ydb-extension"
        if canonical.upper().startswith(z_marker.upper())
        else "ansi"
    )


def _iter_dash_sections(lines: list[str]):
    """Yield ``(start, end, heading_text)`` for each ``-``-underlined block.

    ``start`` is the index of the heading text line; ``end`` is the
    index of the next command heading (or len(lines)).
    """
    headings: list[tuple[int, str]] = []
    for i in range(1, len(lines)):
        rule = lines[i]
        prev = lines[i - 1].strip()
        if not prev:
            continue
        if _HEADING_RULE.fullmatch(rule) and _HEADING_RULE.fullmatch(prev):
            # Underline of a previous heading (top of an over+underlined
            # block). Skip — we only want underline-only level-2 headings.
            continue
        if _DASH_RULE.fullmatch(rule) and not _HEADING_RULE.fullmatch(prev):
            headings.append((i - 1, prev))

    for idx, (start, heading) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        yield start, end, heading


def _find_format(body: list[str]) -> str | None:
    """Locate the format string for a section.

    Preferred: the first code-block after a "The format … is:" sentence.
    Fallback (BL-008): if no format-intro sentence appears in the section,
    take the first code-block whose content line looks like a format
    (starts with ``$`` or with an uppercase letter followed by ``[``).
    """
    for j, line in enumerate(body):
        if _FORMAT_INTRO.search(line):
            fmt = _first_codeblock_line(body, j + 1)
            if fmt:
                return fmt

    for j, line in enumerate(body):
        if _CODE_BLOCK.match(line.strip()):
            candidate = _first_codeblock_line(body, j)
            if candidate and (
                candidate.startswith("$")
                or re.match(r"^[A-Z][A-Z]*\[", candidate)
            ):
                return candidate
    return None


def _first_codeblock_line(body: list[str], start: int) -> str | None:
    for k in range(start, len(body)):
        if _CODE_BLOCK.match(body[k].strip()):
            m = k + 1
            while m < len(body) and body[m].strip() == "":
                m += 1
            if m < len(body) and body[m].startswith(" "):
                return body[m].strip()
            return None
    return None


def _abbreviation_from_format(fmt: str) -> str:
    match = _ABBREV.match(fmt)
    return match.group(1) if match else ""


def _canonical_from_format(fmt: str, *, want_dollar: bool = False) -> str | None:
    """Pull the canonical entry name out of a format like B[REAK]."""
    pattern = r"^(\$?[A-Za-z]+)(?:\[([A-Za-z]*)\])?" if want_dollar else (
        r"^([A-Za-z]+)(?:\[([A-Za-z]*)\])?"
    )
    match = re.match(pattern, fmt)
    if not match:
        return None
    head, tail = match.group(1), (match.group(2) or "")
    return (head + tail).upper()


def _first_paragraph(body: list[str]) -> str:
    """Return the first non-empty paragraph below the heading, trimmed.

    Skips RST directives (``..`` lines), the underline of the heading
    itself, and the optional ``.. contents::`` block when present.
    """
    paragraph: list[str] = []
    in_para = False
    for line in body:
        stripped = line.strip()
        if not stripped:
            if in_para:
                break
            continue
        if stripped.startswith(".."):
            continue
        in_para = True
        paragraph.append(stripped)
    # Collapse internal whitespace for stable storage.
    return re.sub(r"\s+", " ", " ".join(paragraph)).strip()


def _relative_label(path: Path) -> str:
    """Path expressed relative to ``sources/ydb/repo/`` when possible."""
    try:
        return path.resolve().relative_to(
            Path("sources/ydb/repo").resolve()
        ).as_posix()
    except (ValueError, FileNotFoundError):
        return path.name


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Extract per-source TSVs from the YottaDB documentation clone."
    )
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    rc = 0
    commands_rst = args.repo / "ProgrammersGuide" / "commands.rst"
    if commands_rst.exists():
        commands = extract_commands(commands_rst)
        write_commands_tsv(commands, args.out_dir / "commands.tsv")
        log.info("wrote %d commands -> %s/commands.tsv", len(commands), args.out_dir)
    else:
        log.error("expected file not found: %s", commands_rst)
        rc = 1

    functions_rst = args.repo / "ProgrammersGuide" / "functions.rst"
    if functions_rst.exists():
        functions = extract_intrinsic_functions(functions_rst)
        write_intrinsic_functions_tsv(
            functions, args.out_dir / "intrinsic-functions.tsv"
        )
        log.info(
            "wrote %d intrinsic functions -> %s/intrinsic-functions.tsv",
            len(functions),
            args.out_dir,
        )
    else:
        log.error("expected file not found: %s", functions_rst)
        rc = 1

    isv_rst = args.repo / "ProgrammersGuide" / "isv.rst"
    if isv_rst.exists():
        svns = extract_special_variables(isv_rst)
        write_special_variables_tsv(
            svns, args.out_dir / "intrinsic-special-variables.tsv"
        )
        log.info(
            "wrote %d ISVs -> %s/intrinsic-special-variables.tsv",
            len(svns),
            args.out_dir,
        )
    else:
        log.error("expected file not found: %s", isv_rst)
        rc = 1

    return rc


if __name__ == "__main__":
    raise SystemExit(main())

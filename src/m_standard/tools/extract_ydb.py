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
_FORMAT_INTRO = re.compile(
    # Real upstream variants observed:
    #   "The format of the BREAK command is:"      (canonical)
    #   "The format of MERGE command is:"          (missing "the")
    #   "The format for the TRESTART command is:"  ("for" not "of")
    #   "Publishes... The format of the ZRUPDATE command is:"  (mid-line)
    # Anchored on "command is:" so it cannot match unrelated uses of
    # "the format of …" elsewhere in prose.
    r"The format (?:of|for) (?:the )?\S+ command is\s*:",
    re.IGNORECASE,
)
_CODE_BLOCK = re.compile(r"^\.\. code-block::")
_ABBREV = re.compile(r"^([A-Za-z]+)\[")

_COMMAND_COLUMNS: tuple[str, ...] = (
    "canonical_name",
    "abbreviation",
    "format",
    "standard_status_hint",
    "source_section",
    "description",
)


@dataclass(frozen=True)
class YdbCommand:
    canonical_name: str
    abbreviation: str
    format: str
    standard_status_hint: str
    source_section: str
    description: str


def extract_commands(commands_rst: Path) -> list[YdbCommand]:
    """Extract one YdbCommand per ``-``-underlined heading in commands.rst.

    Skips the chapter heading (``=``-underlined) and any non-command
    headings (``+`` examples, ``~`` sub-sections).
    """
    text = commands_rst.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = _relative_label(commands_rst)
    out: list[YdbCommand] = []

    for start, end, heading in _iter_command_sections(lines):
        body = lines[start + 2 : end]
        fmt = _find_format(body)
        if not fmt:
            log.warning("no format string found for command %r", heading)
            continue
        canonical = _canonical_from_format(fmt) or heading.upper()
        out.append(
            YdbCommand(
                canonical_name=canonical,
                abbreviation=_abbreviation_from_format(fmt),
                format=fmt,
                standard_status_hint=(
                    "ydb-extension"
                    if canonical.upper().startswith("Z")
                    else "ansi"
                ),
                source_section=f"{rel}#{heading}",
                description=_first_paragraph(body),
            )
        )
    out.sort(key=lambda c: c.canonical_name)
    return out


def write_commands_tsv(commands: list[YdbCommand], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_COMMAND_COLUMNS)
        for cmd in commands:
            writer.writerow([getattr(cmd, c) for c in _COMMAND_COLUMNS])
    # Defensive: dataclass field set must match the column order.
    assert {f.name for f in fields(YdbCommand)} >= set(_COMMAND_COLUMNS)


def _iter_command_sections(lines: list[str]):
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
    for j, line in enumerate(body):
        if _FORMAT_INTRO.search(line):
            for k in range(j + 1, len(body)):
                if _CODE_BLOCK.match(body[k].strip()):
                    # Skip the directive line + any blank lines, then take
                    # the first non-empty indented content line.
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


def _canonical_from_format(fmt: str) -> str | None:
    """Pull the canonical command name out of a format like ``B[REAK]…``."""
    match = re.match(r"^([A-Za-z]+)(?:\[([A-Za-z]*)\])?", fmt)
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

    commands_rst = args.repo / "ProgrammersGuide" / "commands.rst"
    if not commands_rst.exists():
        log.error("expected file not found: %s", commands_rst)
        return 1
    commands = extract_commands(commands_rst)
    write_commands_tsv(commands, args.out_dir / "commands.tsv")
    log.info("wrote %d commands -> %s/commands.tsv", len(commands), args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

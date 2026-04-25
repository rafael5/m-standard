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


_PATCODE_COLUMNS: tuple[str, ...] = (
    "code",
    "description",
    "standard_status_hint",
    "source_section",
)
_ANSI_PATCODES = frozenset("ACELNPU")


@dataclass(frozen=True)
class YdbPatternCode:
    code: str
    description: str
    standard_status_hint: str
    source_section: str


def extract_pattern_codes(langfeat_rst: Path) -> list[YdbPatternCode]:
    """Parse the "The pattern codes are:" RST grid table from langfeat.rst.

    Each row is a single-character code + description. The standard ANSI
    codes are A, C, E, L, N, P, U; anything else is a YDB extension.
    """
    text = langfeat_rst.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = _relative_label(langfeat_rst)
    out: list[YdbPatternCode] = []

    intro_re = re.compile(r"The pattern codes are\s*:\s*$", re.IGNORECASE)
    intro_idx: int | None = None
    for i, line in enumerate(lines):
        if intro_re.search(line):
            intro_idx = i
            break
    if intro_idx is None:
        return []

    rows = _read_rst_grid_table(lines, intro_idx + 1)
    for row in rows:
        if len(row) < 2 or row[0].strip().lower() == "code":
            continue
        code = row[0].strip()
        if not code or len(code) > 2:
            continue
        out.append(
            YdbPatternCode(
                code=code,
                description=re.sub(r"\s+", " ", row[1].strip()),
                standard_status_hint=(
                    "ansi" if code.upper() in _ANSI_PATCODES else "ydb-extension"
                ),
                source_section=f"{rel}#pattern-codes",
            )
        )
    out.sort(key=lambda p: p.code)
    return out


def write_pattern_codes_tsv(codes: list[YdbPatternCode], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_PATCODE_COLUMNS)
        for code in codes:
            writer.writerow([getattr(code, c) for c in _PATCODE_COLUMNS])


_OPERATOR_COLUMNS: tuple[str, ...] = (
    "symbol",
    "operator_class",
    "description",
    "standard_status_hint",
    "source_section",
)
# Class label ↔ "The X operators are:" intro line in langfeat.rst.
_OPERATOR_INTROS: tuple[tuple[str, str], ...] = (
    ("arithmetic", r"The arithmetic operators are\s*:\s*$"),
    ("logical", r"The logical operators are\s*:\s*$"),
    ("numeric-relational", r"The numeric relational operators are\s*:\s*$"),
    ("string-relational", r"The string relational operators are\s*:\s*$"),
)


@dataclass(frozen=True)
class YdbOperator:
    symbol: str
    operator_class: str
    description: str
    standard_status_hint: str
    source_section: str


def extract_operators(langfeat_rst: Path) -> list[YdbOperator]:
    """Parse YDB's four operator grid tables in langfeat.rst.

    Classes captured: arithmetic, logical, numeric-relational,
    string-relational.
    """
    text = langfeat_rst.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = _relative_label(langfeat_rst)
    out: list[YdbOperator] = []

    for cls, intro_pattern in _OPERATOR_INTROS:
        intro_re = re.compile(intro_pattern, re.IGNORECASE)
        intro_idx = next(
            (i for i, line in enumerate(lines) if intro_re.search(line)), None
        )
        if intro_idx is None:
            log.warning("operator intro %r not found", intro_pattern)
            continue
        rows = _read_rst_grid_table(lines, intro_idx + 1)
        for row in rows:
            if len(row) < 2 or row[0].strip().lower() == "operator":
                continue
            symbol = _strip_rst_escapes(row[0]).strip()
            if not symbol:
                continue
            out.append(
                YdbOperator(
                    symbol=symbol,
                    operator_class=cls,
                    description=re.sub(r"\s+", " ", row[1].strip()),
                    standard_status_hint="ansi",
                    source_section=f"{rel}#{cls}-operators",
                )
            )
    out.sort(key=lambda o: (o.operator_class, o.symbol))
    return out


def write_operators_tsv(ops: list[YdbOperator], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_OPERATOR_COLUMNS)
        for op in ops:
            writer.writerow([getattr(op, c) for c in _OPERATOR_COLUMNS])


_ENVIRONMENT_COLUMNS: tuple[str, ...] = (
    "name",
    "kind",
    "summary",
    "standard_status_hint",
    "source_section",
)


@dataclass(frozen=True)
class YdbEnvironmentEntry:
    name: str
    kind: str
    summary: str
    standard_status_hint: str
    source_section: str


def extract_environment(ioproc_rst: Path) -> list[YdbEnvironmentEntry]:
    """Extract device I/O parameter entries from ProgrammersGuide/ioproc.rst.

    Per spec §5.7, the environment family is the most heterogeneous —
    process model, lock semantics, transaction semantics, device I/O
    parameters, namespace and routine resolution. v1.0 captures the
    most well-bounded subset: device I/O parameters (the keyword
    arguments to OPEN / USE / CLOSE), which appear in ioproc.rst as
    ``~``-underlined sub-headings under their command sections.

    Per spec §5.7 + BL-009, the rest of the environment family
    (lock/transaction/error-handling semantics) is covered by entries
    already in commands.tsv (LOCK, TSTART, TCOMMIT, TROLLBACK,
    TRESTART) and intrinsic-special-variables.tsv ($ETRAP, $ECODE,
    $ESTACK, $STACK).
    """
    text = ioproc_rst.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = _relative_label(ioproc_rst)
    out: list[YdbEnvironmentEntry] = []

    seen: set[str] = set()
    for i in range(1, len(lines)):
        if not re.fullmatch(r"~{3,}", lines[i]):
            continue
        heading = lines[i - 1].strip()
        if not heading or not _looks_like_device_parameter(heading):
            continue
        if heading in seen:
            continue
        seen.add(heading)
        body = lines[i + 1 : i + 50]  # Description usually within 50 lines.
        summary = _first_paragraph(body)
        out.append(
            YdbEnvironmentEntry(
                name=heading,
                kind="device-parameter",
                summary=summary,
                standard_status_hint=_standard_status(heading, "Z"),
                source_section=f"{rel}#{heading}",
            )
        )
    out.sort(key=lambda e: e.name)
    return out


def _looks_like_device_parameter(heading: str) -> bool:
    """Filter rule: uppercase ASCII-only single token, length 2-15.

    This excludes utility sub-headings ("USE Device Parameters",
    "Direct Mode Editing", "User Interface") and ISVs ($DEVICE, $IO,
    $X, etc.) which already appear in intrinsic-special-variables.tsv.
    """
    if not (2 <= len(heading) <= 15):
        return False
    if " " in heading:
        return False
    if heading.startswith("$"):
        return False
    return all(ch.isupper() or ch.isdigit() or ch == "_" for ch in heading)


def write_environment_tsv(entries: list[YdbEnvironmentEntry], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_ENVIRONMENT_COLUMNS)
        for entry in entries:
            writer.writerow([getattr(entry, c) for c in _ENVIRONMENT_COLUMNS])


_ERROR_COLUMNS: tuple[str, ...] = (
    "mnemonic",
    "summary",
    "kind",
    "standard_status_hint",
    "source_section",
)


@dataclass(frozen=True)
class YdbError:
    mnemonic: str
    summary: str
    kind: str
    standard_status_hint: str
    source_section: str


def extract_errors(errors_rst: Path) -> list[YdbError]:
    """Walk MessageRecovery/errors.rst dash-section per-mnemonic entries.

    Each section is headed by an uppercase mnemonic; the first paragraph
    starts with ``MNEMONIC, summary text``. The next paragraph often
    classifies the error (Compile Time Error / Run-time Error / Warning).
    All YDB error mnemonics are recorded as ``ydb-extension`` because
    YDB does not catalogue the ANSI ``M1``–``M75`` set in this file.
    """
    text = errors_rst.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = _relative_label(errors_rst)
    out: list[YdbError] = []

    for start, end, heading in _iter_dash_sections(lines):
        if not re.fullmatch(r"[A-Z][A-Z0-9]+", heading):
            continue
        body = lines[start + 2 : end]
        first = _first_paragraph(body)
        # Strip the leading "MNEMONIC, " prefix to keep the summary clean.
        summary = re.sub(rf"^{re.escape(heading)}\s*,\s*", "", first)
        kind = _detect_error_kind(body)
        out.append(
            YdbError(
                mnemonic=heading,
                summary=summary,
                kind=kind,
                standard_status_hint="ydb-extension",
                source_section=f"{rel}#{heading}",
            )
        )
    out.sort(key=lambda e: e.mnemonic)
    return out


def write_errors_tsv(errors: list[YdbError], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_ERROR_COLUMNS)
        for err in errors:
            writer.writerow([getattr(err, c) for c in _ERROR_COLUMNS])


def _detect_error_kind(body: list[str]) -> str:
    text = " ".join(body)
    for marker in ("Compile Time Error", "Run-time Error", "Run Time Error",
                   "Warning", "Information", "Fatal", "Error"):
        if marker in text:
            return marker
    return ""


def _strip_rst_escapes(s: str) -> str:
    r"""RST escapes like `\+` collapse to `+`; `\\` collapses to `\`.

    Strip *one* backslash from each backslash-escape pair so that the
    integer-division operator (rendered as ``\\``) is preserved as a
    single ``\`` rather than disappearing entirely.
    """
    return re.sub(r"\\(.)", r"\1", s)


def _read_rst_grid_table(lines: list[str], start: int) -> list[list[str]]:
    """Parse one RST grid table beginning at or after ``start``.

    Skips blank lines, finds the first ``+---`` rule, and reads
    consecutive content lines (those starting with ``|``) until a rule
    that's followed by a non-rule line. Returns a list of rows; each
    row is a list of cell texts (one per pipe-delimited column).
    """
    i = start
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or not lines[i].lstrip().startswith("+"):
        return []

    rows: list[list[str]] = []
    current: list[str] | None = None
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("+"):
            if current is not None:
                rows.append([c.strip() for c in current])
                current = None
            # Continue past rules; bail when we leave the table.
            if i + 1 >= len(lines) or not lines[i + 1].lstrip().startswith("|"):
                break
        elif stripped.startswith("|"):
            cells = [c for c in stripped.strip("|").split("|")]
            if current is None:
                current = list(cells)
            else:
                # Multi-line cell continuation: append to existing cells.
                for j in range(min(len(current), len(cells))):
                    current[j] = (current[j] + " " + cells[j]).strip()
        else:
            break
        i += 1
    return rows


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

    langfeat_rst = args.repo / "ProgrammersGuide" / "langfeat.rst"
    if langfeat_rst.exists():
        codes = extract_pattern_codes(langfeat_rst)
        write_pattern_codes_tsv(codes, args.out_dir / "pattern-codes.tsv")
        log.info(
            "wrote %d pattern codes -> %s/pattern-codes.tsv",
            len(codes),
            args.out_dir,
        )
        ops = extract_operators(langfeat_rst)
        write_operators_tsv(ops, args.out_dir / "operators.tsv")
        log.info(
            "wrote %d operators -> %s/operators.tsv",
            len(ops),
            args.out_dir,
        )

    errors_rst = args.repo / "MessageRecovery" / "errors.rst"
    if errors_rst.exists():
        errors = extract_errors(errors_rst)
        write_errors_tsv(errors, args.out_dir / "errors.tsv")
        log.info(
            "wrote %d errors -> %s/errors.tsv",
            len(errors),
            args.out_dir,
        )

    ioproc_rst = args.repo / "ProgrammersGuide" / "ioproc.rst"
    if ioproc_rst.exists():
        env = extract_environment(ioproc_rst)
        write_environment_tsv(env, args.out_dir / "environment.tsv")
        log.info(
            "wrote %d environment entries -> %s/environment.tsv",
            len(env),
            args.out_dir,
        )

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

"""SAC pattern-rule linter for M source code.

Applies the subset of XINDEX SAC rules that detect *usage patterns*
(rather than entry names). Per-name violations like ``BREAK`` or
``ZWRITE`` are flagged by static-analysis tools that consume the
``mappings/va-sac.tsv`` overlay; this linter handles what the
overlay can't — patterns like "READ without timeout" or
"exclusive Kill" that need to look at how a token is *used*.

Coverage in v0.2 (8 rules):

  Rule  Severity  Pattern
  ----  --------  ----------------------------------------------------
   13   W         Trailing whitespace at end of line
   19   S         Line longer than 245 bytes
   22   S         Exclusive Kill — KILL with parenthesised arg list
   23   S         Unargumented Kill — KILL with no argument
   26   S         Exclusive or Unargumented NEW
   33   S         READ command without timeout
   47   S         Lowercase command(s) used
   60   S         LOCK without timeout

This is **regex-based**, not a real M parser. Patterns that need
true syntax awareness (matched parens across line breaks, comment
stripping inside strings, indirection resolution) are out of scope
— they belong in tree-sitter-m once that grammar exists. The
linter is good enough to flag obvious violations in standard
single-line M; it will both miss subtle patterns and flag false
positives in pathological code (string literals containing the
patterns, etc.). Treat findings as advisory.

Severity codes mirror XINDEX's: F (Fatal), S (Standard / SAC
violation), W (Warning), I (Info).
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

log = logging.getLogger(__name__)

_FINDINGS_COLUMNS: tuple[str, ...] = (
    "file", "line", "column", "rule_id", "severity", "message", "snippet",
)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int          # 1-based
    column: int        # 1-based; 0 means whole-line
    rule_id: int
    severity: str      # F / S / W / I
    message: str
    snippet: str


def lint_source(path: Path) -> Iterator[Finding]:
    """Lint a single M source file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    yield from lint_text(text, filename=str(path))


def lint_text(text: str, *, filename: str) -> Iterator[Finding]:
    """Lint M source text, yielding one Finding per detected violation."""
    for lineno, raw in enumerate(text.splitlines(), start=1):
        # Skip the first line (routine label / header) for some rules
        # but apply rule 13 / 19 to every line.
        is_header = lineno == 1
        yield from _check_line(filename, lineno, raw, is_header=is_header)


# ----- per-rule detectors ----------------------------------------------------

def _check_line(
    filename: str, lineno: int, line: str, *, is_header: bool
) -> Iterator[Finding]:
    # Rule 13: trailing whitespace.
    if line and line[-1] in (" ", "\t") and line.strip():
        # Ignore lines that are entirely whitespace (probably blank).
        yield _find(
            filename, lineno, len(line.rstrip()) + 1,
            rule_id=13, severity="W",
            message="Trailing whitespace at end of line.",
            snippet=line,
        )

    # Rule 19: line >245 bytes.
    if len(line.encode("utf-8")) > 245:
        yield _find(
            filename, lineno, 246,
            rule_id=19, severity="S",
            message=f"Line is {len(line.encode('utf-8'))} bytes (max 245).",
            snippet=line[:80] + "…",
        )

    # The pattern detectors below ignore the header line (label + ;
    # comment) since those don't carry M code.
    if is_header:
        return

    # Tokenize loosely on whitespace runs to inspect command usage.
    # M lines start with a single leading space then commands, so we
    # work on the stripped line for command-level patterns and rely
    # on the original for column reporting.
    body = line.lstrip(" \t")
    if not body or body.startswith(";"):
        return  # blank or comment-only

    # Strip inline comment (everything after ;) for command analysis.
    code = _strip_comment_outside_strings(body)

    # Rule 22 / 23: KILL variants.
    yield from _kill_rules(filename, lineno, line, code)

    # Rule 26: NEW variants.
    yield from _new_rules(filename, lineno, line, code)

    # Rule 33: READ without timeout.
    yield from _read_rule(filename, lineno, line, code)

    # Rule 47: lowercase command at start of statement.
    yield from _lowercase_rule(filename, lineno, line, code)

    # Rule 60: LOCK without timeout.
    yield from _lock_rule(filename, lineno, line, code)


_KILL_EXCL_RE = re.compile(r"^(?:K|KILL):?[^ ]*\s+\(", re.IGNORECASE)
_KILL_UNARG_RE = re.compile(r"^(?:K|KILL):?[^ ]*\s\s", re.IGNORECASE)


def _kill_rules(file: str, line: int, raw: str, code: str) -> Iterator[Finding]:
    if _KILL_EXCL_RE.match(code):
        yield _find(
            file, line, 0, rule_id=22, severity="S",
            message=(
                "Exclusive Kill (KILL with parenthesised arg list) — "
                "keeps only listed vars."
            ),
            snippet=raw,
        )
    elif _KILL_UNARG_RE.match(code):
        yield _find(
            file, line, 0, rule_id=23, severity="S",
            message="Unargumented Kill — kills every variable in scope.",
            snippet=raw,
        )


_NEW_EXCL_RE = re.compile(r"^(?:N|NEW):?[^ ]*\s+\(", re.IGNORECASE)
_NEW_UNARG_RE = re.compile(r"^(?:N|NEW):?[^ ]*\s\s", re.IGNORECASE)


def _new_rules(file: str, line: int, raw: str, code: str) -> Iterator[Finding]:
    if _NEW_EXCL_RE.match(code) or _NEW_UNARG_RE.match(code):
        yield _find(
            file, line, 0, rule_id=26, severity="S",
            message="Exclusive or Unargumented NEW.",
            snippet=raw,
        )


# Match READ that doesn't include a ``:T`` timeout on its first argument.
_READ_RE = re.compile(
    r"^(?:R|READ)(?::[^ ]+)?\s+(?P<arg>[^,\s]+)",
    re.IGNORECASE,
)


def _read_rule(file: str, line: int, raw: str, code: str) -> Iterator[Finding]:
    match = _READ_RE.match(code)
    if not match:
        return
    arg = match.group("arg")
    # If the argument carries its own ":<timeout>" suffix, it's fine.
    # Strip leading * (READ *X) and # (READ X#5).
    arg_for_check = arg.lstrip("*#")
    if ":" not in arg_for_check:
        yield _find(
            file, line, 0, rule_id=33, severity="S",
            message="READ without timeout — process can block forever.",
            snippet=raw,
        )


_COMMAND_AT_START = re.compile(r"^([A-Za-z][A-Za-z]*)(?::|[ \t])")


def _lowercase_rule(file: str, line: int, raw: str, code: str) -> Iterator[Finding]:
    match = _COMMAND_AT_START.match(code)
    if match:
        cmd = match.group(1)
        if cmd != cmd.upper():
            yield _find(
                file, line, 0, rule_id=47, severity="S",
                message=f"Lowercase command {cmd!r} — SAC requires uppercase.",
                snippet=raw,
            )


_LOCK_RE = re.compile(
    r"^(?:L|LOCK)(?::[^ ]+)?\s+(?P<arg>[^\s]+)",
    re.IGNORECASE,
)


def _lock_rule(file: str, line: int, raw: str, code: str) -> Iterator[Finding]:
    match = _LOCK_RE.match(code)
    if not match:
        return
    arg = match.group("arg")
    # LOCK reference may be "+^FOO", "-^FOO", "(^A,^B)", etc.
    # Timeout is ":N" appended after the reference list.
    # Strip leading +/- sign for the check.
    if ":" not in arg.lstrip("+-"):
        yield _find(
            file, line, 0, rule_id=60, severity="S",
            message="LOCK without timeout — process can block forever.",
            snippet=raw,
        )


# ----- helpers --------------------------------------------------------------

def _strip_comment_outside_strings(s: str) -> str:
    """Drop the M comment (everything after ; outside string literals)."""
    out: list[str] = []
    in_str = False
    for ch in s:
        if ch == '"':
            in_str = not in_str
            out.append(ch)
        elif ch == ";" and not in_str:
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _find(
    file: str, line: int, column: int, *,
    rule_id: int, severity: str, message: str, snippet: str,
) -> Finding:
    return Finding(
        file=file, line=line, column=column,
        rule_id=rule_id, severity=severity,
        message=message, snippet=snippet,
    )


def write_findings_tsv(findings: Iterable[Finding], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_FINDINGS_COLUMNS)
        for x in findings:
            writer.writerow([
                x.file, x.line, x.column, x.rule_id,
                x.severity, x.message, x.snippet,
            ])


# ----- CLI ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Lint M source against XINDEX SAC pattern rules."
    )
    parser.add_argument("paths", nargs="+", type=Path,
                        help="M source files to lint.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Optional output TSV path (default: stdout).")
    parser.add_argument(
        "--severity", default="FSWI",
        help="Severities to include (default: FSWI = all).",
    )
    args = parser.parse_args(argv)

    accepted = set(args.severity.upper())
    findings: list[Finding] = []
    for p in args.paths:
        for f in lint_source(p):
            if f.severity in accepted:
                findings.append(f)

    if args.out:
        write_findings_tsv(findings, args.out)
        log.info("wrote %d findings -> %s", len(findings), args.out)
    else:
        for f in findings:
            tag = f"[{f.severity}{f.rule_id:02d}]"
            print(f"{f.file}:{f.line}:{f.column}\t{tag} {f.message}")
    return 1 if any(f.severity in ("F", "S") for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())

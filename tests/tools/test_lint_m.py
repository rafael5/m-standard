"""Tests for the SAC pattern-rule M linter.

The linter takes M source files and applies the subset of XINDEX
SAC rules that detect usage *patterns* (rather than entry names).
Per-name violations (BREAK, ZWRITE, $ZHOROLOG, etc.) live in the
va-sac.tsv overlay and are flagged by static analysis tools that
consume that overlay; this linter handles what the overlay can't.

Coverage in v0.2:

  Rule  Severity  Pattern
  ----  --------  ----------------------------------------------------
   13   W         Trailing whitespace at end of line
   19   S         Line longer than 245 bytes
   22   S         Exclusive Kill — KILL with parenthesised arg list
   23   S         Unargumented Kill — KILL with no argument
   26   S         Exclusive or Unargumented NEW
   33   S         READ command without timeout (e.g. R X without :T)
   47   S         Lowercase command(s) used (write/set/do)
   60   S         LOCK without timeout
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.lint_m import (
    Finding,
    lint_source,
    lint_text,
)


def _findings_for(text: str, filename: str = "test.m") -> list[Finding]:
    return list(lint_text(text, filename=filename))


# ----- per-rule tests --------------------------------------------------------

def test_rule_13_trailing_whitespace() -> None:
    text = "TEST ;test\n W \"hi\"   \n"  # trailing spaces on line 2
    findings = _findings_for(text)
    f = next(f for f in findings if f.rule_id == 13)
    assert f.line == 2
    assert f.severity == "W"


def test_rule_19_line_too_long() -> None:
    long_line = " W " + "x" * 250
    findings = _findings_for(f"TEST ;test\n{long_line}\n")
    assert any(f.rule_id == 19 and f.line == 2 for f in findings)


def test_rule_22_exclusive_kill() -> None:
    """KILL (X,Y) — exclusive kill keeps only the listed vars."""
    text = "TEST ;test\n K (X,Y)\n"
    findings = _findings_for(text)
    assert any(f.rule_id == 22 for f in findings)


def test_rule_23_unargumented_kill() -> None:
    """KILL with two trailing spaces (no arg) → kills everything."""
    text = "TEST ;test\n K  W \"after\"\n"
    findings = _findings_for(text)
    assert any(f.rule_id == 23 for f in findings)


def test_rule_26_exclusive_new() -> None:
    """NEW (X,Y) — exclusive new."""
    text = "TEST ;test\n N (X,Y)\n"
    findings = _findings_for(text)
    assert any(f.rule_id == 26 for f in findings)


def test_rule_26_unargumented_new() -> None:
    """NEW with two trailing spaces (no arg) → news everything."""
    text = "TEST ;test\n N  W \"after\"\n"
    findings = _findings_for(text)
    assert any(f.rule_id == 26 for f in findings)


def test_rule_33_read_without_timeout() -> None:
    text = "TEST ;test\n R X\n"
    findings = _findings_for(text)
    assert any(f.rule_id == 33 for f in findings)


def test_rule_33_read_with_timeout_is_clean() -> None:
    """READ X:5 has a timeout; no rule-33 finding."""
    text = "TEST ;test\n R X:5\n"
    findings = _findings_for(text)
    assert not any(f.rule_id == 33 for f in findings)


def test_rule_47_lowercase_command() -> None:
    text = "TEST ;test\n write \"hi\"\n"
    findings = _findings_for(text)
    assert any(f.rule_id == 47 for f in findings)


def test_rule_47_uppercase_is_clean() -> None:
    text = "TEST ;test\n WRITE \"hi\"\n"
    findings = _findings_for(text)
    assert not any(f.rule_id == 47 for f in findings)


def test_rule_60_lock_without_timeout() -> None:
    text = "TEST ;test\n L +^FOO\n"
    findings = _findings_for(text)
    assert any(f.rule_id == 60 for f in findings)


def test_rule_60_lock_with_timeout_is_clean() -> None:
    text = "TEST ;test\n L +^FOO:5\n"
    findings = _findings_for(text)
    assert not any(f.rule_id == 60 for f in findings)


# ----- multi-rule + severity filtering --------------------------------------

def test_lint_clean_routine_yields_no_findings() -> None:
    text = (
        "MYRTN ;namespace test\n"
        " ;;1.0;TEST;**1**;Apr 25, 2026;Build 1\n"
        " W \"hello\",!\n"
        " Q\n"
    )
    findings = _findings_for(text)
    assert findings == []


def test_lint_finding_carries_severity_and_message() -> None:
    text = "TEST ;test\n write \"hi\"\n"
    f = next(f for f in _findings_for(text) if f.rule_id == 47)
    assert f.severity == "S"
    assert f.message  # non-empty
    assert f.snippet.strip().startswith("write")


def test_lint_source_reads_file(tmp_path: Path) -> None:
    src = tmp_path / "TEST.m"
    src.write_text("TEST ;test\n write \"hi\"\n")
    findings = list(lint_source(src))
    assert any(f.rule_id == 47 for f in findings)
    # Filename in the finding is the path passed in (caller-controlled).
    assert findings[0].file == str(src)


def test_lint_writes_tsv(tmp_path: Path) -> None:
    from m_standard.tools.lint_m import write_findings_tsv

    src = tmp_path / "TEST.m"
    src.write_text("TEST ;test\n write \"hi\"   \n")
    findings = list(lint_source(src))
    out = tmp_path / "findings.tsv"
    write_findings_tsv(findings, out)
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].split("\t") == [
        "file", "line", "column", "rule_id", "severity", "message", "snippet",
    ]
    assert len(rows) >= 2  # header + at least one finding

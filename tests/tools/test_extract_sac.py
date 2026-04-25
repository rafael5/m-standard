"""Tests for the XINDEX SAC rule extractor.

XINDX1.m's ``ERROR`` table encodes ~65 SAC rules in the form:

    <rule_id> ;;<exempt_namespaces>;<severity> - <description>

Severity codes: F (Fatal), S (Standard / SAC violation), W (Warning),
I (Info). The extractor parses this table and (separately) projects
the subset of rules that flag specific named entries (commands /
functions / svns) onto a `mappings/va-sac.tsv`-style overlay.
"""

from __future__ import annotations

from pathlib import Path

from m_standard.tools.extract_sac import (
    SacRule,
    derive_overlay,
    parse_xindx1_rules,
)

XINDX1_FIXTURE = """\
XINDX1 ;ISC/REL,GRK,RWF - ERROR ROUTINE ;2018-03-01  10:01 AM
 ;;7.3;TOOLKIT;**header**;Apr 25, 1995;Build 4
 ; Original Routine authored by Department of Veterans Affairs
 G A
ERROR ;
1 ;;;F - UNDEFINED COMMAND (rest of line not checked).
2 ;;X,Z,DI,DD,KMP;F - Non-standard (Undefined) 'Z' command.
20 ;;X,Z,DI,DD,KMP;S - View command used.
25 ;;;S - Break command used.
27 ;;X,Z,DI,DD,KMP;S - $View function used.
28 ;;X,Z,DI,DD,KMP;S - Non-standard $Z special variable used.
31 ;;X,Z,DI,DD,KMP;S - Non-standard $Z function used.
32 ;;X,Z,DI,DD,KMP;S - 'HALT' command should be invoked through 'G ^XUSCLEAN'.
36 ;;X,Z,DI,DD,KMP;S - Should use 'TASKMAN' instead of 'JOB' command.
65 ;;X,Z,DI,DD,KMP;S - Vendor specific code is not allowed (SACC 2.2.8)
"""


def test_parse_xindx1_rules_extracts_each(tmp_path: Path) -> None:
    src = tmp_path / "XINDX1.m"
    src.write_text(XINDX1_FIXTURE)
    rules = parse_xindx1_rules(src)
    ids = sorted(r.rule_id for r in rules)
    assert ids == [1, 2, 20, 25, 27, 28, 31, 32, 36, 65]


def test_parse_xindx1_rules_records_severity_and_description(
    tmp_path: Path,
) -> None:
    src = tmp_path / "XINDX1.m"
    src.write_text(XINDX1_FIXTURE)
    by_id = {r.rule_id: r for r in parse_xindx1_rules(src)}
    assert by_id[2].severity == "F"
    assert "Z' command" in by_id[2].description
    assert by_id[25].severity == "S"
    assert "Break command" in by_id[25].description


def test_parse_xindx1_rules_records_exempt_namespaces(tmp_path: Path) -> None:
    src = tmp_path / "XINDX1.m"
    src.write_text(XINDX1_FIXTURE)
    by_id = {r.rule_id: r for r in parse_xindx1_rules(src)}
    # Rule 25 has no exempt namespaces (applies to all routines).
    assert by_id[25].exempt_namespaces == ()
    # Rule 2 exempts X, Z, DI, DD, KMP namespaces.
    assert by_id[2].exempt_namespaces == ("X", "Z", "DI", "DD", "KMP")


def test_derive_overlay_targets_specific_named_entries(tmp_path: Path) -> None:
    """The rules subset that flags specific names projects onto va-sac.tsv."""
    rules = [
        SacRule(rule_id=25, severity="S",
                description="Break command used.",
                exempt_namespaces=()),
        SacRule(rule_id=20, severity="S",
                description="View command used.",
                exempt_namespaces=("X",)),
        SacRule(rule_id=32, severity="S",
                description="'HALT' command should be invoked through 'G ^XUSCLEAN'.",
                exempt_namespaces=()),
        SacRule(rule_id=36, severity="S",
                description="Should use 'TASKMAN' instead of 'JOB' command.",
                exempt_namespaces=()),
    ]
    # Per-source TSV stand-ins (the "universe" the overlay projects onto).
    integrated = {
        "commands": {"BREAK", "VIEW", "HALT", "JOB", "DO", "QUIT"},
        "intrinsic-functions": {"$VIEW", "$ASCII"},
        "intrinsic-special-variables": {"$DEVICE"},
    }
    overlay = derive_overlay(rules, integrated)
    by_key = {(r["concept"], r["name"]): r for r in overlay}
    # Specific commands flagged by single rules.
    assert by_key[("commands", "BREAK")]["sac_status"] == "forbidden"
    assert by_key[("commands", "VIEW")]["sac_status"] == "forbidden"
    assert by_key[("commands", "HALT")]["sac_status"] == "restricted"
    assert by_key[("commands", "JOB")]["sac_status"] == "restricted"
    assert by_key[("commands", "BREAK")]["sac_section"] == "XINDEX rule 25 (severity S)"
    # Things rule didn't target stay out of the overlay.
    assert ("commands", "DO") not in by_key
    assert ("commands", "QUIT") not in by_key


def test_derive_overlay_z_extension_rules_fan_out(tmp_path: Path) -> None:
    """Rules 2/28/31 (any Z* command/svn/function) flag every Z-prefixed entry."""
    rules = [
        SacRule(rule_id=2, severity="F",
                description="Non-standard (Undefined) 'Z' command.",
                exempt_namespaces=("X", "Z")),
        SacRule(rule_id=28, severity="S",
                description="Non-standard $Z special variable used.",
                exempt_namespaces=()),
        SacRule(rule_id=31, severity="S",
                description="Non-standard $Z function used.",
                exempt_namespaces=()),
    ]
    integrated = {
        "commands": {"BREAK", "ZBREAK", "ZWRITE", "ZTRIGGER"},
        "intrinsic-functions": {"$ASCII", "$ZASCII", "$ZSEARCH"},
        "intrinsic-special-variables": {"$DEVICE", "$ZHOROLOG", "$ZTRAP"},
    }
    overlay = derive_overlay(rules, integrated)
    by_key = {(r["concept"], r["name"]): r for r in overlay}
    # Every Z-prefixed entry tagged forbidden by the broad rules.
    assert by_key[("commands", "ZBREAK")]["sac_status"] == "forbidden"
    assert by_key[("commands", "ZWRITE")]["sac_status"] == "forbidden"
    assert by_key[("commands", "ZTRIGGER")]["sac_status"] == "forbidden"
    assert by_key[("intrinsic-functions", "$ZSEARCH")]["sac_status"] == "forbidden"
    assert by_key[("intrinsic-special-variables", "$ZHOROLOG")]["sac_status"] == "forbidden"
    # Non-Z entries not flagged.
    assert ("commands", "BREAK") not in by_key
    assert ("intrinsic-functions", "$ASCII") not in by_key

"""Parse XINDEX SAC rules from XINDX1.m and project onto va-sac.tsv.

XINDEX is the operational SAC validator the VA runs against VistA M
routines. XINDX1.m's ``ERROR`` table encodes ~65 SAC rules in the form:

    <rule_id> ;;<exempt_namespaces>;<severity> - <description>

Severity codes:
- ``F`` — Fatal (parser / language error)
- ``S`` — Standard (SAC violation)
- ``W`` — Warning
- ``I`` — Info

This module:

1. Parses XINDX1's ERROR table into ``SacRule`` records.
2. Writes the full rule list to ``integrated/va-sac-rules.tsv``
   (input for downstream linters that flag pattern-level
   violations like "READ without timeout").
3. Projects the subset of rules that target *specific named entries*
   (e.g. "BREAK command used", "Non-standard $Z function used")
   onto ``mappings/va-sac.tsv``, the per-name overlay consumed by
   ``emit_sac_compliance``.

Rules that don't target a specific name (rule 22 "Exclusive Kill",
rule 33 "READ without timeout", rule 60 "LOCK without timeout") are
recorded in the rules table but don't appear in the overlay — they
need usage-pattern analysis, not name lookup.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_XINDX1 = Path("sources/sac/routines/XINDX1.m")
DEFAULT_INTEGRATED_DIR = Path("integrated")
DEFAULT_RULES_OUT = Path("integrated/va-sac-rules.tsv")
DEFAULT_OVERLAY_OUT = Path("mappings/va-sac.tsv")

_RULES_COLUMNS: tuple[str, ...] = (
    "rule_id",
    "severity",
    "exempt_namespaces",
    "description",
)
_OVERLAY_COLUMNS: tuple[str, ...] = (
    "concept",
    "name",
    "sac_status",
    "sac_section",
    "notes",
)

# Rule line: ``<id> ;;<exempt>;<severity> - <description>``
_RULE_LINE = re.compile(
    r"^(?P<id>\d+)\s*;;(?P<exempt>[^;]*);(?P<severity>[FSWI])\s*-\s*(?P<desc>.*)$"
)


@dataclass(frozen=True)
class SacRule:
    rule_id: int
    severity: str           # F / S / W / I
    exempt_namespaces: tuple[str, ...]
    description: str


def parse_xindx1_rules(path: Path) -> list[SacRule]:
    """Parse the ERROR table from XINDX1.m into SacRule records."""
    text = path.read_text(encoding="utf-8")
    in_error_section = False
    out: list[SacRule] = []
    for line in text.splitlines():
        if line.strip().startswith("ERROR"):
            in_error_section = True
            continue
        if not in_error_section:
            continue
        match = _RULE_LINE.match(line)
        if not match:
            # Stop when we leave the table — typically the next labeled
            # section starts with a non-numeric line.
            if (
                line
                and not line.startswith(" ")
                and not line.startswith(";")
                and not match
            ):
                break
            continue
        exempt = tuple(
            ns.strip() for ns in match.group("exempt").split(",") if ns.strip()
        )
        out.append(SacRule(
            rule_id=int(match.group("id")),
            severity=match.group("severity"),
            exempt_namespaces=exempt,
            description=match.group("desc").strip(),
        ))
    return out


# Rules that flag specific named entries. Maps rule_id → (concept,
# matcher, sac_status). The matcher is either a string (exact
# canonical match) or a callable taking (concept, name) → bool for
# the broad Z-extension rules.
_SPECIFIC_RULE_TARGETS: dict[int, tuple[str, str | None, str]] = {
    20: ("commands", "VIEW", "forbidden"),
    25: ("commands", "BREAK", "forbidden"),
    27: ("intrinsic-functions", "$VIEW", "forbidden"),
    32: ("commands", "HALT", "restricted"),
    36: ("commands", "JOB", "restricted"),
}

# Broad Z-extension rules: every entry in the named concept whose
# canonical name starts with the given prefix is flagged.
_BROAD_RULE_TARGETS: dict[int, tuple[str, str, str]] = {
    2: ("commands", "Z", "forbidden"),
    28: ("intrinsic-special-variables", "$Z", "forbidden"),
    31: ("intrinsic-functions", "$Z", "forbidden"),
}


def derive_overlay(
    rules: list[SacRule],
    integrated: dict[str, set[str]],
) -> list[dict[str, str]]:
    """Project rules onto a list of va-sac.tsv-shaped overlay rows.

    ``integrated`` maps concept ('commands', 'intrinsic-functions',
    'intrinsic-special-variables') to the set of canonical names
    present in the corresponding integrated TSV. The overlay is the
    intersection of "rule targets" with "names that exist".
    """
    rules_by_id = {r.rule_id: r for r in rules}
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for rule_id, (concept, exact_name, status) in _SPECIFIC_RULE_TARGETS.items():
        rule = rules_by_id.get(rule_id)
        if rule is None or exact_name not in integrated.get(concept, set()):
            continue
        key = (concept, exact_name)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "concept": concept,
            "name": exact_name,
            "sac_status": status,
            "sac_section": f"XINDEX rule {rule_id} (severity {rule.severity})",
            "notes": rule.description,
        })

    for rule_id, (concept, prefix, status) in _BROAD_RULE_TARGETS.items():
        rule = rules_by_id.get(rule_id)
        if rule is None:
            continue
        for name in sorted(integrated.get(concept, set())):
            if not name.upper().startswith(prefix.upper()):
                continue
            key = (concept, name)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "concept": concept,
                "name": name,
                "sac_status": status,
                "sac_section": f"XINDEX rule {rule_id} (severity {rule.severity})",
                "notes": rule.description,
            })

    out.sort(key=lambda r: (r["concept"], r["name"]))
    return out


def write_rules_tsv(rules: list[SacRule], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_RULES_COLUMNS)
        for r in sorted(rules, key=lambda x: x.rule_id):
            writer.writerow([
                r.rule_id, r.severity,
                ",".join(r.exempt_namespaces), r.description,
            ])


def write_overlay_tsv(overlay: list[dict[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_OVERLAY_COLUMNS)
        for r in overlay:
            writer.writerow([r[c] for c in _OVERLAY_COLUMNS])


def _read_canonical_names(integrated_dir: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for concept in ("commands", "intrinsic-functions", "intrinsic-special-variables"):
        path = integrated_dir / f"{concept}.tsv"
        if not path.exists():
            out[concept] = set()
            continue
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            out[concept] = {row["canonical_name"] for row in reader}
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Parse XINDEX SAC rules + derive the va-sac.tsv overlay."
    )
    parser.add_argument("--xindx1", type=Path, default=DEFAULT_XINDX1)
    parser.add_argument(
        "--integrated", type=Path, default=DEFAULT_INTEGRATED_DIR
    )
    parser.add_argument("--rules-out", type=Path, default=DEFAULT_RULES_OUT)
    parser.add_argument("--overlay-out", type=Path, default=DEFAULT_OVERLAY_OUT)
    args = parser.parse_args(argv)

    if not args.xindx1.exists():
        log.error(
            "%s not found — run `bash tools/clone-sac.sh` first",
            args.xindx1,
        )
        return 1

    rules = parse_xindx1_rules(args.xindx1)
    write_rules_tsv(rules, args.rules_out)
    log.info("wrote %d SAC rules -> %s", len(rules), args.rules_out)

    integrated = _read_canonical_names(args.integrated)
    overlay = derive_overlay(rules, integrated)
    write_overlay_tsv(overlay, args.overlay_out)
    log.info(
        "wrote %d derived overlay entries -> %s",
        len(overlay), args.overlay_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

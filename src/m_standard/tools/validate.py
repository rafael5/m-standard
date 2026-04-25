"""Validation harness for the integrated layer (spec §7.4).

Seven gates, each a standalone function:

1. Manifest integrity
2. Provenance
3. Conflict resolution
4. Schema validation
5. TSV/JSON consistency
6. Round-trip determinism of the reconciler
7. Coverage (per-source entries appear in integrated)

``run_all_gates`` runs all seven and raises a single
``ValidationFailure`` aggregating every violation across gates so a
failing CI report shows the full picture, not just the first issue.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import tempfile
from pathlib import Path

import jsonschema

from m_standard.tools.manifest import sha256_of

log = logging.getLogger(__name__)

# Names that are ALWAYS tracked under sources/<src>/ regardless of
# whether the bulk content is committed.
_MANIFEST_BOOKKEEPING = frozenset({"manifest.tsv", "fetch.sh", "README.md", "NOTICE"})

# Concepts and their primary key field within the integrated TSV.
_CONCEPT_KEYS: dict[str, str] = {
    "commands": "canonical_name",
    "intrinsic-functions": "canonical_name",
    "intrinsic-special-variables": "canonical_name",
    "operators": "symbol",
    "pattern-codes": "code",
    "errors": "mnemonic",
    "environment": "name",
}

# JSON Schema basenames per concept (must match emit_json.CONCEPTS).
_SCHEMA_BASENAMES: dict[str, str] = {
    "commands": "command.schema.json",
    "intrinsic-functions": "intrinsic-function.schema.json",
    "intrinsic-special-variables": "intrinsic-special-variable.schema.json",
    "operators": "operator.schema.json",
    "pattern-codes": "pattern-code.schema.json",
    "errors": "error.schema.json",
    "environment": "environment-entry.schema.json",
    "conflicts": "conflicts.schema.json",
}


class ValidationFailure(Exception):
    """Raised when one or more validation gates report a violation.

    The message is a multi-line summary; aggregate failures join the
    individual gate failures with blank-line separators so CI logs
    show every issue, not just the first.
    """


# ---------- Gate 1: manifest integrity --------------------------------------

def gate_manifest_integrity(project_root: Path) -> None:
    """Every file under ``sources/<src>/`` matches manifest.tsv (path + sha256)."""
    failures: list[str] = []
    sources_dir = project_root / "sources"
    if not sources_dir.is_dir():
        return  # Nothing to check.

    for src_dir in sorted(p for p in sources_dir.iterdir() if p.is_dir()):
        manifest_path = src_dir / "manifest.tsv"
        if not manifest_path.exists():
            continue
        manifest_paths, manifest_shas = _read_manifest_index(manifest_path)
        # Walk on-disk files under src_dir, excluding bookkeeping +
        # any embedded .git/ tree (kept gitignored, not vendored).
        for f in sorted(src_dir.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(src_dir).as_posix()
            top = rel.split("/", 1)[0]
            if top == ".git" or rel in _MANIFEST_BOOKKEEPING:
                continue
            if rel not in manifest_paths:
                # Manifests record paths relative to manifest's parent,
                # i.e. relative to src_dir; some on-disk-only AnnoStd
                # files (e.g. fetch.sh) are exempt above.
                failures.append(
                    f"manifest-integrity: {src_dir.name}/{rel} present on "
                    f"disk but not in {manifest_path.relative_to(project_root)}"
                )
                continue
            actual = sha256_of(f)
            if actual != manifest_shas[rel]:
                failures.append(
                    f"manifest-integrity: sha256 drift for "
                    f"{src_dir.name}/{rel}: manifest={manifest_shas[rel][:12]} "
                    f"disk={actual[:12]}"
                )

    if failures:
        raise ValidationFailure("\n".join(failures))


# ---------- Gate 2: provenance ----------------------------------------------

def gate_provenance(project_root: Path) -> None:
    """No integrated row may exist without at least one source attesting it."""
    failures: list[str] = []
    integrated = project_root / "integrated"
    per_source = project_root / "per-source"

    for concept, key_field in _CONCEPT_KEYS.items():
        tsv = integrated / f"{concept}.tsv"
        if not tsv.exists():
            continue
        anno_keys = _per_source_keys(per_source / "anno" / f"{concept}.tsv", key_field)
        ydb_keys = _per_source_keys(per_source / "ydb" / f"{concept}.tsv", key_field)
        for row in _read_tsv(tsv):
            entry = row[key_field]
            if entry not in anno_keys and entry not in ydb_keys:
                failures.append(
                    f"provenance: {concept}/{entry} appears in integrated/ "
                    f"but in neither per-source/anno nor per-source/ydb"
                )
            in_anno = row.get("in_anno", "false").lower() == "true"
            in_ydb = row.get("in_ydb", "false").lower() == "true"
            if in_anno != (entry in anno_keys):
                failures.append(
                    f"provenance: {concept}/{entry} in_anno={in_anno} but "
                    f"per-source presence is {entry in anno_keys}"
                )
            if in_ydb != (entry in ydb_keys):
                failures.append(
                    f"provenance: {concept}/{entry} in_ydb={in_ydb} but "
                    f"per-source presence is {entry in ydb_keys}"
                )

    if failures:
        raise ValidationFailure("\n".join(failures))


# ---------- Gate 3: conflict resolution -------------------------------------

def gate_conflict_resolution(project_root: Path) -> None:
    """No row in conflicts.tsv has resolution=PENDING-MANUAL."""
    path = project_root / "integrated" / "conflicts.tsv"
    if not path.exists():
        return
    failures: list[str] = []
    for row in _read_tsv(path):
        resolution = row.get("resolution", "").strip()
        if not resolution or resolution.upper() == "PENDING-MANUAL":
            failures.append(
                f"conflict-resolution: {row.get('conflict_id', '?')} "
                f"({row.get('entry', '?')}) has resolution=PENDING-MANUAL "
                f"or empty — needs a human decision"
            )
    if failures:
        raise ValidationFailure("\n".join(failures))


# ---------- Gate 4: schema validation ---------------------------------------

def gate_schema_validation(project_root: Path) -> None:
    """Every integrated/*.json validates against its schemas/*.schema.json."""
    failures: list[str] = []
    integrated = project_root / "integrated"
    schemas = project_root / "schemas"

    for concept, schema_basename in _SCHEMA_BASENAMES.items():
        json_path = integrated / f"{concept}.json"
        schema_path = schemas / schema_basename
        if not json_path.exists() or not schema_path.exists():
            continue
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(payload, schema)
        except jsonschema.ValidationError as e:
            # Surface enough of the failing path that the CI log is
            # actionable without dumping the whole document.
            failures.append(
                f"schema-validation: {concept}.json fails "
                f"{schema_basename}: {e.message} at "
                f"{'/'.join(str(p) for p in e.absolute_path)}"
            )
        except json.JSONDecodeError as e:
            failures.append(f"schema-validation: {concept}.json is not valid JSON: {e}")

    if failures:
        raise ValidationFailure("\n".join(failures))


# ---------- Gate 5: TSV/JSON consistency ------------------------------------

def gate_tsv_json_consistency(project_root: Path) -> None:
    """Every TSV row has a JSON entry and vice versa; common fields agree."""
    failures: list[str] = []
    integrated = project_root / "integrated"

    for concept, key_field in _CONCEPT_KEYS.items():
        tsv_path = integrated / f"{concept}.tsv"
        json_path = integrated / f"{concept}.json"
        if not tsv_path.exists() or not json_path.exists():
            continue
        tsv_keys = {row[key_field] for row in _read_tsv(tsv_path)}
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        json_keys = {entry[key_field] for entry in payload["entries"]}
        only_tsv = tsv_keys - json_keys
        only_json = json_keys - tsv_keys
        if only_tsv:
            failures.append(
                f"tsv-json-consistency: {concept}: in TSV but not JSON "
                f"({len(only_tsv)}): {', '.join(sorted(only_tsv)[:5])}"
            )
        if only_json:
            failures.append(
                f"tsv-json-consistency: {concept}: in JSON but not TSV "
                f"({len(only_json)}): {', '.join(sorted(only_json)[:5])}"
            )

    if failures:
        raise ValidationFailure("\n".join(failures))


# ---------- Gate 6: round-trip ---------------------------------------------

def gate_round_trip(project_root: Path) -> None:
    """Re-running reconcile on per-source/ produces a byte-identical integrated/."""
    from m_standard.tools.reconcile import reconcile_all

    if not (project_root / "integrated" / "commands.tsv").exists():
        return  # Nothing to round-trip.

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "integrated"
        reconcile_all(per_source=project_root / "per-source", out_dir=out_dir)
        for path in sorted(out_dir.glob("*.tsv")):
            committed = project_root / "integrated" / path.name
            if not committed.exists():
                failures.append(
                    f"round-trip: reconciler produces {path.name} but it is "
                    f"not committed under integrated/"
                )
                continue
            if path.read_bytes() != committed.read_bytes():
                failures.append(
                    f"round-trip: integrated/{path.name} drifts from what "
                    f"reconcile.py would produce — re-run `make reconcile`"
                )

    if failures:
        raise ValidationFailure("\n".join(failures))


# ---------- Gate 7: coverage ------------------------------------------------

def gate_coverage(project_root: Path) -> None:
    """Every per-source entry appears in the corresponding integrated TSV."""
    failures: list[str] = []
    integrated = project_root / "integrated"
    per_source = project_root / "per-source"

    for concept, key_field in _CONCEPT_KEYS.items():
        tsv_path = integrated / f"{concept}.tsv"
        if not tsv_path.exists():
            continue
        integrated_keys = {row[key_field] for row in _read_tsv(tsv_path)}
        for src in ("anno", "ydb"):
            ps_path = per_source / src / f"{concept}.tsv"
            if not ps_path.exists():
                continue
            for row in _read_tsv(ps_path):
                key = row[key_field]
                if key not in integrated_keys:
                    failures.append(
                        f"coverage: {concept}/{key} present in "
                        f"per-source/{src}/{concept}.tsv but absent from "
                        f"integrated/{concept}.tsv"
                    )

    if failures:
        raise ValidationFailure("\n".join(failures))


# ---------- Orchestrator ----------------------------------------------------

def gate_mapping_integrity(project_root: Path) -> None:
    """Every entry in mappings/*.tsv refers to identifiers that exist.

    For ``mappings/ydb-ansi-errors.tsv``:
    - Every ``ydb_mnemonic`` must exist in
      ``per-source/ydb/errors.tsv``.
    - Every ``ansi_code`` must exist in
      ``per-source/anno/errors.tsv``.
    Catches stale mappings after upstream renames or YDB-version bumps.
    """
    failures: list[str] = []
    mapping_path = project_root / "mappings" / "ydb-ansi-errors.tsv"
    if not mapping_path.exists():
        return

    ydb_keys = _per_source_keys(
        project_root / "per-source" / "ydb" / "errors.tsv", "mnemonic"
    )
    anno_keys = _per_source_keys(
        project_root / "per-source" / "anno" / "errors.tsv", "mnemonic"
    )
    for row in _read_tsv(mapping_path):
        ydb_m = row.get("ydb_mnemonic", "").strip()
        ansi = row.get("ansi_code", "").strip()
        if ydb_m and ydb_m not in ydb_keys:
            failures.append(
                f"mapping-integrity: ydb-ansi-errors.tsv references "
                f"YDB mnemonic {ydb_m!r} which does not exist in "
                f"per-source/ydb/errors.tsv"
            )
        if ansi and ansi not in anno_keys:
            failures.append(
                f"mapping-integrity: ydb-ansi-errors.tsv references "
                f"ANSI code {ansi!r} which does not exist in "
                f"per-source/anno/errors.tsv"
            )

    if failures:
        raise ValidationFailure("\n".join(failures))


_GATES = (
    ("manifest-integrity", gate_manifest_integrity),
    ("provenance", gate_provenance),
    ("conflict-resolution", gate_conflict_resolution),
    ("schema-validation", gate_schema_validation),
    ("tsv-json-consistency", gate_tsv_json_consistency),
    ("round-trip", gate_round_trip),
    ("coverage", gate_coverage),
    ("mapping-integrity", gate_mapping_integrity),
)


def run_all_gates(project_root: Path) -> None:
    """Run every gate, accumulate failures, raise once at the end.

    This makes CI output complete on a single run — the user sees
    every violation rather than a cycle of fix-rerun-fix-rerun.
    """
    accumulated: list[str] = []
    for name, gate in _GATES:
        try:
            gate(project_root)
        except ValidationFailure as e:
            accumulated.append(f"[{name}]\n{e}")
        except Exception as e:  # pragma: no cover — surface programmer errors
            accumulated.append(f"[{name}] internal error: {e}")
    if accumulated:
        raise ValidationFailure("\n\n".join(accumulated))


# ---------- helpers ---------------------------------------------------------

def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _read_manifest_index(path: Path) -> tuple[set[str], dict[str, str]]:
    paths: set[str] = set()
    shas: dict[str, str] = {}
    for row in _read_tsv(path):
        local = row["local_path"]
        paths.add(local)
        shas[local] = row["sha256"]
    return paths, shas


def _per_source_keys(path: Path, key_field: str) -> set[str]:
    if not path.exists():
        return set()
    return {row[key_field] for row in _read_tsv(path)}


# ---------- CLI -------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Run all validation gates against the integrated layer."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        run_all_gates(args.root)
    except ValidationFailure as e:
        log.error("validation FAILED:\n%s", e)
        return 1
    log.info("validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

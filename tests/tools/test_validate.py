"""Tests for the validation harness (spec §7.4).

The harness enforces seven gates. Each test arranges a small in-tree
project layout under tmp_path that violates exactly one gate, then
checks that the corresponding gate flags the violation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m_standard.tools.validate import (
    ValidationFailure,
    gate_conflict_resolution,
    gate_coverage,
    gate_manifest_integrity,
    gate_provenance,
    gate_round_trip,
    gate_schema_validation,
    gate_tsv_json_consistency,
    run_all_gates,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# Build a minimal valid project tree under tmp_path so individual
# tests can perturb one piece and verify the relevant gate fails.
def _scaffold_valid_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / "sources" / "anno").mkdir(parents=True)
    (proj / "sources" / "ydb").mkdir(parents=True)
    (proj / "per-source" / "anno").mkdir(parents=True)
    (proj / "per-source" / "ydb").mkdir(parents=True)
    (proj / "integrated").mkdir(parents=True)
    # Re-use the project's real schemas/ rather than copy them.
    (proj / "schemas").symlink_to(REPO_ROOT / "schemas")

    # Minimal anno manifest + a tracked file with matching sha.
    anno_file = proj / "sources" / "anno" / "site_index.html"
    anno_file.parent.mkdir(parents=True, exist_ok=True)
    anno_file.write_text("<html></html>\n")
    import hashlib
    anno_sha = hashlib.sha256(anno_file.read_bytes()).hexdigest()
    (proj / "sources" / "anno" / "manifest.tsv").write_text(
        "source_url\tlocal_path\tsha256\tfetched_at\tformat\tcommit_sha\textraction_target\n"
        f"http://x/index.html\tsite_index.html\t{anno_sha}\t2026-04-25T00:00:00+00:00\thtml\t\t\n"
    )
    (proj / "sources" / "ydb" / "manifest.tsv").write_text(
        "source_url\tlocal_path\tsha256\tfetched_at\tformat\tcommit_sha\textraction_target\n"
    )

    # Per-source commands TSVs.
    (proj / "per-source" / "anno" / "commands.tsv").write_text(
        "canonical_name\tabbreviation\tsection_number\tformat\t"
        "standard_status_hint\tsource_section\tdescription\n"
        "BREAK\tB\t8.2.1\tB[REAK]\tansi\tanno_ref\tBreak.\n"
    )
    (proj / "per-source" / "ydb" / "commands.tsv").write_text(
        "canonical_name\tabbreviation\tformat\t"
        "standard_status_hint\tsource_section\tdescription\n"
        "BREAK\tB\tB[REAK][:tvexpr]\tansi\tydb_ref\tBreak.\n"
    )

    # Integrated layer (commands TSV + matching JSON + empty conflicts).
    integrated_tsv = proj / "integrated" / "commands.tsv"
    integrated_tsv.write_text(
        "canonical_name\tabbreviation\tformat\tstandard_status\t"
        "in_anno\tin_ydb\tanno_section\tydb_section\tconflict_id\tnotes\n"
        "BREAK\tB\tB[REAK][:tvexpr]\tansi\ttrue\ttrue\tanno_ref\tydb_ref\t\t\n"
    )
    (proj / "integrated" / "commands.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "concept": "commands",
                "entries": [
                    {
                        "canonical_name": "BREAK",
                        "abbreviation": "B",
                        "format": "B[REAK][:tvexpr]",
                        "standard_status": "ansi",
                        "in_anno": True,
                        "in_ydb": True,
                        "anno_section": "anno_ref",
                        "ydb_section": "ydb_ref",
                        "conflict_id": None,
                        "notes": "",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    (proj / "integrated" / "conflicts.tsv").write_text(
        "conflict_id\tconcept\tentry\tkind\tanno_says\tydb_says\t"
        "resolution\tresolution_basis\n"
    )
    return proj


# ----- Gate 1: manifest integrity -----

def test_gate_manifest_integrity_passes_on_valid_project(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    gate_manifest_integrity(proj)  # raises on failure


def test_gate_manifest_integrity_flags_unknown_file(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    # Add a file under sources/ that the manifest doesn't know about.
    (proj / "sources" / "anno" / "stray.html").write_text("<html></html>")
    with pytest.raises(ValidationFailure) as exc:
        gate_manifest_integrity(proj)
    assert "stray.html" in str(exc.value)


def test_gate_manifest_integrity_flags_sha_drift(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    # Mutate the file content so its sha no longer matches the manifest.
    (proj / "sources" / "anno" / "site_index.html").write_text("DRIFTED")
    with pytest.raises(ValidationFailure) as exc:
        gate_manifest_integrity(proj)
    assert "sha" in str(exc.value).lower() or "drift" in str(exc.value).lower()


# ----- Gate 2: provenance -----

def test_gate_provenance_flags_orphan_integrated_row(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    # Add a row to integrated/commands.tsv that is not in either per-source TSV.
    p = proj / "integrated" / "commands.tsv"
    p.write_text(
        p.read_text()
        + "ORPHAN\tO\tO[RPHAN]\tansi\tfalse\tfalse\t\t\t\t\n"
    )
    with pytest.raises(ValidationFailure) as exc:
        gate_provenance(proj)
    assert "ORPHAN" in str(exc.value)


# ----- Gate 3: conflict resolution -----

def test_gate_conflict_resolution_flags_pending_manual(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    p = proj / "integrated" / "conflicts.tsv"
    p.write_text(
        p.read_text()
        + "CONF-001\tcommands\tBREAK\tdefinition\tx\ty\tPENDING-MANUAL\tneed human\n"
    )
    with pytest.raises(ValidationFailure) as exc:
        gate_conflict_resolution(proj)
    assert "PENDING-MANUAL" in str(exc.value)


# ----- Gate 4: schema validation -----

def test_gate_schema_validation_flags_invalid_json(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    bad = json.loads((proj / "integrated" / "commands.json").read_text())
    bad["entries"][0]["standard_status"] = "not-a-real-status"
    (proj / "integrated" / "commands.json").write_text(
        json.dumps(bad, indent=2, sort_keys=True) + "\n"
    )
    with pytest.raises(ValidationFailure) as exc:
        gate_schema_validation(proj)
    assert "standard_status" in str(exc.value)


# ----- Gate 5: TSV/JSON consistency -----

def test_gate_tsv_json_consistency_flags_mismatched_count(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    p = proj / "integrated" / "commands.tsv"
    p.write_text(
        p.read_text()
        + "EXTRA\tE\tE[XTRA]\tansi\ttrue\ttrue\tx\ty\t\t\n"
    )
    with pytest.raises(ValidationFailure) as exc:
        gate_tsv_json_consistency(proj)
    assert "EXTRA" in str(exc.value) or "row count" in str(exc.value).lower()


# ----- Gate 6: round-trip -----

def test_gate_round_trip_passes_when_integrated_matches_reconciler(
    tmp_path: Path,
) -> None:
    """Reconciler is byte-deterministic: re-run produces identical output."""
    proj = _scaffold_valid_project(tmp_path)
    # The scaffold's integrated/commands.tsv was hand-written; rerun
    # the reconciler to materialise the canonical version, then this
    # gate should pass.
    from m_standard.tools.reconcile import reconcile_all
    reconcile_all(per_source=proj / "per-source", out_dir=proj / "integrated")
    # Recreate JSON because reconciler rewrote the TSV.
    from m_standard.tools.emit_json import emit_all
    emit_all(proj / "integrated", proj / "schemas")
    gate_round_trip(proj)


def test_gate_round_trip_flags_drift_from_reconciler(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    p = proj / "integrated" / "commands.tsv"
    # Tamper with the integrated TSV so it diverges from what the
    # reconciler would produce given the per-source inputs.
    p.write_text(p.read_text().replace("B[REAK][:tvexpr]", "TAMPERED"))
    with pytest.raises(ValidationFailure):
        gate_round_trip(proj)


# ----- Gate 7: coverage -----

def test_gate_coverage_flags_missing_per_source_entry(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    # Add a YDB-only entry in per-source but NOT in integrated.
    p = proj / "per-source" / "ydb" / "commands.tsv"
    p.write_text(
        p.read_text()
        + "ZBREAK\tZB\tZB[REAK]\tydb-extension\tydb_ref\tInsert temp BREAK.\n"
    )
    with pytest.raises(ValidationFailure) as exc:
        gate_coverage(proj)
    assert "ZBREAK" in str(exc.value)


# ----- Orchestrator -----

def test_run_all_gates_passes_on_valid_project(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    run_all_gates(proj)


def test_run_all_gates_returns_aggregate_failure_listing(tmp_path: Path) -> None:
    proj = _scaffold_valid_project(tmp_path)
    # Two independent failures: stray file + invalid JSON.
    (proj / "sources" / "anno" / "stray.html").write_text("<html></html>")
    bad = json.loads((proj / "integrated" / "commands.json").read_text())
    bad["entries"][0]["standard_status"] = "junk"
    (proj / "integrated" / "commands.json").write_text(
        json.dumps(bad, indent=2, sort_keys=True) + "\n"
    )
    with pytest.raises(ValidationFailure) as exc:
        run_all_gates(proj)
    msg = str(exc.value)
    assert "stray.html" in msg
    assert "standard_status" in msg

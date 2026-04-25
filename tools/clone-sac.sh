#!/usr/bin/env bash
# Clone the XINDEX routine source from WorldVistA/VistA-M into
# sources/sac/routines/. XINDEX is the operational SAC validator —
# the M routines that the VA actually runs against VistA M code to
# enforce the Standards and Conventions. The routines IN AGGREGATE
# define what SAC rules are checked; XINDX1.m's ERROR table is the
# canonical rule list (~65 rules).
#
# Per ADR-007, SAC is a *policy overlay* not a primary language
# source — but the source documents (XINDX*.m routines) live under
# sources/sac/ following the same offline-replica pattern as the
# three primary sources (anno, ydb, iris). The mappings/va-sac.tsv
# overlay is auto-derived from this clone via extract_sac.
#
# Configure:
#   UPSTREAM_BASE — raw URL prefix for the routines.
#   ROUTINES — the 18 XINDX*-prefixed Toolkit routines.
set -euo pipefail

OUT_DIR="${OUT_DIR:-sources/sac/routines}"
MANIFEST="${MANIFEST:-sources/sac/manifest.tsv}"
UPSTREAM_BASE="${UPSTREAM_BASE:-https://raw.githubusercontent.com/WorldVistA/VistA-M/master/Packages/Toolkit/Routines}"
UA="m-standard-sac-crawler/0.1"

mkdir -p "$OUT_DIR"

ROUTINES=(
  XINDEX.m
  XINDX1.m XINDX2.m XINDX3.m XINDX4.m XINDX5.m XINDX51.m XINDX52.m XINDX53.m
  XINDX6.m XINDX7.m XINDX8.m XINDX9.m XINDX10.m XINDX11.m XINDX12.m XINDX13.m
)

for r in "${ROUTINES[@]}"; do
  out="$OUT_DIR/$r"
  if [[ -f "$out" ]]; then
    echo "==> skip (cached): $r" >&2
    continue
  fi
  echo "==> fetching $r" >&2
  curl -fSsL --max-time 30 -A "$UA" \
    "$UPSTREAM_BASE/$r" -o "$out"
  sleep 0.25
done

# Regenerate manifest.tsv from the on-disk tree.
.venv/bin/python -m m_standard.tools.sac_manifest \
  --routines "$OUT_DIR" \
  --upstream "$UPSTREAM_BASE" \
  --out "$MANIFEST"

echo "==> Manifest written to $MANIFEST" >&2

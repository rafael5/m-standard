#!/usr/bin/env bash
# Clone the YottaDB documentation source repository into sources/ydb/repo/
# at a pinned commit SHA.
#
# Vendoring policy: the working tree is committed to m-standard's repo
# (GFDL-1.3, redistribution permitted) so a fresh clone of m-standard is
# self-contained; the inner .git/ is stripped after checkout to avoid
# turning the outer repo into a submodule wrapper. The pinned SHA is
# preserved per-row in sources/ydb/manifest.tsv, so reproducibility holds.
#
# Re-running this script:
#   - if sources/ydb/repo/.git exists, fetch + checkout the pin in place;
#   - otherwise (the typical post-clone state), clone into a temporary
#     directory at the pin, then mirror the tree into sources/ydb/repo/
#     and rebuild the manifest.
#
# Per spec §4.2, the cloned tree is the analysis foundation; the rendered
# site at https://docs.yottadb.com/ is referenced only for human
# verification.
#
# Configure:
#   UPSTREAM   — git URL of the YottaDB documentation source repo.
#   PIN_COMMIT — commit SHA to check out. Empty means "use the tip of
#                UPSTREAM_BRANCH at first clone, then record what we
#                got into manifest.tsv". After Phase A0, this MUST be
#                set to a specific SHA so source pin-stability holds.
#   UPSTREAM_BRANCH — branch to track when PIN_COMMIT is empty.
#
# Override either via environment variable, e.g.:
#   UPSTREAM=https://gitlab.com/YottaDB/DB/YDBDoc.git \
#   PIN_COMMIT=abc123 \
#   bash tools/clone-ydb.sh
set -euo pipefail

REPO_DIR="${REPO_DIR:-sources/ydb/repo}"
MANIFEST="${MANIFEST:-sources/ydb/manifest.tsv}"
UPSTREAM="${UPSTREAM:-https://gitlab.com/YottaDB/DB/YDBDoc.git}"
PIN_COMMIT="${PIN_COMMIT:-}"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-master}"

mkdir -p "$(dirname "$REPO_DIR")"

if [[ -d "$REPO_DIR/.git" ]]; then
  echo "==> Updating existing clone at $REPO_DIR" >&2
  git -C "$REPO_DIR" fetch --all --tags --prune
  if [[ -n "$PIN_COMMIT" ]]; then
    echo "==> Checking out pinned commit $PIN_COMMIT" >&2
    git -C "$REPO_DIR" checkout --detach "$PIN_COMMIT"
  else
    git -C "$REPO_DIR" checkout "$UPSTREAM_BRANCH"
    git -C "$REPO_DIR" pull --ff-only origin "$UPSTREAM_BRANCH"
  fi
  ACTUAL_SHA="$(git -C "$REPO_DIR" rev-parse HEAD)"
else
  # No embedded .git/ (the post-vendor state). Clone fresh into a temp
  # directory at the pinned commit, then mirror the working tree onto
  # REPO_DIR. Strip .git/ from the result so we stay vendored.
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  echo "==> Cloning $UPSTREAM -> $TMP_DIR" >&2
  git clone "$UPSTREAM" "$TMP_DIR/clone"
  if [[ -n "$PIN_COMMIT" ]]; then
    echo "==> Checking out pinned commit $PIN_COMMIT" >&2
    git -C "$TMP_DIR/clone" checkout --detach "$PIN_COMMIT"
  else
    git -C "$TMP_DIR/clone" checkout "$UPSTREAM_BRANCH"
  fi
  ACTUAL_SHA="$(git -C "$TMP_DIR/clone" rev-parse HEAD)"
  echo "==> Mirroring working tree into $REPO_DIR (stripping .git/)" >&2
  rm -rf "$REPO_DIR"
  mkdir -p "$(dirname "$REPO_DIR")"
  rsync -a --delete --exclude='.git' "$TMP_DIR/clone/" "$REPO_DIR/"
fi

echo "==> Repository at $ACTUAL_SHA" >&2

# Regenerate the manifest from the on-disk tree so every tracked file
# has a sha256 + commit_sha entry.
.venv/bin/python -m m_standard.tools.ydb_manifest \
  --repo "$REPO_DIR" \
  --upstream "$UPSTREAM" \
  --commit "$ACTUAL_SHA" \
  --out "$MANIFEST"

echo "==> Manifest written to $MANIFEST" >&2

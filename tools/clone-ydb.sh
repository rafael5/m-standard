#!/usr/bin/env bash
# Clone the YottaDB documentation source repository into sources/ydb/repo/
# at a pinned commit SHA. Idempotent: re-running fast-forwards (or fetches)
# rather than re-cloning. The cloned tree retains its .git/ so the exact
# commit is reproducible and updates are a `git pull`.
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
#   UPSTREAM=https://gitlab.com/YottaDB/DOC/YDBDoc.git \
#   PIN_COMMIT=abc123 \
#   bash tools/clone-ydb.sh
set -euo pipefail

REPO_DIR="${REPO_DIR:-sources/ydb/repo}"
MANIFEST="${MANIFEST:-sources/ydb/manifest.tsv}"
UPSTREAM="${UPSTREAM:-https://gitlab.com/YottaDB/DOC/YDBDoc.git}"
PIN_COMMIT="${PIN_COMMIT:-}"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-master}"

mkdir -p "$(dirname "$REPO_DIR")"

if [[ -d "$REPO_DIR/.git" ]]; then
  echo "==> Updating existing clone at $REPO_DIR" >&2
  git -C "$REPO_DIR" fetch --all --tags --prune
else
  echo "==> Cloning $UPSTREAM -> $REPO_DIR" >&2
  git clone "$UPSTREAM" "$REPO_DIR"
fi

if [[ -n "$PIN_COMMIT" ]]; then
  echo "==> Checking out pinned commit $PIN_COMMIT" >&2
  git -C "$REPO_DIR" checkout --detach "$PIN_COMMIT"
else
  echo "==> No PIN_COMMIT set; using tip of $UPSTREAM_BRANCH" >&2
  git -C "$REPO_DIR" checkout "$UPSTREAM_BRANCH"
  git -C "$REPO_DIR" pull --ff-only origin "$UPSTREAM_BRANCH"
fi

ACTUAL_SHA="$(git -C "$REPO_DIR" rev-parse HEAD)"
echo "==> Repository at $ACTUAL_SHA" >&2

# Regenerate the manifest from the on-disk tree so every tracked file
# has a sha256 + commit_sha entry.
.venv/bin/python -m m_standard.tools.ydb_manifest \
  --repo "$REPO_DIR" \
  --upstream "$UPSTREAM" \
  --commit "$ACTUAL_SHA" \
  --out "$MANIFEST"

echo "==> Manifest written to $MANIFEST" >&2

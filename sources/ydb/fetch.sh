#!/usr/bin/env bash
# Re-acquire the YottaDB documentation clone at the pinned commit.
# Used when sources/ydb/repo/ is not committed (e.g. pending Phase A0
# redistribution check). The pipeline always reads from the local
# clone, never from the network at run time.
set -euo pipefail
cd "$(dirname "$0")/../.."
bash tools/clone-ydb.sh "$@"

#!/usr/bin/env bash
# Re-acquire the InterSystems IRIS docs subset by re-running the
# bounded crawler. Used when sources/iris/site/ is not committed
# (the v0.2 default — InterSystems' docs licence does not state
# explicit redistribution permission). The pipeline always reads
# from the local mirror, never the network at run time.
set -euo pipefail
cd "$(dirname "$0")/../.."
.venv/bin/python -m m_standard.tools.crawl_iris "$@"

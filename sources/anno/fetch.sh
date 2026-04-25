#!/usr/bin/env bash
# Re-acquire the AnnoStd offline mirror by re-running the crawler.
# Used when the bulk content of sources/anno/site/ is not committed
# (e.g. pending Phase A0 redistribution check). The pipeline always
# reads from the local mirror, never from the network at run time.
set -euo pipefail
cd "$(dirname "$0")/../.."
.venv/bin/python -m m_standard.tools.crawl_anno "$@"

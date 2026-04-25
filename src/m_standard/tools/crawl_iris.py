"""Bounded crawler for the InterSystems IRIS documentation subset.

Per spec §4.3, IRIS docs are vast — thousands of pages covering SQL,
productions, %CSP, deployment, etc. — most of which are out of scope
for an M-language standard. So unlike ``crawl_anno`` (which discovers
links recursively from a single base URL), ``crawl_iris`` is
*seed-bounded*: callers pass a list of KEYs, and the crawler fetches
the corresponding pages without following internal links.

Default seed set covers the M-language-relevant subset:
- ``RERR_system`` — System Error Messages (the M-language ``<UNDEFINED>``
  / ``<DIVIDE>`` style errors)
- ``RERR_gen`` — General Error Messages (numeric %Status codes)
- ``RCOS`` — ObjectScript Reference (commands, functions, ISVs)
- ``GCOS_trycatch`` — TRY-CATCH error processing
- ``RCOS_COMMANDS``, ``RCOS_FUNCTIONS``, ``RCOS_VARIABLES``,
  ``RCOS_ZCOMMANDS`` — concept-family TOCs (each one links to per-entry
  sub-pages like ``RCOS_cbreak``, ``RCOS_fascii``, ``RCOS_vdevice``)

Optional ``--follow-prefix`` discovers sub-page KEYs from already-fetched
index pages and queues them in a second pass. This lets one command
fetch the full M-language reference subset (~233 pages) without
hardcoding hundreds of seeds.

Idempotent on re-run; preserves page bodies byte-for-byte; writes a
``manifest.tsv`` with sha256 per file.
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from m_standard.tools.manifest import Manifest, ManifestEntry, sha256_of

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = (
    "https://docs.intersystems.com/irislatest/csp/docbook/Doc.View.cls"
)
DEFAULT_OUTPUT_DIR = Path("sources/iris/site")
DEFAULT_MANIFEST_PATH = Path("sources/iris/manifest.tsv")
DEFAULT_SEED_KEYS: tuple[str, ...] = (
    "RERR_system",       # M-language system errors (<UNDEFINED>, <DIVIDE>, ...)
    "RERR_gen",          # %Status numeric codes
    "RCOS",              # ObjectScript Reference top-level TOC
    "RCOS_COMMANDS",     # Command index (links to per-cmd pages)
    "RCOS_FUNCTIONS",    # Function index (links to per-fn pages)
    "RCOS_VARIABLES",    # Special variable index
    "RCOS_ZCOMMANDS",    # Z-command index
    "RCOS_OPERATORS",    # Operator reference
    "GCOS_trycatch",     # TRY-CATCH error processing
)

# Default prefix to follow when discovering sub-page KEYs. ``RCOS_c``
# matches per-command pages (RCOS_cbreak, RCOS_cclose, ...);
# ``RCOS_f`` matches per-function pages; ``RCOS_v`` matches per-svn
# pages; ``RCOS_cz`` matches Z-command pages. The unified prefix
# ``RCOS_`` covers all of these plus their TOC variants.
DEFAULT_FOLLOW_PREFIX = "RCOS_"


@dataclass(frozen=True)
class Fetched:
    url: str
    content: bytes
    content_type: str


class Fetcher(Protocol):
    def get(self, url: str) -> Fetched: ...


@dataclass
class RequestsFetcher:
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "m-standard-iris-crawler/0.1"
    )
    timeout: float = 30.0
    delay_seconds: float = 0.5  # IRIS docs are public; be polite.

    def get(self, url: str) -> Fetched:
        import requests

        time.sleep(self.delay_seconds)
        resp = requests.get(
            url, headers={"User-Agent": self.user_agent}, timeout=self.timeout
        )
        resp.raise_for_status()
        return Fetched(
            url=resp.url,
            content=resp.content,
            content_type=resp.headers.get("Content-Type", ""),
        )


def crawl(
    base_url: str,
    seed_keys: list[str] | tuple[str, ...],
    output_dir: Path,
    manifest_path: Path,
    fetcher: Fetcher,
    *,
    follow_prefix: str | None = None,
) -> Manifest:
    """Fetch each ``KEY`` in ``seed_keys`` from ``base_url``.

    Saves each page to ``output_dir/<KEY>.html`` and records it in the
    manifest. Files already on disk are not refetched. Returns the
    resulting Manifest.

    If ``follow_prefix`` is set, after fetching the seeds the crawler
    walks each fetched page for ``href=…?KEY=<follow_prefix>…`` links
    and queues them too (one extra pass). This lets a small seed list
    bootstrap a wider crawl without true link-following.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest()

    queue: list[str] = list(seed_keys)
    seen: set[str] = set()
    for key in queue:
        if key in seen:
            continue
        seen.add(key)
        _fetch_one(
            base_url, key, output_dir, manifest_path, fetcher, manifest
        )

    if follow_prefix:
        discovered: list[str] = []
        for key in list(seen):
            page = output_dir / f"{key}.html"
            if not page.exists():
                continue
            for sub in _discover_subkeys(page, follow_prefix):
                if sub not in seen:
                    discovered.append(sub)
                    seen.add(sub)
        for key in discovered:
            _fetch_one(
                base_url, key, output_dir, manifest_path, fetcher, manifest
            )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.write(manifest_path)
    log.info("crawl done: %d files", len(manifest.entries))
    return manifest


def _fetch_one(
    base_url: str,
    key: str,
    output_dir: Path,
    manifest_path: Path,
    fetcher: Fetcher,
    manifest: Manifest,
) -> None:
    url = f"{base_url}?KEY={key}"
    local_path = output_dir / f"{key}.html"
    manifest_local = (
        output_dir / f"{key}.html"
    ).resolve().relative_to(manifest_path.resolve().parent)

    if local_path.exists():
        log.debug("skip (cached): %s", url)
    else:
        try:
            fetched = fetcher.get(url)
        except Exception as exc:  # noqa: BLE001
            log.warning("fetch failed: %s (%s)", url, exc)
            return
        local_path.write_bytes(fetched.content)
        log.info("saved: %s -> %s", url, key)

    manifest.add(
        ManifestEntry(
            source_url=url,
            local_path=manifest_local.as_posix(),
            sha256=sha256_of(local_path),
            fetched_at=datetime.now(tz=timezone.utc),
            format="html",
        )
    )


_KEY_RE = re.compile(r"KEY=([A-Z][A-Za-z_0-9]+)")


def _discover_subkeys(page_path: Path, prefix: str) -> list[str]:
    """Extract sub-page KEYs matching ``prefix`` from a page's article body.

    Restricting to ``<article>`` keeps the discovery scoped to actual
    document content rather than the persistent left-nav TOC, which
    links out to the entire IRIS docs corpus.
    """
    import warnings as _w
    _w.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(page_path.read_bytes(), "lxml")
    container = soup.find("article") or soup
    out: list[str] = []
    seen: set[str] = set()
    for a in container.find_all("a", href=True):
        match = _KEY_RE.search(str(a["href"]))
        if not match:
            continue
        key = match.group(1)
        if key.startswith(prefix) and key not in seen:
            seen.add(key)
            out.append(key)
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Bounded crawler for the InterSystems IRIS docs subset."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--seeds",
        nargs="+",
        default=list(DEFAULT_SEED_KEYS),
        help="DocBook KEYs to fetch (default: M-language relevant subset).",
    )
    parser.add_argument(
        "--follow-prefix",
        default=DEFAULT_FOLLOW_PREFIX,
        help=(
            "After fetching seeds, walk fetched pages for sub-page KEYs "
            "starting with this prefix and queue them. Set to empty "
            "string to disable."
        ),
    )
    args = parser.parse_args(argv)

    crawl(
        base_url=args.base_url,
        seed_keys=args.seeds,
        output_dir=args.out,
        manifest_path=args.manifest,
        fetcher=RequestsFetcher(),
        follow_prefix=args.follow_prefix or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

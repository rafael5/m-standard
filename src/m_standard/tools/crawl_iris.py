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

Idempotent on re-run; preserves page bodies byte-for-byte; writes a
``manifest.tsv`` with sha256 per file.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from m_standard.tools.manifest import Manifest, ManifestEntry, sha256_of

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = (
    "https://docs.intersystems.com/irislatest/csp/docbook/Doc.View.cls"
)
DEFAULT_OUTPUT_DIR = Path("sources/iris/site")
DEFAULT_MANIFEST_PATH = Path("sources/iris/manifest.tsv")
DEFAULT_SEED_KEYS: tuple[str, ...] = (
    "RERR_system",   # M-language system errors (<UNDEFINED>, <DIVIDE>, ...)
    "RERR_gen",      # %Status numeric codes
    "RCOS",          # ObjectScript Reference (commands, functions, ISVs)
    "GCOS_trycatch", # TRY-CATCH error processing
)


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
) -> Manifest:
    """Fetch each ``KEY`` in ``seed_keys`` from ``base_url``.

    Saves each page to ``output_dir/<KEY>.html`` and records it in the
    manifest. Files already on disk with matching contents are not
    refetched. Returns the resulting Manifest.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest()

    for key in seed_keys:
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
                continue
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

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.write(manifest_path)
    log.info("crawl done: %d files", len(manifest.entries))
    return manifest


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
    args = parser.parse_args(argv)

    crawl(
        base_url=args.base_url,
        seed_keys=args.seeds,
        output_dir=args.out,
        manifest_path=args.manifest,
        fetcher=RequestsFetcher(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

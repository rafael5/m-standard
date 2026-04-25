"""Crawl AnnoStd into a local offline replica.

Usage:
    python -m m_standard.tools.crawl_anno
    python -m m_standard.tools.crawl_anno --base-url <url> --out <dir>

Behaviour (per spec §4.1):
- Walks the AnnoStd HTML tree breadth-first from a single base URL,
  staying strictly within the same host AND within the base URL's path
  prefix. Off-host and off-prefix links are recorded but not followed.
- Saves every fetched resource under ``output_dir`` at a path that
  mirrors its URL path, so the mirror opens directly in a browser
  (``file://.../output_dir/index.html``) and via ``make serve-anno``.
- Page bodies are preserved byte-for-byte. The crawler does *not*
  rewrite link targets in the saved HTML — relative links resolve
  against the saved file's location, which is enough for browseable
  offline mirrors that preserve the upstream directory shape.
- Idempotent: a file already on disk with a matching sha256 is left
  alone and not refetched.
- Writes a ``manifest.tsv`` capturing every saved file (URL, local
  path, sha256, fetched_at, format).
"""

from __future__ import annotations

import argparse
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from m_standard.tools.manifest import Manifest, ManifestEntry, sha256_of

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://71.174.62.16/Demo/AnnoStd"
DEFAULT_OUTPUT_DIR = Path("sources/anno/site")
DEFAULT_MANIFEST_PATH = Path("sources/anno/manifest.tsv")

_HTML_TYPES = ("text/html", "application/xhtml+xml")


@dataclass(frozen=True)
class Fetched:
    url: str
    content: bytes
    content_type: str


class Fetcher(Protocol):
    def get(self, url: str) -> Fetched: ...


@dataclass
class RequestsFetcher:
    user_agent: str = "m-standard-crawler/0.1 (+offline replica)"
    timeout: float = 30.0
    delay_seconds: float = 0.25

    def get(self, url: str) -> Fetched:
        import requests  # local import keeps tests free of network deps

        time.sleep(self.delay_seconds)
        resp = requests.get(
            url, headers={"User-Agent": self.user_agent}, timeout=self.timeout
        )
        resp.raise_for_status()
        return Fetched(
            url=resp.url, content=resp.content, content_type=resp.headers.get(
                "Content-Type", ""
            )
        )


def crawl(
    base_url: str,
    output_dir: Path,
    manifest_path: Path,
    fetcher: Fetcher,
) -> Manifest:
    """Mirror the site rooted at ``base_url`` under ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)

    base = base_url.rstrip("/") + "/"
    base_parsed = urlparse(base)
    seen: set[str] = set()
    queue: deque[str] = deque([base])
    manifest = Manifest()

    while queue:
        raw = queue.popleft()
        raw, _ = urldefrag(raw)
        if not _in_scope(raw, base_parsed):
            continue
        url = _canonicalize(raw, base_parsed)
        if url in seen:
            continue
        seen.add(url)

        rel = _site_rel_for(url, base_parsed)
        local_path = output_dir / rel
        manifest_local = (
            output_dir / rel
        ).resolve().relative_to(manifest_path.resolve().parent)

        # Idempotency: if the file already exists, skip the network fetch
        # and reuse the on-disk content for link discovery.
        if local_path.exists():
            content = local_path.read_bytes()
            content_type = _guess_content_type(rel)
            log.debug("skip (cached): %s", url)
        else:
            try:
                fetched = fetcher.get(url)
            except Exception as exc:  # noqa: BLE001 — log and move on
                log.warning("fetch failed: %s (%s)", url, exc)
                continue
            content = fetched.content
            content_type = fetched.content_type
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(content)
            log.info("saved: %s -> %s", url, rel)

        fmt = "html" if _is_html(content_type, rel) else "asset"
        manifest.add(
            ManifestEntry(
                source_url=url,
                local_path=manifest_local.as_posix(),
                sha256=sha256_of(local_path),
                fetched_at=datetime.now(tz=timezone.utc),
                format=fmt,
            )
        )

        if fmt == "html":
            for link in _extract_links(content, url):
                if link not in seen and _in_scope(link, base_parsed):
                    queue.append(link)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.write(manifest_path)
    log.info("crawl done: %d files", len(manifest.entries))
    return manifest


def _canonicalize(url: str, base_parsed) -> str:
    """Map directory URLs to their ``index.html`` so seen-set dedupes."""
    p = urlparse(url)
    if p.path.endswith("/"):
        return url + "index.html"
    base_dir = base_parsed.path if base_parsed.path.endswith("/") else (
        base_parsed.path + "/"
    )
    if p.path + "/" == base_dir:
        return url + "/index.html"
    return url


def _in_scope(url: str, base_parsed) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False
    if p.netloc != base_parsed.netloc:
        return False
    base_dir = base_parsed.path if base_parsed.path.endswith("/") else (
        base_parsed.path + "/"
    )
    return p.path.startswith(base_dir)


def _site_rel_for(url: str, base_parsed) -> Path:
    """Path of ``url`` *within* the mirror root (e.g. ``ch01.html``).

    The full on-disk path is ``output_dir / rel``. The manifest records
    each file's location relative to the manifest's parent, which is
    typically one level above the mirror root.
    """
    base_dir = base_parsed.path if base_parsed.path.endswith("/") else (
        base_parsed.path + "/"
    )
    rel = urlparse(url).path[len(base_dir):]
    if rel == "" or rel.endswith("/"):
        rel = rel + "index.html"
    return Path(rel)


def _is_html(content_type: str, local_rel: Path) -> bool:
    ct = content_type.split(";", 1)[0].strip().lower()
    if ct in _HTML_TYPES:
        return True
    return local_rel.suffix.lower() in (".html", ".htm")


def _guess_content_type(local_rel: Path) -> str:
    suffix = local_rel.suffix.lower()
    if suffix in (".html", ".htm"):
        return "text/html"
    if suffix == ".css":
        return "text/css"
    if suffix in (".js",):
        return "application/javascript"
    return "application/octet-stream"


def _extract_links(content: bytes, page_url: str) -> list[str]:
    soup = BeautifulSoup(content, "lxml")
    out: list[str] = []
    selectors = (
        ("a", "href"),
        ("link", "href"),
        ("img", "src"),
        ("script", "src"),
    )
    for tag, attr in selectors:
        for el in soup.find_all(tag):
            raw = el.get(attr)
            if not raw:
                continue
            absolute = urljoin(page_url, str(raw))
            absolute, _ = urldefrag(absolute)
            out.append(absolute)
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Crawl AnnoStd into a local offline mirror."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Directory to write the mirror under (parent of site/).",
    )
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST_PATH,
    )
    args = parser.parse_args(argv)

    crawl(
        base_url=args.base_url,
        output_dir=args.out,
        manifest_path=args.manifest,
        fetcher=RequestsFetcher(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

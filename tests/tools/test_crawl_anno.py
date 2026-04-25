"""Crawler tests use a FakeFetcher — no network in the test suite.

The FakeFetcher serves a small in-memory pretend AnnoStd site with:
- An index page that links to two child pages and a CSS asset
- One child that links back to the index and to a sibling
- A page outside the prefix (to verify scope confinement)
- A page outside the host (to verify we don't follow off-site links)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from m_standard.tools.crawl_anno import (
    Fetched,
    Fetcher,
    crawl,
)

BASE = "http://anno.example/Demo/AnnoStd"

INDEX_HTML = b"""<!doctype html>
<html><head><link rel="stylesheet" href="style.css"></head>
<body>
<a href="ch01.html">Chapter 1</a>
<a href="sub/ch02.html">Chapter 2</a>
<a href="../OtherDemo/x.html">Off-prefix</a>
<a href="http://elsewhere.example/y.html">Off-host</a>
</body></html>
"""

CH01_HTML = b"""<!doctype html>
<html><body>
<a href="index.html">home</a>
<a href="sub/ch02.html">next</a>
</body></html>
"""

CH02_HTML = b"""<!doctype html>
<html><body><a href="../ch01.html">prev</a></body></html>
"""

CSS = b"body { color: black; }"


@dataclass
class FakeFetcher(Fetcher):
    log: list[str]

    def get(self, url: str) -> Fetched:
        self.log.append(url)
        if url == f"{BASE}/" or url == f"{BASE}/index.html":
            return Fetched(
                url=f"{BASE}/index.html", content=INDEX_HTML, content_type="text/html"
            )
        if url == f"{BASE}/ch01.html":
            return Fetched(
                url=url, content=CH01_HTML, content_type="text/html; charset=utf-8"
            )
        if url == f"{BASE}/sub/ch02.html":
            return Fetched(url=url, content=CH02_HTML, content_type="text/html")
        if url == f"{BASE}/style.css":
            return Fetched(url=url, content=CSS, content_type="text/css")
        raise AssertionError(f"FakeFetcher reached unscoped URL: {url}")


def _crawl(tmp_path: Path) -> tuple[FakeFetcher, Path]:
    out = tmp_path / "site"
    fetcher = FakeFetcher(log=[])
    crawl(base_url=BASE, output_dir=out, manifest_path=tmp_path / "manifest.tsv",
          fetcher=fetcher)
    return fetcher, out


def test_crawl_writes_pages_under_output_dir(tmp_path: Path) -> None:
    _, out = _crawl(tmp_path)
    assert (out / "index.html").exists()
    assert (out / "ch01.html").exists()
    assert (out / "sub" / "ch02.html").exists()
    assert (out / "style.css").exists()


def test_crawl_does_not_follow_off_prefix_or_off_host(tmp_path: Path) -> None:
    fetcher, _ = _crawl(tmp_path)
    for url in fetcher.log:
        assert url.startswith(BASE), f"crawler escaped scope: {url}"


def test_crawl_writes_manifest_with_one_row_per_file(tmp_path: Path) -> None:
    from m_standard.tools.manifest import Manifest

    _crawl(tmp_path)
    m = Manifest.read(tmp_path / "manifest.tsv")
    paths = sorted(e.local_path for e in m.entries)
    assert paths == [
        "site/ch01.html",
        "site/index.html",
        "site/style.css",
        "site/sub/ch02.html",
    ]
    formats = {e.local_path: e.format for e in m.entries}
    assert formats["site/index.html"] == "html"
    assert formats["site/style.css"] == "asset"


def test_crawl_preserves_page_bytes(tmp_path: Path) -> None:
    """Page bodies are preserved byte-for-byte (per spec §4.1)."""
    _, out = _crawl(tmp_path)
    assert (out / "ch01.html").read_bytes() == CH01_HTML
    assert (out / "sub" / "ch02.html").read_bytes() == CH02_HTML


def test_crawl_is_idempotent(tmp_path: Path) -> None:
    """Re-running over an existing mirror does not refetch unchanged files."""
    fetcher, _ = _crawl(tmp_path)
    first_pass = list(fetcher.log)
    fetcher.log.clear()
    crawl(
        base_url=BASE,
        output_dir=tmp_path / "site",
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    # Second pass may still touch the index to discover links, but it
    # must be strictly smaller than the first pass — no pointless refetch
    # of every asset and child page.
    assert len(fetcher.log) < len(first_pass)

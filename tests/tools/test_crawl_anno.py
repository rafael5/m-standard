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


ANNO_BASE = "http://anno.example/Demo/AnnoStd"
ANNO_INDEX = b"""<!doctype html>
<html><body>
<span onclick="GetText('ShowPage', 'a100001', '', '');">Annotations</span>
<span onclick="GetText('ShowPage', 'a100002', '', '');">Title Page</span>
<span onclick="GetText('ShowLiterature', '', '', '');">Literature</span>
</body></html>
"""

ANNO_PAGE_001 = b"""<table><tr><td>
<span onclick="GetText('ShowPage', 'a100002', '', '');">Next</span>
</td></tr></table>
<h1>Annotations</h1>
"""

ANNO_PAGE_002 = b"""<table><tr><td>
<span onclick="GetText('ShowPage', 'a100001', '', '');">Prev</span>
</td></tr></table>
<h1>Title Page</h1>
"""

ANNO_LITERATURE = b"<h1>Literature</h1>"


@dataclass
class AnnoFetcher(Fetcher):
    log: list[str]

    def get(self, url: str) -> Fetched:
        self.log.append(url)
        if url in (f"{ANNO_BASE}/", f"{ANNO_BASE}/index.html"):
            return Fetched(
                url=f"{ANNO_BASE}/index.html",
                content=ANNO_INDEX,
                content_type="text/html",
            )
        if url.startswith(f"{ANNO_BASE}/?"):
            if "Page=a100001" in url:
                return Fetched(url=url, content=ANNO_PAGE_001, content_type="text/html")
            if "Page=a100002" in url:
                return Fetched(url=url, content=ANNO_PAGE_002, content_type="text/html")
            if "Action=ShowLiterature" in url:
                return Fetched(
                    url=url, content=ANNO_LITERATURE, content_type="text/html"
                )
        raise AssertionError(f"AnnoFetcher reached unexpected URL: {url}")


def test_crawl_follows_gettext_page_calls(tmp_path: Path) -> None:
    out = tmp_path / "site"
    fetcher = AnnoFetcher(log=[])
    crawl(
        base_url=ANNO_BASE,
        output_dir=out,
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    # Each ShowPage page lands as pages/<id>.html
    assert (out / "pages" / "a100001.html").read_bytes() == ANNO_PAGE_001
    assert (out / "pages" / "a100002.html").read_bytes() == ANNO_PAGE_002
    # ShowLiterature lands as a separate path so it doesn't collide with pages/
    assert (out / "literature.html").read_bytes() == ANNO_LITERATURE


def test_crawl_dedupes_dynamic_pages_across_back_references(tmp_path: Path) -> None:
    out = tmp_path / "site"
    fetcher = AnnoFetcher(log=[])
    crawl(
        base_url=ANNO_BASE,
        output_dir=out,
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    # Page 002 links back to page 001; we must fetch each page exactly once.
    fetched_pages = [u for u in fetcher.log if "Page=a100001" in u]
    assert len(fetched_pages) == 1


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

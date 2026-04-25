"""Tests for the bounded IRIS docs crawler.

Unlike crawl_anno (which discovers links recursively from a single
base URL), crawl_iris is *seed-bounded*: callers pass a list of
KEYs, and the crawler fetches the corresponding pages without
following internal links. This is because IRIS docs are vast and
most of it (SQL, productions, %CSP, deployment) is out of scope for
an M-language standard.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from m_standard.tools.crawl_iris import (
    Fetched,
    Fetcher,
    crawl,
)

BASE = "https://iris.example/csp/docbook/Doc.View.cls"

PAGE_RERR_SYSTEM = b"<html><body><h1>System Error Messages</h1></body></html>"
PAGE_RCOS = b"<html><body><h1>ObjectScript Reference</h1></body></html>"


@dataclass
class FakeFetcher(Fetcher):
    log: list[str]

    def get(self, url: str) -> Fetched:
        self.log.append(url)
        if "RERR_system" in url:
            return Fetched(url=url, content=PAGE_RERR_SYSTEM, content_type="text/html")
        if "RCOS" in url:
            return Fetched(url=url, content=PAGE_RCOS, content_type="text/html")
        raise AssertionError(f"FakeFetcher reached unexpected URL: {url}")


def test_crawl_fetches_each_seed_key(tmp_path: Path) -> None:
    out = tmp_path / "site"
    fetcher = FakeFetcher(log=[])
    crawl(
        base_url=BASE,
        seed_keys=["RERR_system", "RCOS"],
        output_dir=out,
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    assert (out / "RERR_system.html").read_bytes() == PAGE_RERR_SYSTEM
    assert (out / "RCOS.html").read_bytes() == PAGE_RCOS


def test_crawl_writes_one_manifest_row_per_seed(tmp_path: Path) -> None:
    from m_standard.tools.manifest import Manifest

    fetcher = FakeFetcher(log=[])
    crawl(
        base_url=BASE,
        seed_keys=["RERR_system", "RCOS"],
        output_dir=tmp_path / "site",
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    m = Manifest.read(tmp_path / "manifest.tsv")
    paths = sorted(e.local_path for e in m.entries)
    assert paths == ["site/RCOS.html", "site/RERR_system.html"]
    formats = {e.local_path: e.format for e in m.entries}
    assert formats["site/RCOS.html"] == "html"


def test_crawl_does_not_follow_internal_links(tmp_path: Path) -> None:
    """The crawler is seed-bounded: only the configured KEYs are fetched."""
    fetcher = FakeFetcher(log=[])
    crawl(
        base_url=BASE,
        seed_keys=["RERR_system"],
        output_dir=tmp_path / "site",
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    # Only one URL was fetched, even though the page might link to
    # RCOS or other KEYs.
    assert len(fetcher.log) == 1


def test_crawl_is_idempotent(tmp_path: Path) -> None:
    fetcher = FakeFetcher(log=[])
    crawl(
        base_url=BASE,
        seed_keys=["RERR_system", "RCOS"],
        output_dir=tmp_path / "site",
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    first = list(fetcher.log)
    fetcher.log.clear()
    crawl(
        base_url=BASE,
        seed_keys=["RERR_system", "RCOS"],
        output_dir=tmp_path / "site",
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    # Second pass reuses the cached files; no fetcher.get() called.
    assert len(fetcher.log) < len(first)


def test_crawl_url_includes_key_query(tmp_path: Path) -> None:
    fetcher = FakeFetcher(log=[])
    crawl(
        base_url=BASE,
        seed_keys=["RCOS"],
        output_dir=tmp_path / "site",
        manifest_path=tmp_path / "manifest.tsv",
        fetcher=fetcher,
    )
    assert any("KEY=RCOS" in u for u in fetcher.log)

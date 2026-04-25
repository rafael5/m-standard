from datetime import datetime, timezone
from pathlib import Path

from m_standard.tools.manifest import (
    Manifest,
    ManifestEntry,
    sha256_of,
)


def test_sha256_of_known_content(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_bytes(b"hello")
    # sha256("hello")
    assert (
        sha256_of(f)
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_manifest_round_trip(tmp_path: Path) -> None:
    m = Manifest()
    m.add(
        ManifestEntry(
            source_url="http://example.com/a.html",
            local_path="site/a.html",
            sha256="aa",
            fetched_at=datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc),
            format="html",
            commit_sha="",
            extraction_target="",
        )
    )
    m.add(
        ManifestEntry(
            source_url="http://example.com/b.html",
            local_path="site/b.html",
            sha256="bb",
            fetched_at=datetime(2026, 4, 25, 12, 0, 1, tzinfo=timezone.utc),
            format="html",
            commit_sha="",
            extraction_target="",
        )
    )

    out = tmp_path / "manifest.tsv"
    m.write(out)

    loaded = Manifest.read(out)
    assert len(loaded.entries) == 2
    assert loaded.entries[0].source_url == "http://example.com/a.html"
    assert loaded.entries[1].sha256 == "bb"
    assert loaded.entries[0].fetched_at.tzinfo is not None


def test_manifest_header_line(tmp_path: Path) -> None:
    out = tmp_path / "manifest.tsv"
    Manifest().write(out)
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header.split("\t") == [
        "source_url",
        "local_path",
        "sha256",
        "fetched_at",
        "format",
        "commit_sha",
        "extraction_target",
    ]


def test_manifest_writes_sorted_by_local_path(tmp_path: Path) -> None:
    m = Manifest()
    for url, lp in [
        ("u3", "site/c.html"),
        ("u1", "site/a.html"),
        ("u2", "site/b.html"),
    ]:
        m.add(
            ManifestEntry(
                source_url=url,
                local_path=lp,
                sha256="x",
                fetched_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
                format="html",
                commit_sha="",
                extraction_target="",
            )
        )
    out = tmp_path / "manifest.tsv"
    m.write(out)
    rows = out.read_text(encoding="utf-8").splitlines()[1:]
    assert [r.split("\t")[1] for r in rows] == [
        "site/a.html",
        "site/b.html",
        "site/c.html",
    ]

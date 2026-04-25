"""Manifest TSV: per-source registry of every file in a local replica.

Schema is fixed (see spec §6.6). One row per file under `sources/<src>/`,
written sorted by `local_path` so diffs of the manifest reflect actual
content changes rather than fetch-order noise.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

COLUMNS: tuple[str, ...] = (
    "source_url",
    "local_path",
    "sha256",
    "fetched_at",
    "format",
    "commit_sha",
    "extraction_target",
)


@dataclass(frozen=True)
class ManifestEntry:
    source_url: str
    local_path: str
    sha256: str
    fetched_at: datetime
    format: str
    commit_sha: str = ""
    extraction_target: str = ""


@dataclass
class Manifest:
    entries: list[ManifestEntry] = field(default_factory=list)

    def add(self, entry: ManifestEntry) -> None:
        self.entries.append(entry)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(self.entries, key=lambda e: e.local_path)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t", lineterminator="\n")
            writer.writerow(COLUMNS)
            for e in rows:
                writer.writerow(
                    [
                        e.source_url,
                        e.local_path,
                        e.sha256,
                        e.fetched_at.isoformat(),
                        e.format,
                        e.commit_sha,
                        e.extraction_target,
                    ]
                )

    @classmethod
    def read(cls, path: Path) -> Manifest:
        m = cls()
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                m.add(
                    ManifestEntry(
                        source_url=row["source_url"],
                        local_path=row["local_path"],
                        sha256=row["sha256"],
                        fetched_at=datetime.fromisoformat(row["fetched_at"]),
                        format=row["format"],
                        commit_sha=row.get("commit_sha", ""),
                        extraction_target=row.get("extraction_target", ""),
                    )
                )
        return m


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

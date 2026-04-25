"""Generate ``sources/ydb/manifest.tsv`` from a cloned YottaDB docs repo.

One row per file in the working tree (excluding ``.git/``). Every row
records the upstream remote URL, the pinned commit SHA, the file's
sha256, and a coarse format tag derived from the file extension.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from m_standard.tools.manifest import Manifest, ManifestEntry, sha256_of

_FORMAT_BY_SUFFIX = {
    ".rst": "rst",
    ".md": "md",
    ".txt": "txt",
    ".html": "html",
    ".htm": "html",
}


def build_manifest(repo: Path, upstream: str, commit: str, out: Path) -> Manifest:
    repo = repo.resolve()
    manifest = Manifest()
    fetched_at = datetime.now(tz=timezone.utc)

    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(repo)
        except ValueError:
            continue
        # Skip the embedded .git/ working state — it is the cloning
        # mechanism, not source content.
        if rel.parts and rel.parts[0] == ".git":
            continue
        local_path = (Path(repo.name) / rel).as_posix()
        fmt = _format_for(path.suffix.lower())
        manifest.add(
            ManifestEntry(
                source_url=f"{upstream}#{commit}:{rel.as_posix()}",
                local_path=local_path,
                sha256=sha256_of(path),
                fetched_at=fetched_at,
                format=fmt,
                commit_sha=commit,
            )
        )

    manifest.write(out)
    return manifest


def _format_for(suffix: str) -> str:
    return _FORMAT_BY_SUFFIX.get(suffix, "asset")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate manifest.tsv for a cloned YottaDB docs repo."
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    build_manifest(
        repo=args.repo, upstream=args.upstream, commit=args.commit, out=args.out
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

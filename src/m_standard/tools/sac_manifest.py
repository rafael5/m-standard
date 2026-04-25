"""Generate ``sources/sac/manifest.tsv`` from the cloned XINDX routines.

Same shape as the other source manifests: one row per file with
URL, local path, sha256, fetched_at, format.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from m_standard.tools.manifest import Manifest, ManifestEntry, sha256_of


def build_manifest(routines: Path, upstream: str, out: Path) -> Manifest:
    routines = routines.resolve()
    manifest = Manifest()
    fetched_at = datetime.now(tz=timezone.utc)

    for path in sorted(routines.rglob("*.m")):
        rel = path.relative_to(routines.parent)
        manifest.add(
            ManifestEntry(
                source_url=f"{upstream}/{path.name}",
                local_path=rel.as_posix(),
                sha256=sha256_of(path),
                fetched_at=fetched_at,
                format="m-routine",
            )
        )

    manifest.write(out)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate manifest.tsv for the sources/sac/ XINDX clone."
    )
    parser.add_argument("--routines", type=Path, required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    build_manifest(args.routines, args.upstream, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

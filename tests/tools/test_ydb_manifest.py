from pathlib import Path

from m_standard.tools.manifest import Manifest
from m_standard.tools.ydb_manifest import build_manifest


def _make_repo(root: Path) -> Path:
    """Stand up a fake cloned-repo tree (no real git) for the walker."""
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "config").write_text("[fake]")
    (root / "AdminOpsGuide").mkdir(parents=True)
    (root / "AdminOpsGuide" / "intro.rst").write_text("Intro\n=====\n")
    (root / "ProgrammersGuide").mkdir(parents=True)
    (root / "ProgrammersGuide" / "commands.rst").write_text("Commands\n========\n")
    (root / "ProgrammersGuide" / "images").mkdir()
    (root / "ProgrammersGuide" / "images" / "fig1.png").write_bytes(b"PNG\x89")
    (root / "README.md").write_text("# yottadb docs\n")
    return root


def test_build_manifest_walks_repo_skipping_dot_git(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path / "repo")
    out = tmp_path / "manifest.tsv"
    build_manifest(
        repo=repo, upstream="https://example.com/ydb.git", commit="abc123", out=out
    )
    m = Manifest.read(out)
    paths = sorted(e.local_path for e in m.entries)
    assert paths == [
        "repo/AdminOpsGuide/intro.rst",
        "repo/ProgrammersGuide/commands.rst",
        "repo/ProgrammersGuide/images/fig1.png",
        "repo/README.md",
    ]


def test_build_manifest_records_commit_and_format(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path / "repo")
    out = tmp_path / "manifest.tsv"
    build_manifest(
        repo=repo, upstream="https://example.com/ydb.git", commit="abc123", out=out
    )
    m = Manifest.read(out)
    by_path = {e.local_path: e for e in m.entries}
    assert by_path["repo/README.md"].commit_sha == "abc123"
    assert by_path["repo/README.md"].format == "md"
    assert by_path["repo/AdminOpsGuide/intro.rst"].format == "rst"
    assert by_path["repo/ProgrammersGuide/images/fig1.png"].format == "asset"
    assert by_path["repo/README.md"].source_url.startswith("https://example.com/ydb.git")

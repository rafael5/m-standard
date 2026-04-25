"""Per-source extractor for the InterSystems IRIS docs subset.

Reads the local mirror under ``sources/iris/site/`` (produced by
``crawl_iris``) and writes raw per-source TSVs under
``per-source/iris/``. Per spec §4.3, IRIS is a third primary source
alongside AnnoStd and YottaDB; per AD-01 it's a peer of YottaDB for
implementation detail (neither outranks the other), with
IRIS-specific extensions tagged ``iris-extension``.

v0.2 ships extraction for:
- **System errors** (``RERR_system.html``): M-language runtime
  errors, parsed from the 2-cell ``[<NAME>, description]`` table rows.
- **Commands** (``RCOS_c*.html``, ``RCOS_cz*.html``): per-page entries
  with name in the ``<h1>``, syntax in the Synopsis section,
  description in the Description section.
- **Intrinsic functions** (``RCOS_f*.html``): same shape as commands
  but ``$``-prefixed names.
- **Special variables** (``RCOS_v*.html``): same shape, ``$``-prefixed.

Per-page filenames carry the concept hint via filename prefix
(``RCOS_c`` = command, ``RCOS_f`` = function, ``RCOS_v`` = svn,
``RCOS_cz`` = z-command). TOC pages like ``RCOS_COMMANDS.html`` and
``RCOS.html`` are skipped — they have uppercase IDs without the
lowercase concept-letter prefix.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from dataclasses import dataclass, fields
from pathlib import Path
from warnings import filterwarnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

log = logging.getLogger(__name__)

DEFAULT_SITE = Path("sources/iris/site")
DEFAULT_OUT_DIR = Path("per-source/iris")

_ERROR_COLUMNS: tuple[str, ...] = (
    "mnemonic",
    "summary",
    "kind",
    "standard_status_hint",
    "source_section",
)

_ENTRY_COLUMNS: tuple[str, ...] = (
    "canonical_name",
    "abbreviation",
    "format",
    "standard_status_hint",
    "source_section",
    "description",
)

_ERROR_NAME = re.compile(r"^<([A-Z][A-Z0-9]+)>$")
# Names like "BREAK (ObjectScript)" or "$ASCII (ObjectScript)" or
# "$DEVICE (ObjectScript)". Strip the trailing parenthetical suffix.
_H1_NAME = re.compile(r"^(\$?[A-Za-z][A-Za-z0-9]*)\s*(?:\([^)]*\))?\s*$")


@dataclass(frozen=True)
class IrisError:
    mnemonic: str
    summary: str
    kind: str
    standard_status_hint: str
    source_section: str


@dataclass(frozen=True)
class IrisEntry:
    """Shared shape for command / function / svn rows from RCOS pages."""

    canonical_name: str
    abbreviation: str
    format: str
    standard_status_hint: str
    source_section: str
    description: str


# Backwards-compat aliases for test ergonomics.
IrisCommand = IrisEntry
IrisFunction = IrisEntry
IrisSpecialVariable = IrisEntry


def extract_errors(site_dir: Path) -> list[IrisError]:
    """Parse ``site_dir/RERR_system.html`` for system-error definitions.

    Each error renders as a 2-cell table row: ``[<NAME>, description]``.
    Mnemonics starting with ``Z`` (e.g. ``<ZDIVIDE>``) are tagged
    ``iris-extension``; everything else is ``ansi`` (the M-language
    runtime errors, mappable to AnnoStd Annex B M-codes via
    ``mappings/iris-ansi-errors.tsv`` once that file lands).
    """
    page = site_dir / "RERR_system.html"
    if not page.exists():
        return []
    soup = BeautifulSoup(page.read_bytes(), "lxml")
    rel = page.relative_to(page.parent.parent).as_posix()

    out: list[IrisError] = []
    seen: set[str] = set()
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        first = _normspace(cells[0].get_text(separator=" "))
        match = _ERROR_NAME.match(first)
        if not match:
            continue
        mnemonic = match.group(1)
        if mnemonic in seen:
            continue
        seen.add(mnemonic)
        out.append(
            IrisError(
                mnemonic=mnemonic,
                summary=_normspace(cells[1].get_text(separator=" ")),
                kind="",
                standard_status_hint=(
                    "iris-extension" if mnemonic.startswith("Z") else "ansi"
                ),
                source_section=f"{rel}#{mnemonic}",
            )
        )
    out.sort(key=lambda e: e.mnemonic)
    return out


def write_errors_tsv(errors: list[IrisError], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_ERROR_COLUMNS)
        for err in errors:
            writer.writerow([getattr(err, c) for c in _ERROR_COLUMNS])
    assert {f.name for f in fields(IrisError)} >= set(_ERROR_COLUMNS)


# ---------- Commands / Functions / Special variables ----------------------

def extract_commands(site_dir: Path) -> list[IrisEntry]:
    """Extract commands from ``RCOS_c*.html`` and ``RCOS_cz*.html`` pages."""
    return _extract_rcos_entries(
        site_dir,
        filename_prefixes=("RCOS_c",),  # matches RCOS_cbreak, RCOS_czbreak, …
        z_filename_marker="cz",
    )


def extract_intrinsic_functions(site_dir: Path) -> list[IrisEntry]:
    """Extract functions from ``RCOS_f*.html`` pages."""
    return _extract_rcos_entries(
        site_dir,
        filename_prefixes=("RCOS_f",),
        z_filename_marker="fz",
    )


def extract_special_variables(site_dir: Path) -> list[IrisEntry]:
    """Extract intrinsic special variables from ``RCOS_v*.html`` pages."""
    return _extract_rcos_entries(
        site_dir,
        filename_prefixes=("RCOS_v",),
        z_filename_marker="vz",
    )


def _extract_rcos_entries(
    site_dir: Path,
    *,
    filename_prefixes: tuple[str, ...],
    z_filename_marker: str,
) -> list[IrisEntry]:
    if not site_dir.is_dir():
        return []
    out: list[IrisEntry] = []
    seen: set[str] = set()
    for prefix in filename_prefixes:
        for page in sorted(site_dir.glob(f"{prefix}*.html")):
            stem = page.stem  # e.g. "RCOS_cbreak"
            after_underscore = stem.split("_", 1)[1] if "_" in stem else stem
            # Skip TOCs / non-entry pages: their stems start with an
            # uppercase concept word ("COMMANDS", "FUNCTIONS", etc.)
            # rather than the lowercase concept-letter prefix.
            if not after_underscore[:1].islower():
                continue
            entry = _extract_rcos_page(page, z_filename_marker=z_filename_marker)
            if entry is None or entry.canonical_name in seen:
                continue
            seen.add(entry.canonical_name)
            out.append(entry)
    out.sort(key=lambda e: e.canonical_name)
    return out


def _extract_rcos_page(page: Path, *, z_filename_marker: str) -> IrisEntry | None:
    soup = BeautifulSoup(page.read_bytes(), "lxml")
    article = soup.find("article") or soup
    h1 = article.find("h1")
    if h1 is None:
        return None
    h1_text = _normspace(h1.get_text(separator=" "))
    name_match = _H1_NAME.match(h1_text)
    if not name_match:
        return None
    canonical = name_match.group(1)
    if canonical.startswith("$"):
        canonical = "$" + canonical[1:].upper()
    else:
        canonical = canonical.upper()

    fmt = _section_first_pre_or_paragraph(article, "Synopsis")
    description = _section_first_paragraph(article, "Description")

    rel = page.relative_to(page.parent.parent).as_posix()

    # Z-prefix heuristic: filename pattern (RCOS_cz*, RCOS_fz*, RCOS_vz*)
    # is the strongest hint; some entries (CATCH, THROW) are IRIS-only
    # extensions but don't carry the Z prefix — the reconciler will
    # reclassify them per AD-01 once it sees they're absent from AnnoStd.
    stem_after = page.stem.split("_", 1)[1] if "_" in page.stem else page.stem
    is_z = (
        stem_after.startswith(z_filename_marker)
        or canonical.lstrip("$").startswith("Z")
    )
    return IrisEntry(
        canonical_name=canonical,
        abbreviation="",  # IRIS docs rarely surface abbreviations in synopsis
        format=fmt,
        standard_status_hint="iris-extension" if is_z else "ansi",
        source_section=f"{rel}#{page.stem}",
        description=description,
    )


def _section_first_pre_or_paragraph(article, heading_text: str) -> str:
    """Find the named section and return its first <pre> or <p> text."""
    for h2 in article.find_all("h2"):
        if heading_text.lower() in h2.get_text(separator=" ").lower():
            section = h2.find_parent("section")
            if section is None:
                # Fall back to scanning siblings until the next h2.
                container = h2.parent
            else:
                container = section
            pre = container.find("pre")
            if pre is not None:
                return _normspace(pre.get_text(separator=" "))
            p = container.find("p")
            if p is not None:
                return _normspace(p.get_text(separator=" "))
            return ""
    return ""


def _section_first_paragraph(article, heading_text: str) -> str:
    """Find the named section and return its first <p> text."""
    for h2 in article.find_all("h2"):
        if heading_text.lower() in h2.get_text(separator=" ").lower():
            section = h2.find_parent("section")
            container = section if section is not None else h2.parent
            p = container.find("p")
            if p is not None:
                return _normspace(p.get_text(separator=" "))
            return ""
    return ""


def write_commands_tsv(entries: list[IrisEntry], out: Path) -> None:
    _write_entries_tsv(entries, out)


def write_intrinsic_functions_tsv(entries: list[IrisEntry], out: Path) -> None:
    _write_entries_tsv(entries, out)


def write_special_variables_tsv(entries: list[IrisEntry], out: Path) -> None:
    _write_entries_tsv(entries, out)


def _write_entries_tsv(entries: list[IrisEntry], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(_ENTRY_COLUMNS)
        for entry in entries:
            writer.writerow([getattr(entry, c) for c in _ENTRY_COLUMNS])
    assert {f.name for f in fields(IrisEntry)} >= set(_ENTRY_COLUMNS)


def _normspace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Extract per-source TSVs from the IRIS local mirror."
    )
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    if not args.site.is_dir():
        log.error(
            "site dir not found: %s — run `make sources-iris` first", args.site
        )
        return 1

    errors = extract_errors(args.site)
    write_errors_tsv(errors, args.out_dir / "errors.tsv")
    log.info("wrote %d IRIS errors -> %s/errors.tsv", len(errors), args.out_dir)

    cmds = extract_commands(args.site)
    write_commands_tsv(cmds, args.out_dir / "commands.tsv")
    log.info("wrote %d IRIS commands -> %s/commands.tsv", len(cmds), args.out_dir)

    funcs = extract_intrinsic_functions(args.site)
    write_intrinsic_functions_tsv(
        funcs, args.out_dir / "intrinsic-functions.tsv"
    )
    log.info(
        "wrote %d IRIS intrinsic functions -> %s/intrinsic-functions.tsv",
        len(funcs), args.out_dir,
    )

    svns = extract_special_variables(args.site)
    write_special_variables_tsv(
        svns, args.out_dir / "intrinsic-special-variables.tsv"
    )
    log.info(
        "wrote %d IRIS ISVs -> %s/intrinsic-special-variables.tsv",
        len(svns), args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

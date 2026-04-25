"""Per-source extractor for the InterSystems IRIS docs subset.

Reads the local mirror under ``sources/iris/site/`` (produced by
``crawl_iris``) and writes raw per-source TSVs under
``per-source/iris/``. Per spec §4.3, IRIS is a third primary source
alongside AnnoStd and YottaDB; per AD-01 it's a peer of YottaDB for
implementation detail (neither outranks the other), with
IRIS-specific extensions tagged ``iris-extension``.

v0.2 ships extraction for system errors only — the M-language
``<NAME>``-style runtime errors documented at KEY=RERR_system.
Other concept families (commands, intrinsic functions, ISVs) are
deferred until the IRIS RCOS extractor is built.
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

_ERROR_NAME = re.compile(r"^<([A-Z][A-Z0-9]+)>$")


@dataclass(frozen=True)
class IrisError:
    mnemonic: str
    summary: str
    kind: str
    standard_status_hint: str
    source_section: str


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ILANG
# [TYPE:script][PROJECT:vpsticker][LANG:en]
# ::ROLE{Export data/offers.json into the public, citable dataset/ files}
# ::WHY{The site refreshes every 6 hours, but dataset/ is what third parties
#       (awesome-public-datasets, Zenodo, Hugging Face) actually cite. If it is
#       not regenerated alongside data/, the published snapshot silently goes stale
#       while the metadata still claims a 6-hour cadence.}
# ::MUST{Be deterministic: the same data/offers.json must produce byte-identical output}
# ::MUST{Never invent a price. This only reshapes what scraper.py already fetched}
# ::BOUNDARY{never:write anything outside data/ and dataset/|scope:permanent}
"""dataset_export.py — rebuild the published dataset from the current scrape.

Input : data/offers.json            (written by scraper.py)
Output: dataset/vpsticker-vps-prices.json   (byte-identical copy of the input)
        dataset/vpsticker-vps-prices.csv    (flat rows, sorted by price_monthly)
        dataset/fetch-status.csv            (per-provider fetch status, incl. failures)
        dataset/README.md                   (snapshot date + counts refreshed in place)

Standard library only. No network, no API keys.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "offers.json"
OUT = ROOT / "dataset"

JSON_OUT = OUT / "vpsticker-vps-prices.json"
CSV_OUT = OUT / "vpsticker-vps-prices.csv"
STATUS_OUT = OUT / "fetch-status.csv"
README = OUT / "README.md"

OFFER_COLUMNS = (
    "provider", "title", "price", "currency", "period",
    "price_monthly", "offer_url", "source_url", "extraction", "fetched_at",
)
STATUS_COLUMNS = (
    "provider", "url", "http", "status", "extraction", "offers", "note",
)


def sort_key(offer: dict):
    """Sort by price_monthly ascending; offers with no price go last.

    Ties keep the input order (Python's sort is stable), which matches the
    ordering already published in the dataset.
    """
    value = offer.get("price_monthly")
    if value is None or value == "":
        return (1, 0.0)
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, 0.0)


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    """CRLF + trailing newline, matching the files already published."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(columns), extrasaction="ignore", lineterminator="\r\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def update_readme(generated_at: str, offers: int, providers: int) -> bool:
    """Refresh the snapshot date and counts in dataset/README.md, in place."""
    if not README.exists():
        return False
    text = README.read_text(encoding="utf-8")
    day = generated_at[:10]

    new = re.sub(
        r"from the public pricing pages of \d+ hosting providers\.",
        f"from the public pricing pages of {providers} hosting providers.",
        text,
        count=1,
    )
    new = re.sub(
        r"Snapshot date: \*\*\d{4}-\d{2}-\d{2}\*\* \(UTC `[^`]+`\)",
        f"Snapshot date: **{day}** (UTC `{generated_at}`)",
        new,
        count=1,
    )
    new = re.sub(
        r"Offers: \*\*\d+\*\* across \*\*\d+\*\* providers",
        f"Offers: **{offers}** across **{providers}** providers",
        new,
        count=1,
    )
    if new == text:
        return False
    README.write_text(new, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    if not DATA.exists():
        print(f"[dataset] ABORT no input: {DATA}")
        return 1

    raw = DATA.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    OUT.mkdir(exist_ok=True)

    # 1. JSON — byte-identical copy, so the raw URL serves exactly what the site read.
    JSON_OUT.write_bytes(raw)

    # 2. Offers CSV — flat rows, sorted by normalised monthly price.
    offers = sorted(data.get("offers", []), key=sort_key)
    write_csv(CSV_OUT, OFFER_COLUMNS, offers)

    # 3. Fetch status CSV — includes providers that returned nothing (auditability).
    sources = data.get("sources", [])
    write_csv(STATUS_OUT, STATUS_COLUMNS, sources)

    # 4. README — snapshot date and counts.
    generated_at = data.get("generated_at", "")
    changed = update_readme(generated_at, len(offers), len(sources))

    print(
        f"[dataset] {len(offers)} offers / {len(sources)} providers "
        f"-> dataset/ (snapshot {generated_at})"
        + (" [README updated]" if changed else "")
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"[dataset] FAILED {type(exc).__name__}: {exc}")
        raise SystemExit(1)

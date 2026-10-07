#!/usr/bin/env python3
"""Download public hardware manuals listed in hardware_sources.json.

Run from anywhere inside the repository:

    python docs/hardware/download_hardware_docs.py

The script never treats an HTML error page as a successful PDF: downloaded
files must begin with the PDF signature and have non-trivial length.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "hardware_sources.json"


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 hardware-manual-downloader/1.0",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)

    header = destination.read_bytes()[:5]
    if header != b"%PDF-" or destination.stat().st_size < 10_000:
        destination.unlink(missing_ok=True)
        raise RuntimeError("response was not a valid/non-trivial PDF")


def main() -> int:
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = 0
    for record in records:
        destination = HERE / record["filename"]
        print(f"[{record['hardware']}] -> {destination.name}")
        try:
            download(record["url"], destination)
            print(f"  OK: {destination.stat().st_size / 1024:.0f} KiB")
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            failures += 1
            print(f"  FAILED: {exc}")
            print(f"  Source: {record['url']}")

    if failures:
        print(f"\n{failures} document(s) could not be downloaded. See README.md/source URLs.")
        return 1
    print("\nAll hardware manuals downloaded successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

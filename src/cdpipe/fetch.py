"""
src/cdpipe/fetch.py
Project : Campaign Donations
Date    : 2026-10-27
Purpose : Finish a large download with several parallel HTTP range requests.
          The FEC's S3 bucket resets long single connections, so the rest of
          the file is split into chunks fetched side by side, each retried on
          its own, then appended to the partial file in order.
Usage   : python -m cdpipe.fetch <url> <dest> [--workers 8] [--chunk-mb 512]
Change log:
  2026-10-27  0.1.0  Initial version.
"""

from __future__ import annotations

import argparse
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ALLOWED_PREFIX = "https://cg-519a459a-0ea3-42c2-b7bc-fa1143481f74.s3-us-gov-west-1.amazonaws.com/"


def plan(have: int, total: int, chunk: int) -> list[tuple[int, int]]:
    """Inclusive byte ranges still needed, in order."""
    return [(s, min(s + chunk, total) - 1) for s in range(have, total, chunk)]


def _size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")  # noqa: S310 (finish() checks the host)
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (https, fixed host)
        return int(r.headers["Content-Length"])


def _get(url: str, start: int, end: int, part: Path, tries: int = 20) -> Path:
    want = end - start + 1
    for attempt in range(tries):
        have = part.stat().st_size if part.exists() else 0
        if have == want:
            return part
        if have > want:
            part.unlink()
            have = 0
        req = urllib.request.Request(url, headers={"Range": f"bytes={start + have}-{end}"})  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(part, "ab") as out:  # noqa: S310
                shutil.copyfileobj(r, out, 1 << 20)
        except OSError as e:
            print(f"{part.name}: retry {attempt + 1} after {e}", flush=True)
            time.sleep(min(60, 5 * (attempt + 1)))
    raise RuntimeError(f"{part.name}: gave up after {tries} tries")


def finish(url: str, dest: Path, workers: int = 8, chunk: int = 512 << 20) -> None:
    if not url.startswith(ALLOWED_PREFIX):
        raise ValueError("only the FEC bulk-data bucket is allowed")
    total = _size(url)
    have = dest.stat().st_size if dest.exists() else 0
    ranges = plan(have, total, chunk)
    print(f"{(total - have) >> 20:,} MB left in {len(ranges)} chunks", flush=True)
    parts_dir = dest.with_suffix(".parts")
    parts_dir.mkdir(exist_ok=True)
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(_get, url, s, e, parts_dir / f"{s:015d}.part") for s, e in ranges]
        with open(dest, "ab") as out:
            for f in futures:  # append strictly in order as each chunk completes
                part = f.result()
                with open(part, "rb") as src:
                    shutil.copyfileobj(src, out, 1 << 20)
                part.unlink()
                print(
                    f"appended {part.name}; {out.tell() >> 20:,} MB of {total >> 20:,}", flush=True
                )
    parts_dir.rmdir()
    if dest.stat().st_size != total:
        raise RuntimeError("size mismatch after download")
    print("complete", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("dest", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk-mb", type=int, default=512)
    a = ap.parse_args()
    finish(a.url, a.dest, a.workers, a.chunk_mb << 20)


if __name__ == "__main__":
    main()

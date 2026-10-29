"""
src/cdpipe/narrow.py
Project : Campaign Donations
Date    : 2026-10-28
Purpose : Keep only some columns of a table streamed out of a pg_restore
          dump. The FEC's Schedule A tables carry about 80 columns, three of
          them full-text indexes; the site needs about 15. Restoring them
          whole filled the disk, so the load pipes
            pg_restore -a -t <table> -f - | python -m cdpipe.narrow --cols ...
          into a narrow COPY instead.
Usage   : python -m cdpipe.narrow --cols a,b,c [--where-in col=ids.txt]
            < pg_restore output > copy data
Change log:
  2026-10-28  0.1.0  Initial version.
  2026-10-28  0.1.0  --where-in row filter (Schedule A: candidate committees only).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

_HEADER = re.compile(rb"^COPY \S+ \((.*)\) FROM stdin;$")
_END = b"\\."


def header_columns(line: bytes) -> list[str]:
    """Column names of a pg_restore "COPY <table> (<cols>) FROM stdin;" line."""
    m = _HEADER.match(line.rstrip(b"\n"))
    if not m:
        raise ValueError(f"not a COPY header: {line[:80]!r}")
    return [c.strip().strip('"') for c in m.group(1).decode().split(",")]


def load_set(path: Path) -> set[bytes]:
    """Non-blank lines of a file, stripped, as a set of byte strings."""
    return {v for v in (line.strip() for line in path.read_bytes().splitlines()) if v}


def project(
    lines: Iterable[bytes], keep: list[str], where: tuple[str, set[bytes]] | None = None
) -> Iterator[bytes]:
    """Yield the data rows of the first COPY block, cut down to `keep`.

    With `where=(column, values)`, only rows whose raw value in that column is
    one of `values` are kept. COPY text format escapes tabs and newlines inside
    values, so splitting on a raw tab is exact.
    """
    it = iter(lines)
    for line in it:
        if line.startswith(b"COPY "):
            cols = header_columns(line)
            break
    else:
        raise ValueError("no COPY block in input")
    missing = [c for c in keep + ([where[0]] if where else []) if c not in cols]
    if missing:
        raise ValueError(f"columns not in table: {', '.join(missing)}")
    idx = [cols.index(c) for c in keep]
    w_idx, w_vals = (cols.index(where[0]), where[1]) if where else (-1, set())
    width = len(cols)
    for line in it:
        row = line.rstrip(b"\n")
        if row == _END:
            return
        f = row.split(b"\t")
        if len(f) != width:
            raise ValueError(f"row has {len(f)} fields, expected {width}: {row[:80]!r}")
        if w_idx >= 0 and f[w_idx] not in w_vals:
            continue
        yield b"\t".join([f[i] for i in idx]) + b"\n"
    raise ValueError("input ended before the end of the COPY block")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cdpipe.narrow")
    ap.add_argument("--cols", required=True, help="comma-separated columns to keep, in order")
    ap.add_argument(
        "--where-in",
        metavar="COL=FILE",
        help="keep only rows whose COL value is a line of FILE",
    )
    args = ap.parse_args(argv)
    where = None
    if args.where_in:
        col, _, file = args.where_in.partition("=")
        where = (col, load_set(Path(file)))
    out = sys.stdout.buffer
    out.writelines(project(sys.stdin.buffer, args.cols.split(","), where))
    out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

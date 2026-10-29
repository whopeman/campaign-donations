"""
src/cdpipe/cli.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Command line entry point.
Usage   : cdpipe demo  [--out site]   render a small made-up data set (layout check)
          cdpipe build [--out site]   render the site from the PostgreSQL database
Change log:
  2026-10-26  0.1.0  Initial version with the demo command.
  2026-10-29  0.1.0  Pass max_individual_gift_usd to the renderer (about page).
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from cdpipe.flags import load_flags
from cdpipe.models import Candidate, CandidateTotals, Donor, Gift
from cdpipe.render import Site


def _demo_data():
    """Clearly fictional records, for checking layout without the database."""
    jane = Candidate("H4NY99901", "EXAMPLE, JANE", "DEM", "H", "NY", "12", True, (2024,))
    sam = Candidate("H4NY99902", "SAMPLE, SAM", "REP", "H", "NY", "12", False, (2024,))
    pat = Candidate("S4NY99903", "PLACEHOLDER, PAT", "IND", "S", "NY", "00", False, (2024,))
    alice = Donor(
        "i:demo1", "DONOR, ALICE (DEMO)", "individual", "ALBANY", "NY", "EXAMPLE CO", "ENGINEER"
    )
    pac = Donor("c:C99999901", "DEMO FUTURE PAC", "committee", None, "NY", cmte_id="C99999901")
    gifts = [
        Gift(alice, jane, 2024, 3300, True, "2024-03-01", None),
        Gift(alice, pat, 2024, 1000, True, "2024-05-12", None),
        Gift(pac, jane, 2024, 125000, False, "2024-10-01", None, "Independent expenditure"),
        Gift(pac, sam, 2024, 5000, True, "2024-09-01", None, "PAC contribution"),
        Gift(pac, sam, 2024, 80000, True, "2024-10-15", None, "Independent expenditure"),
    ]
    totals = {
        (jane.cand_id, 2024): CandidateTotals(910000, 240000, 60000, 125000, 410000),
        (sam.cand_id, 2024): CandidateTotals(520000, 310000, 80000, 0, 150000),
        (pat.cand_id, 2024): CandidateTotals(90000, 0, 0, 0, 30000),
    }
    return [jane, sam, pat], [alice, pac], gifts, totals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cdpipe")
    ap.add_argument("command", choices=["demo", "build"])
    ap.add_argument("--out", type=Path, default=Path("site"))
    args = ap.parse_args(argv)
    flags = load_flags()
    site = Site(
        out_dir=args.out,
        cycles=flags.cycles,
        generated=dt.date.today().isoformat(),
        max_gift=flags.max_individual_gift_usd,
    )
    if args.command == "demo":
        site.build(*_demo_data())
    else:
        from cdpipe.db import build_from_db

        counts = build_from_db(site, flags)
        print(f"{counts['candidates']:,} candidate pages, {counts['donors']:,} donor pages")
    print(f"wrote site to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

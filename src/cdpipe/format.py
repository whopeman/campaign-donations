"""
src/cdpipe/format.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Display helpers: whole-dollar money, percentages, and URL-safe
          slugs for page file names.
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

MAX_SLUG = 80


def usd(amount) -> str:
    d = Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    return f"{sign}${abs(int(d)):,}"


def pct(part, whole) -> str:
    if not whole:
        return "0.0%"
    return f"{float(part) / float(whole) * 100:.1f}%"


_TITLES = re.compile(r"(?:^|(?<=[\s,]))(?:MR|MRS|MS|MISS|DR|HON)\.?(?=\s|,|$)")


def clean_name(name: str | None) -> str:
    """Drop courtesy titles (MR., MRS., DR.) that some filers include, keep suffixes."""
    n = _TITLES.sub(" ", (name or "").upper())
    n = re.sub(r"\s+", " ", n)
    n = re.sub(r"\s+,", ",", n)
    return n.strip(" ,")


def slugify(name: str | None, ident: str | None) -> str:
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    tail = re.sub(r"[^a-z0-9]+", "", (ident or "").lower())
    if not tail:
        return base[:MAX_SLUG].strip("-")
    room = MAX_SLUG - len(tail) - 1
    base = base[:room].strip("-")
    return f"{base}-{tail}" if base else tail

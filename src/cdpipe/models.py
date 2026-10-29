"""
src/cdpipe/models.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Plain data records passed from the database layer to the page
          renderer, plus the URLs and page paths derived from them.
Change log:
  2026-10-26  0.1.0  Initial version.
  2026-10-28  0.1.0  Short page paths (IDs and codes) in place of name slugs.
  2026-10-29  0.1.0  Excluded: a Schedule A record left out of the totals.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# Page file names stay at 16 characters or fewer, ".html" included: GoDaddy
# counts a longer name as two or more inodes, of 250,000 per account.
_CMTE_ID = re.compile(r"C\d{8}")
_HEX_KEY = re.compile(r"[0-9a-f]{12,}")
_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36(n: int, width: int) -> str:
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = _B36[r] + s
    return s.rjust(width, "0")


PARTIES = {
    "DEM": "Democratic",
    "REP": "Republican",
    "IND": "Independent",
    "LIB": "Libertarian",
    "GRE": "Green",
    "DFL": "Democratic-Farmer-Labor",
    "NNE": "None",
    "UNK": "Unknown",
}
OFFICES = {"H": "House", "S": "Senate", "P": "President"}


def party_name(code: str | None) -> str:
    return PARTIES.get((code or "").upper(), code or "Unknown")


def party_kind(code: str | None) -> str:
    """Chart style key: the major parties get their own, everyone else OTHER."""
    c = (code or "").upper()
    if c == "DFL":
        return "DEM"
    return c if c in {"DEM", "REP", "IND", "LIB", "GRE"} else "OTHER"


@dataclass(frozen=True)
class Candidate:
    cand_id: str
    name: str
    party: str | None
    office: str
    state: str
    district: str | None
    incumbent: bool
    cycles: tuple[int, ...]

    @property
    def path(self) -> str:
        """Site-relative path: the FEC ID, in a folder named by its state letters."""
        ident = re.sub(r"[^a-z0-9]", "", self.cand_id.lower())[:11] or "unknown"
        return f"candidates/{ident[2:4] or 'xx'}/{ident}.html"

    @property
    def party_full(self) -> str:
        return party_name(self.party)

    @property
    def office_full(self) -> str:
        office = OFFICES.get(self.office, self.office)
        if self.office == "H" and self.district and self.district not in {"00", "0"}:
            return f"{office}, {self.state} district {int(self.district)}"
        return f"{office}, {self.state}"

    @property
    def fec_url(self) -> str:
        return f"https://www.fec.gov/data/candidate/{self.cand_id}/"


@dataclass(frozen=True)
class Donor:
    key: str  # "i:<hash>" for individuals, "c:<committee id>" for committees
    name: str
    kind: str  # "individual" or "committee"
    city: str | None = None
    state: str | None = None
    employer: str | None = None
    occupation: str | None = None
    cmte_id: str | None = None
    has_page: bool = True  # individuals under the threshold have no page of their own

    @property
    def path(self) -> str:
        """Site-relative path, sharded so no folder passes about 1,000 files.

        Committees: their FEC ID, in a folder by its last digit. Individuals:
        "i" + the first 48 bits of their key in base 36 (10 characters).
        """
        kind, _, ident = self.key.partition(":")
        if kind == "c" and _CMTE_ID.fullmatch(ident):
            return f"donors/c{ident[-1]}/{ident.lower()}.html"
        if kind == "i" and _HEX_KEY.fullmatch(ident):
            h = ident
        else:
            h = hashlib.blake2b(self.key.encode(), digest_size=8).hexdigest()
        prefix = "i" if kind == "i" else "x"
        return f"donors/{h[:2]}/{prefix}{_base36(int(h[:12], 16), 10)}.html"

    @property
    def fec_url(self) -> str | None:
        if self.cmte_id:
            return f"https://www.fec.gov/data/committee/{self.cmte_id}/"
        return None


@dataclass(frozen=True)
class Gift:
    donor: Donor
    candidate: Candidate
    cycle: int
    amount: float
    support: bool
    date: str | None
    source_url: str | None
    via: str = "Contribution"
    count: int = 1  # gifts combined into this row


@dataclass(frozen=True)
class CandidateTotals:
    individual: float  # itemized individual contributions
    committee: float  # PAC and party contributions
    ie_support: float  # independent expenditures supporting
    ie_oppose: float  # independent expenditures opposing
    other_individual: float = 0  # unitemized (under $200) individual contributions


@dataclass(frozen=True)
class Excluded:
    """A Schedule A record left out of totals and donor pages (issue #3).
    The contributor's name is deliberately not carried."""

    candidate: Candidate
    cycle: int
    amount: float
    date: str | None
    source_url: str | None
    reason: str

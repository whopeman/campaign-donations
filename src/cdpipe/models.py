"""
src/cdpipe/models.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Plain data records passed from the database layer to the page
          renderer, plus the URLs and slugs derived from them.
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

from dataclasses import dataclass

from cdpipe.format import slugify

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
    def slug(self) -> str:
        return slugify(self.name, self.cand_id)

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
    def slug(self) -> str:
        return slugify(self.name, self.key.split(":", 1)[1])

    @property
    def path(self) -> str:
        """Site-relative path; donors are sharded by slug prefix to keep folders small."""
        return f"donors/{self.slug[:2]}/{self.slug}.html"

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

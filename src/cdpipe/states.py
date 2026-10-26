"""
src/cdpipe/states.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : US states, DC and territories that elect federal representatives,
          with postal codes (as used by the FEC) and Census FIPS codes (as
          used by the map).
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

from typing import NamedTuple


class State(NamedTuple):
    code: str
    name: str
    fips: str
    is_state: bool = True


STATES: tuple[State, ...] = (
    State("AL", "Alabama", "01"),
    State("AK", "Alaska", "02"),
    State("AZ", "Arizona", "04"),
    State("AR", "Arkansas", "05"),
    State("CA", "California", "06"),
    State("CO", "Colorado", "08"),
    State("CT", "Connecticut", "09"),
    State("DE", "Delaware", "10"),
    State("DC", "District of Columbia", "11", False),
    State("FL", "Florida", "12"),
    State("GA", "Georgia", "13"),
    State("HI", "Hawaii", "15"),
    State("ID", "Idaho", "16"),
    State("IL", "Illinois", "17"),
    State("IN", "Indiana", "18"),
    State("IA", "Iowa", "19"),
    State("KS", "Kansas", "20"),
    State("KY", "Kentucky", "21"),
    State("LA", "Louisiana", "22"),
    State("ME", "Maine", "23"),
    State("MD", "Maryland", "24"),
    State("MA", "Massachusetts", "25"),
    State("MI", "Michigan", "26"),
    State("MN", "Minnesota", "27"),
    State("MS", "Mississippi", "28"),
    State("MO", "Missouri", "29"),
    State("MT", "Montana", "30"),
    State("NE", "Nebraska", "31"),
    State("NV", "Nevada", "32"),
    State("NH", "New Hampshire", "33"),
    State("NJ", "New Jersey", "34"),
    State("NM", "New Mexico", "35"),
    State("NY", "New York", "36"),
    State("NC", "North Carolina", "37"),
    State("ND", "North Dakota", "38"),
    State("OH", "Ohio", "39"),
    State("OK", "Oklahoma", "40"),
    State("OR", "Oregon", "41"),
    State("PA", "Pennsylvania", "42"),
    State("RI", "Rhode Island", "44"),
    State("SC", "South Carolina", "45"),
    State("SD", "South Dakota", "46"),
    State("TN", "Tennessee", "47"),
    State("TX", "Texas", "48"),
    State("UT", "Utah", "49"),
    State("VT", "Vermont", "50"),
    State("VA", "Virginia", "51"),
    State("WA", "Washington", "53"),
    State("WV", "West Virginia", "54"),
    State("WI", "Wisconsin", "55"),
    State("WY", "Wyoming", "56"),
    State("AS", "American Samoa", "60", False),
    State("GU", "Guam", "66", False),
    State("MP", "Northern Mariana Islands", "69", False),
    State("PR", "Puerto Rico", "72", False),
    State("VI", "U.S. Virgin Islands", "78", False),
)

_BY_CODE = {s.code: s for s in STATES}
BY_FIPS = {s.fips: s for s in STATES}


def state_name(code: str) -> str | None:
    s = _BY_CODE.get(code.upper())
    return s.name if s else None


def get(code: str) -> State | None:
    return _BY_CODE.get(code.upper())

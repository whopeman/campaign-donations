"""
tests/test_states.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : State list used for the map and state pages.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

from cdpipe.states import STATES, state_name


def test_fifty_states_plus_dc_and_territories():
    codes = {s.code for s in STATES}
    assert len([s for s in STATES if s.is_state]) == 50
    assert {"DC", "PR", "GU", "VI", "AS", "MP"} <= codes


def test_lookup():
    assert state_name("ny") == "New York"
    assert state_name("ZZ") is None


def test_fips_codes_are_two_digits():
    assert all(len(s.fips) == 2 and s.fips.isdigit() for s in STATES)

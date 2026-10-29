"""
tests/test_flags.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Feature flags load from TOML and can be overridden by environment.
Change log:
  2026-10-26  0.1.0  Initial tests.
  2026-10-29  0.1.0  max_individual_gift_usd (#3).
"""

import pytest

from cdpipe.flags import load_flags


@pytest.fixture
def flags_file(tmp_path):
    p = tmp_path / "flags.toml"
    p.write_text(
        "use_gpu = true\ncycles = [2022, 2024]\ndonor_page_threshold_usd = 1000\n"
        'offices = ["H"]\ncounty_view = false\n',
        encoding="utf-8",
    )
    return p


def test_reads_values_from_file(flags_file):
    flags = load_flags(flags_file, env={})
    assert flags.use_gpu is True
    assert flags.cycles == (2022, 2024)
    assert flags.donor_page_threshold_usd == 1000
    assert flags.offices == ("H",)
    assert flags.county_view is False


def test_env_overrides_bool_and_int(flags_file):
    flags = load_flags(
        flags_file, env={"CD_USE_GPU": "false", "CD_DONOR_PAGE_THRESHOLD_USD": "250"}
    )
    assert flags.use_gpu is False
    assert flags.donor_page_threshold_usd == 250


def test_env_overrides_list(flags_file):
    flags = load_flags(flags_file, env={"CD_CYCLES": "2020,2022"})
    assert flags.cycles == (2020, 2022)


def test_rejects_bad_bool(flags_file):
    with pytest.raises(ValueError, match="CD_USE_GPU"):
        load_flags(flags_file, env={"CD_USE_GPU": "maybe"})


def test_rejects_odd_cycle(flags_file):
    with pytest.raises(ValueError, match="cycle"):
        load_flags(flags_file, env={"CD_CYCLES": "2023"})


def test_max_individual_gift_defaults_and_overrides(flags_file):
    assert load_flags(flags_file, env={}).max_individual_gift_usd == 20000
    flags = load_flags(flags_file, env={"CD_MAX_INDIVIDUAL_GIFT_USD": "15000"})
    assert flags.max_individual_gift_usd == 15000

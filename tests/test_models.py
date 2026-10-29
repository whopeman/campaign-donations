"""
tests/test_models.py
Project : Campaign Donations
Date    : 2026-10-28
Purpose : Page paths. GoDaddy counts a file name longer than 16 characters as
          two or more inodes (250,000 per account), so every page file name,
          ".html" included, must be 16 characters or fewer.
Change log:
  2026-10-28  0.1.0  Initial tests.
"""

from pathlib import PurePosixPath

import pytest

from cdpipe.models import Candidate, Donor


def cand(cand_id: str) -> Candidate:
    return Candidate(cand_id, "DOE, JANE", "DEM", "H", "NY", "12", False, (2024,))


def name_of(path: str) -> str:
    return PurePosixPath(path).name


def test_candidate_path_is_id_in_state_folder():
    assert cand("H4NY12345").path == "candidates/ny/h4ny12345.html"


def test_committee_donor_path_is_committee_id():
    d = Donor("c:C00999999", "BETTER FUTURE PAC", "committee", cmte_id="C00999999")
    assert d.path == "donors/c9/c00999999.html"


def test_individual_donor_path_is_short_code_of_key():
    d = Donor("i:0123456789abcdef", "SMITH, ALICE", "individual")
    folder, name = d.path.split("/")[1:]
    assert folder == "01"
    assert name.startswith("i") and name.endswith(".html")
    assert int(name[1:-5], 36) == 0x0123456789AB


@pytest.mark.parametrize(
    "key",
    ["i:ffffffffffffffff", "i:0000000000000000", "i:demo1", "c:C99999999", "c:ODD-ID"],
)
def test_donor_file_names_fit_one_inode(key):
    d = Donor(key, "X", "committee" if key.startswith("c:") else "individual")
    assert len(name_of(d.path)) <= 16
    assert ".." not in d.path and d.path.count("/") == 2


def test_candidate_file_names_fit_one_inode():
    assert len(name_of(cand("S6TX00001").path)) <= 16


def test_different_keys_give_different_paths():
    a = Donor("i:0123456789abcdef", "A", "individual")
    b = Donor("i:0123456789bbcdef", "B", "individual")
    assert a.path != b.path  # keys equal in their first 48 bits are caught by Site._write

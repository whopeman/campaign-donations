"""
tests/test_fetch.py
Project : Campaign Donations
Date    : 2026-10-27
Purpose : Range planning for the parallel downloader, and host restriction.
Change log:
  2026-10-27  0.1.0  Initial tests.
"""

from pathlib import Path

import pytest

from cdpipe.fetch import finish, plan


def test_plan_covers_remaining_bytes_exactly():
    r = plan(have=100, total=1000, chunk=300)
    assert r == [(100, 399), (400, 699), (700, 999)]


def test_plan_last_chunk_is_short():
    assert plan(0, 10, 4) == [(0, 3), (4, 7), (8, 9)]


def test_plan_nothing_left():
    assert plan(1000, 1000, 300) == []


def test_refuses_other_hosts(tmp_path: Path):
    with pytest.raises(ValueError, match="FEC"):
        finish("https://example.com/x.dump", tmp_path / "x")

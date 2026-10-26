"""
tests/test_format.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Money formatting and URL slugs.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

from decimal import Decimal

import pytest

from cdpipe.format import clean_name, pct, slugify, usd


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0, "$0"),
        (5, "$5"),
        (1234.4, "$1,234"),
        (1234.5, "$1,235"),
        (Decimal("-2500"), "-$2,500"),
        (12_345_678, "$12,345,678"),
    ],
)
def test_usd(amount, expected):
    assert usd(amount) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("OCASIO-CORTEZ, ALEXANDRIA", "OCASIO-CORTEZ, ALEXANDRIA"),
        ("TUCKER, ANTOINE MR.", "TUCKER, ANTOINE"),
        ("ZHERKA, HASIME SAMANTHA MRS.", "ZHERKA, HASIME SAMANTHA"),
        ("LANG, EDWARD JAKE MR", "LANG, EDWARD JAKE"),
        ("DR. SMITH, JOHN", "SMITH, JOHN"),
        ("CARL, JERRY LEE, JR", "CARL, JERRY LEE, JR"),
        ("  MRAZ,  MARY  ", "MRAZ, MARY"),
        (None, ""),
    ],
)
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


def test_pct():
    assert pct(1, 3) == "33.3%"
    assert pct(0, 0) == "0.0%"


@pytest.mark.parametrize(
    ("name", "ident", "expected"),
    [
        ("SMITH, JOHN Q.", "H2CA01234", "smith-john-q-h2ca01234"),
        ("O'Brien & Sons PAC", "C00123456", "o-brien-sons-pac-c00123456"),
        ("José Núñez", None, "jose-nunez"),
        ("", "C00000001", "c00000001"),
    ],
)
def test_slugify(name, ident, expected):
    assert slugify(name, ident) == expected


def test_slugify_limits_length():
    s = slugify("A" * 300, "C00000001")
    assert len(s) <= 80
    assert s.endswith("-c00000001")


def test_slugify_never_allows_path_tricks():
    assert "/" not in slugify("../../etc/passwd", None)
    assert ".." not in slugify("../../etc/passwd", None)

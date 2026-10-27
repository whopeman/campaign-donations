"""
tests/test_render.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : The renderer writes every page type, links candidates and donors
          both ways, links every figure to its FEC source, escapes data, and
          produces relative links that work under /campaign-donations/.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

from pathlib import Path

import pytest

from cdpipe.models import Candidate, CandidateTotals, Donor, Gift
from cdpipe.render import Site


@pytest.fixture
def data():
    jane = Candidate(
        cand_id="H4NY12345",
        name="DOE, JANE",
        party="DEM",
        office="H",
        state="NY",
        district="12",
        incumbent=True,
        cycles=(2024,),
    )
    bob = Candidate(
        cand_id="S6TX00001",
        name="ROE, BOB <i>",
        party="REP",
        office="S",
        state="TX",
        district="00",
        incumbent=False,
        cycles=(2024,),
    )
    alice = Donor(
        key="i:abc123",
        name="SMITH, ALICE",
        kind="individual",
        city="ALBANY",
        state="NY",
        employer="ACME",
        occupation="ENGINEER",
    )
    pac = Donor(
        key="c:C00999999",
        name="BETTER FUTURE PAC",
        kind="committee",
        state="DC",
        cmte_id="C00999999",
    )
    gifts = [
        Gift(
            donor=alice,
            candidate=jane,
            cycle=2024,
            amount=2500,
            support=True,
            date="2024-03-01",
            source_url="https://docquery.fec.gov/cgi-bin/fecimg/?111",
        ),
        Gift(
            donor=pac,
            candidate=jane,
            cycle=2024,
            amount=10000,
            support=False,
            date="2024-10-01",
            source_url="https://docquery.fec.gov/cgi-bin/fecimg/?222",
            via="Independent expenditure",
        ),
        Gift(
            donor=pac,
            candidate=bob,
            cycle=2024,
            amount=5000,
            support=True,
            date="2024-09-01",
            source_url="https://docquery.fec.gov/cgi-bin/fecimg/?333",
            via="Contribution",
        ),
    ]
    totals = {
        ("H4NY12345", 2024): CandidateTotals(
            individual=2500, committee=0, ie_support=0, ie_oppose=10000, other_individual=700
        ),
        ("S6TX00001", 2024): CandidateTotals(
            individual=0, committee=5000, ie_support=0, ie_oppose=0, other_individual=0
        ),
    }
    return [jane, bob], [alice, pac], gifts, totals


@pytest.fixture
def built(tmp_path, data):
    cands, donors, gifts, totals = data
    Site(out_dir=tmp_path, cycles=(2024,), generated="2026-10-26").build(
        cands, donors, gifts, totals
    )
    return tmp_path


def read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def test_home_has_title_and_clickable_map(built):
    html = read(built, "index.html")
    assert "Donor tracking and aggregation" in html
    assert 'href="states/ny/index.html"' in html
    assert "<svg" in html and "New York" in html


def test_every_state_page_exists(built):
    assert (built / "states/ny/index.html").exists()
    assert (built / "states/wy/index.html").exists()
    assert (built / "states/pr/index.html").exists()


def test_state_page_lists_its_candidates(built):
    ny = read(built, "states/ny/index.html")
    assert "DOE, JANE" in ny and "ROE" not in ny
    assert 'href="../../candidates/doe-jane-h4ny12345.html"' in ny


def test_candidate_page_pie_party_and_links(built):
    html = read(built, "candidates/doe-jane-h4ny12345.html")
    assert "Democratic" in html
    assert "<svg" in html and "Outside spending against" in html and "$10,000" in html
    assert "https://www.fec.gov/data/candidate/H4NY12345/" in html
    assert "../donors/sm/smith-alice-abc123.html" in html
    assert "fecimg/?222" in html


def test_donor_page_party_summary_and_for_against(built):
    html = read(built, "donors/be/better-future-pac-c00999999.html")
    assert "Democratic" in html and "Republican" in html
    assert "Against" in html and "For" in html
    assert "../../candidates/doe-jane-h4ny12345.html" in html
    assert "../../candidates/roe-bob-i-s6tx00001.html" in html
    assert "https://www.fec.gov/data/committee/C00999999/" in html


def test_donor_below_threshold_has_no_page_and_no_link(tmp_path, data):
    cands, donors, gifts, totals = data
    small = Donor(key="i:small1", name="SMALL, SUE", kind="individual", state="NY", has_page=False)
    gifts = [*gifts, Gift(small, cands[0], 2024, 250, True, "2024-02-02", "https://x.test/f")]
    Site(out_dir=tmp_path, cycles=(2024,), generated="2026-10-26").build(
        cands, [*donors, small], gifts, totals
    )
    html = read(tmp_path, "candidates/doe-jane-h4ny12345.html")
    assert "SMALL, SUE" in html
    assert "small-sue" not in html
    assert not (tmp_path / "donors/sm/small-sue-small1.html").exists()


def test_candidate_rows_combine_gifts_from_one_donor(tmp_path, data):
    cands, donors, gifts, totals = data
    alice = donors[0]
    extra = Gift(alice, cands[0], 2024, 500, True, "2024-06-01", "https://x.test/latest")
    Site(out_dir=tmp_path, cycles=(2024,), generated="2026-10-26").build(
        cands, donors, [*gifts, extra], totals
    )
    html = read(tmp_path, "candidates/doe-jane-h4ny12345.html")
    assert "$3,000" in html  # 2,500 + 500 on one row
    assert "https://x.test/latest" in html and "latest filing" in html


def test_candidate_page_notes_donors_left_off(tmp_path, data):
    cands, _, _, totals = data
    site = Site(out_dir=tmp_path, cycles=(2024,), generated="2026-10-26")
    site.common_pages()
    site.candidate_page(cands[0], {2024: totals[("H4NY12345", 2024)]}, {}, {2024: (1234, 56789)})
    html = read(tmp_path, "candidates/doe-jane-h4ny12345.html")
    assert "1,234 smaller donors" in html and "$56,789" in html


def test_long_names_give_short_titles(tmp_path, data):
    cands, _, _, totals = data
    long_pac = Donor(key="c:C00000042", name="A VERY LONG COMMITTEE NAME " * 5, kind="committee")
    site = Site(out_dir=tmp_path, cycles=(2024,), generated="2026-10-26")
    site.common_pages()
    site.donor_page(long_pac, [])
    html = read(tmp_path, long_pac.path)
    title = html.split("<title>")[1].split("</title>")[0]
    assert len(title) <= 70
    assert title.endswith("| Hopeman Horde")


def test_data_is_escaped(built):
    html = read(built, "candidates/roe-bob-i-s6tx00001.html")
    assert "<i>" not in html.split("<main")[1]
    assert "&lt;i&gt;" in html


def test_pages_carry_fec_use_notice_and_csp(built):
    html = read(built, "index.html")
    assert "may not be sold or used for commercial purposes" in html
    assert "Content-Security-Policy" in html


def test_writes_css_and_htaccess(built):
    assert (built / "css/site.css").exists()
    assert "Content-Security-Policy" in read(built, ".htaccess")

"""
tests/test_db.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Integration test: render pages from a small "site"-shaped schema in
          a real PostgreSQL database. Skipped unless CD_TEST_DSN is set, e.g.
          CD_TEST_DSN="dbname=fec" uv run pytest tests/test_db.py
Change log:
  2026-10-26  0.1.0  Initial tests.
  2026-10-28  0.1.0  Short page paths.
"""

import os

import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.environ.get("CD_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="CD_TEST_DSN not set")

SCHEMA = "site_test"
DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.candidate (cand_id text, cycle int, name text, party text, office text,
  state text, district text, incumbent boolean, pcc text);
CREATE TABLE {SCHEMA}.cand_totals (cand_id text, cycle int, individual numeric,
  committee numeric, ie_support numeric, ie_oppose numeric, other_individual numeric);
CREATE TABLE {SCHEMA}.gift (donor_key text, cand_id text, cycle int, amount numeric,
  support boolean, via text, gift_date date, source_url text, sub_id bigint);
CREATE TABLE {SCHEMA}.donor (donor_key text, name text, kind text, city text, state text,
  employer text, occupation text, cmte_id text, has_page boolean);
INSERT INTO {SCHEMA}.candidate VALUES
  ('H4NY00001', 2022, 'DOE, JANE', 'DEM', 'H', 'NY', '12', false, 'C1'),
  ('H4NY00001', 2024, 'DOE, JANE', 'DEM', 'H', 'NY', '12', true, 'C1');
INSERT INTO {SCHEMA}.cand_totals VALUES
  ('H4NY00001', 2024, 3000, 0, 0, 10000, 500),
  ('H4NY00001', 2022, 100, 0, 0, 0, 0);
INSERT INTO {SCHEMA}.donor VALUES
  ('i:aaa', 'SMITH, ALICE', 'individual', 'ALBANY', 'NY', 'ACME', 'ENGINEER', null, true),
  ('i:bbb', 'LOW, LARRY', 'individual', 'TROY', 'NY', null, null, null, false),
  ('c:C9', 'PAC NINE', 'committee', null, 'DC', null, null, 'C9', true);
INSERT INTO {SCHEMA}.gift VALUES
  ('i:aaa', 'H4NY00001', 2024, 2000, true, 'Contribution', '2024-01-02', 'https://f/1', 1),
  ('i:aaa', 'H4NY00001', 2024, 1000, true, 'Contribution', '2024-05-02', 'https://f/2', 2),
  ('i:bbb', 'H4NY00001', 2022, 100, true, 'Contribution', '2022-05-02', 'https://f/3', 3),
  ('c:C9', 'H4NY00001', 2024, 10000, false, 'Independent expenditure', '2024-10-01',
   'https://f/4', 4);
"""


@pytest.fixture(scope="module")
def db():
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(DDL)
        yield
        conn.execute(f"DROP SCHEMA {SCHEMA} CASCADE")


def test_build_from_db(tmp_path, db):
    from cdpipe.db import build_from_db
    from cdpipe.flags import Flags
    from cdpipe.render import Site

    flags = Flags(False, (2022, 2024), 1000, ("H",), False)
    site = Site(out_dir=tmp_path, cycles=flags.cycles, generated="2026-10-26")
    counts = build_from_db(site, flags, dsn=DSN, schema=SCHEMA)
    assert counts == {"candidates": 1, "donors": 2}

    from cdpipe.models import Donor

    cand = (tmp_path / "candidates/ny/h4ny00001.html").read_text(encoding="utf-8")
    assert "$3,000" in cand and "https://f/2" in cand  # combined, latest filing
    assert "LOW, LARRY" in cand and Donor("i:bbb", "", "individual").path not in cand
    assert "2021&ndash;2022" in cand

    pac = (tmp_path / Donor("c:C9", "", "committee").path).read_text(encoding="utf-8")
    assert "Against" in pac and "$10,000" in pac

    ny = (tmp_path / "states/ny/index.html").read_text(encoding="utf-8")
    assert "DOE, JANE" in ny and "SMITH, ALICE" in ny

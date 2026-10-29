"""
tests/test_sql.py
Project : Campaign Donations
Date    : 2026-10-29
Purpose : Integration test of the SQL that builds the "site" schema
          (sql/20_site.sql) and of the data validation (scripts/validate.sh,
          sql/90_validate.sql), on made-up FEC rows in a scratch database.
          Covers issues #1 (amended reports), #2 (committee linked to two
          candidates), #3 (implausible individual gifts), #4 (data through-date)
          and #5 (placeholder names, undated rows).
Usage   : CD_TEST_DSN="dbname=fec" uv run pytest tests/test_sql.py
          The role needs CREATEDB; the scratch database cd_sql_test is dropped
          afterwards. Skipped unless CD_TEST_DSN is set and psql is on PATH.
Change log:
  2026-10-29  0.1.0  Initial tests.
  2026-10-29  0.1.0  Committee missing from both committee lists (V5 on real data).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.environ.get("CD_TEST_DSN")
pytestmark = pytest.mark.skipif(
    not DSN or not shutil.which("psql"), reason="CD_TEST_DSN not set or psql missing"
)

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = "cd_sql_test"
MAX_GIFT = 20000

# Made-up FEC rows. Committees: C1 Doe (amendments), C2 Roe (bad rows,
# placeholders), C3 linked to two Mills candidate IDs, C5 Ode (self-funding).
FIXTURE = """
CREATE SCHEMA IF NOT EXISTS disclosure;
CREATE TABLE disclosure.fec_fitem_sched_e (cmte_id text, s_o_cand_id text, exp_amt numeric,
  s_o_ind text, exp_dt timestamp, dissem_dt timestamp, pdf_url text, image_num text,
  sub_id bigint, election_cycle int, memo_cd text, rpt_tp text);
CREATE TABLE disclosure.ofec_committee_history (committee_id text, name text, city text,
  state text, cycle int);
CREATE TABLE disclosure.sched_a_2024 PARTITION OF disclosure.sched_a FOR VALUES IN (2024);

INSERT INTO bulk.cn (cycle, cand_id, cand_name, cand_pty_affiliation, cand_office_st,
                     cand_office, cand_office_district, cand_ici, cand_pcc) VALUES
  (2024, 'H4NY00001', 'DOE, JANE', 'DEM', 'NY', 'H', '12', 'I', 'C1'),
  (2024, 'H4NY00002', 'ROE, RICHARD', 'REP', 'NY', 'H', '13', 'C', 'C2'),
  (2024, 'H2FL00003', 'MILLS, JOHN', 'REP', 'FL', 'H', '01', 'C', 'C3'),
  (2024, 'H4TN00004', 'MILLS, JOHN', 'REP', 'TN', 'H', '08', 'C', 'C3'),
  (2024, 'H4CA00005', 'ODE, FREDERICK J', 'REP', 'CA', 'H', '05', 'C', 'C5');
INSERT INTO bulk.ccl VALUES
  (2024, 'H4NY00001', 2024, 2024, 'C1', 'H', 'P', 1),
  (2024, 'H4NY00002', 2024, 2024, 'C2', 'H', 'P', 2),
  (2024, 'H2FL00003', 2024, 2024, 'C3', 'H', 'P', 3),
  (2024, 'H4TN00004', 2016, 2024, 'C3', 'H', 'P', 4),
  (2024, 'H4CA00005', 2024, 2024, 'C5', 'H', 'P', 5);
INSERT INTO bulk.cm (cycle, cmte_id, cmte_nm, cmte_st) VALUES
  (2024, 'C1', 'DOE FOR CONGRESS', 'NY'), (2024, 'C2', 'ROE FOR CONGRESS', 'NY'),
  (2024, 'C3', 'MILLS FOR CONGRESS', 'FL'), (2024, 'C5', 'ODE FOR CONGRESS', 'CA');
INSERT INTO bulk.weball (cycle, cand_id, ttl_indiv_contrib) VALUES
  (2024, 'H4NY00001', 10000), (2024, 'H4NY00002', 20000), (2024, 'H2FL00003', 1000),
  (2024, 'H4TN00004', 0), (2024, 'H4CA00005', 5200000);

INSERT INTO disclosure.sched_a (sub_id, cmte_id, two_year_transaction_period, entity_tp,
  is_individual, receipt_tp, memo_cd, contbr_nm, contbr_city, contbr_st, contbr_zip,
  contb_receipt_dt, contb_receipt_amt, image_num, file_num, rpt_tp, rpt_yr) VALUES
  -- #1: Q1 filed (file 100) and re-filed in full (file 101): count file 101 only.
  (1, 'C1', 2024, 'IND', true, '15', null, 'SMITH, ALICE', 'ALBANY', 'NY', '12207',
   '2024-01-10', 1000, 'img1', 100, 'Q1', 2024),
  (2, 'C1', 2024, 'IND', true, '15', null, 'LEE, BOB', 'TROY', 'NY', '12180',
   '2024-01-11', 500, 'img2', 100, 'Q1', 2024),
  (3, 'C1', 2024, 'IND', true, '15', null, 'SMITH, ALICE', 'ALBANY', 'NY', '12207',
   '2024-01-10', 1000, 'img3', 101, 'Q1', 2024),
  (4, 'C1', 2024, 'IND', true, '15', null, 'LEE, BOB', 'TROY', 'NY', '12180',
   '2024-01-11', 250, 'img4', 101, 'Q1', 2024),
  -- #1: Q2 (file 102) and a one-row partial amendment (file 103): keep both.
  (5, 'C1', 2024, 'IND', true, '15', null, 'SMITH, ALICE', 'ALBANY', 'NY', '12207',
   '2024-04-05', 2000, 'img5', 102, 'Q2', 2024),
  (6, 'C1', 2024, 'IND', true, '15', null, 'LEE, BOB', 'TROY', 'NY', '12180',
   '2024-04-06', 100, 'img6', 102, 'Q2', 2024),
  (7, 'C1', 2024, 'IND', true, '15', null, 'KIM, ANN', 'TROY', 'NY', '12180',
   '2024-04-07', 300, 'img7', 102, 'Q2', 2024),
  (8, 'C1', 2024, 'IND', true, '15', null, 'KIM, ANN', 'TROY', 'NY', '12180',
   '2024-04-08', 50, 'img8', 103, 'Q2', 2024),
  -- #1: two 12P reports for different periods (no date overlap): keep both.
  (9, 'C1', 2024, 'IND', true, '15', null, 'TAN, TOM', 'TROY', 'NY', '12180',
   '2024-02-01', 400, 'img9', 104, '12P', 2024),
  (10, 'C1', 2024, 'IND', true, '15', null, 'TAN, TOM', 'TROY', 'NY', '12180',
   '2024-05-01', 400, 'img10', 105, '12P', 2024),
  -- #2: one gift to the committee linked to both Mills IDs.
  (20, 'C3', 2024, 'IND', true, '15', null, 'GREEN, GAIL', 'MIAMI', 'FL', '33101',
   '2024-04-10', 700, 'img20', 200, 'Q2', 2024),
  -- #3: a typo, a committee flagged as an individual, a big negative typo, and a
  -- legitimate $10,500 check covering several elections.
  (30, 'C2', 2024, 'IND', true, '15', null, 'HARTSHORN, NANCY', 'DC', 'DC', '20001',
   '2024-04-11', 3958610, 'img30', 300, 'Q2', 2024),
  (31, 'C2', 2024, 'COM', true, '15J', null, 'TEAM ELISE', 'ALBANY', 'NY', '12207',
   '2024-04-11', 616785, 'img31', 300, 'Q2', 2024),
  (32, 'C2', 2024, 'IND', true, '15', null, 'BIG, NEGATIVE', 'TROY', 'NY', '12180',
   '2024-04-11', -50000, 'img32', 300, 'Q2', 2024),
  (33, 'C2', 2024, 'IND', true, '15', null, 'RICH, RITA', 'TROY', 'NY', '12180',
   '2024-04-12', 10500, 'img33', 300, 'Q2', 2024),
  -- #3: the candidate's own money, as IND under a short name and as CAN.
  (40, 'C5', 2024, 'IND', true, '15', null, 'ODE, FRED', 'LA', 'CA', '90001',
   '2024-03-01', 5000000, 'img40', 500, 'Q1', 2024),
  (41, 'C5', 2024, 'CAN', true, '15', null, 'ODE, FREDERICK', 'LA', 'CA', '90001',
   '2024-03-01', 100000, 'img41', 500, 'Q1', 2024),
  -- #5: placeholder names.
  (50, 'C2', 2024, 'IND', true, '15', null, 'ANONYMOUS, INDIVIDUAL-101', 'TROY', 'NY',
   '12180', '2024-03-05', 1500, 'img50', 301, 'Q1', 2024),
  (51, 'C2', 2024, 'IND', true, '15', null, 'UNKNOWN-DONOR', 'TROY', 'NY', '12180',
   '2024-03-05', 1500, 'img51', 301, 'Q1', 2024),
  (52, 'C2', 2024, 'IND', true, '15', null, 'N/A', 'TROY', 'NY', '12180',
   '2024-03-05', 1500, 'img52', 301, 'Q1', 2024),
  -- #5: an undated row for Alice with an old city: the dated rows must win.
  (60, 'C2', 2024, 'IND', true, '15', null, 'SMITH, ALICE', 'OLDTOWN', 'NY', '12207',
   null, 100, 'img60', 301, 'Q1', 2024);

-- A committee in neither the committee history nor the committee master.
INSERT INTO disclosure.fec_fitem_sched_e (cmte_id, s_o_cand_id, exp_amt, s_o_ind, exp_dt,
  image_num, sub_id, election_cycle) VALUES
  ('C9', 'H4NY00002', 2500, 'O', '2024-04-02', 'img90', 90, 2024);
"""


def _psql(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", TEST_DB, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _validate() -> subprocess.CompletedProcess:
    env = {**os.environ, "FEC_DB": TEST_DB, "CD_MAX_INDIVIDUAL_GIFT_USD": str(MAX_GIFT)}
    return subprocess.run(
        ["bash", str(ROOT / "scripts" / "validate.sh")], capture_output=True, text=True, env=env
    )


@pytest.fixture(scope="module")
def db():
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    try:
        _psql("-f", str(ROOT / "sql" / "10_bulk.sql"))
        _psql("-f", str(ROOT / "sql" / "15_sched_a.sql"))
        _psql("-c", FIXTURE)
        _psql(
            "-v",
            "cycles={2024}",
            "-v",
            "offices={H}",
            "-v",
            "threshold=1000",
            "-v",
            f"max_gift={MAX_GIFT}",
            "-f",
            str(ROOT / "sql" / "20_site.sql"),
        )
        with psycopg.connect(f"dbname={TEST_DB}", autocommit=True) as conn:
            yield conn
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")


def one(conn, q: str, *args):
    return conn.execute(q, args).fetchone()[0]


def individual(conn, cand_id: str) -> float:
    return float(one(conn, "SELECT individual FROM site.cand_totals WHERE cand_id = %s", cand_id))


# -- #1 amended reports ----------------------------------------------------------
def test_amended_report_counts_the_latest_full_filing_only(db):
    # File 101 replaces 100; 102 + its partial amendment 103; both 12P reports.
    assert individual(db, "H4NY00001") == 1250 + 2400 + 50 + 800
    assert one(db, "SELECT count(*) FROM site.gift WHERE sub_id IN (1, 2)") == 0


# -- #2 committee linked to two candidates --------------------------------------------
def test_committee_linked_to_two_candidates_counts_for_one(db):
    assert one(db, "SELECT count(*) FROM site.gift WHERE sub_id = 20") == 1
    assert individual(db, "H2FL00003") == 700  # election year = cycle wins
    assert individual(db, "H4TN00004") == 0


# -- #3 implausible individual gifts --------------------------------------------------
def test_implausible_individual_gifts_are_left_out(db):
    assert individual(db, "H4NY00002") == 10500 + 4500 + 100
    assert one(db, "SELECT count(*) FROM site.gift WHERE sub_id IN (30, 31, 32)") == 0
    reasons = dict(db.execute("SELECT sub_id, reason FROM site.excluded_gift").fetchall())
    assert set(reasons) == {30, 31, 32}
    assert "committee" in reasons[31].lower()


def test_excluded_records_keep_no_contributor_name(db):
    cols = {
        r[0]
        for r in db.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'site' AND table_name = 'excluded_gift'"
        ).fetchall()
    }
    assert cols >= {"cand_id", "cycle", "amount", "gift_date", "source_url", "reason"}
    assert not cols & {"name", "contbr_nm", "donor_key"}


def test_self_funding_is_kept(db):
    assert individual(db, "H4CA00005") == 5100000
    assert one(db, "SELECT bool_and(self_funded) FROM site.gift WHERE sub_id IN (40, 41)")


# -- #4 data through-date -----------------------------------------------------------
def test_through_date_is_the_last_fully_loaded_month(db):
    # Busiest month April (6 counted gifts); March has 5, May and January fewer
    # than 40% of April, so April is the last fully loaded month.
    assert one(db, "SELECT value FROM site.meta WHERE key = 'sched_a_through'") == "2024-04-30"
    assert one(db, "SELECT value FROM site.meta WHERE key = 'sched_a_cycle'") == "2024"


# -- #5 donor clean-ups ----------------------------------------------------------------
def test_placeholder_names_get_no_page(db):
    rows = db.execute(
        "SELECT name, has_page FROM site.donor WHERE kind = 'individual' "
        "AND name IN ('ANONYMOUS, INDIVIDUAL-101', 'UNKNOWN-DONOR', 'N/A')"
    ).fetchall()
    assert len(rows) == 3 and not any(p for _, p in rows)
    assert one(db, "SELECT has_page FROM site.donor WHERE name = 'RICH, RITA'")


def test_donor_details_come_from_dated_rows(db):
    assert one(db, "SELECT city FROM site.donor WHERE name = 'SMITH, ALICE'") == "ALBANY"


def test_unknown_committee_gets_a_readable_name_and_fec_id(db):
    name, cmte_id = db.execute(
        "SELECT name, cmte_id FROM site.donor WHERE donor_key = 'c:C9'"
    ).fetchone()
    assert (name, cmte_id) == ("Committee C9", "C9")


# -- validation (sql/90_validate.sql via scripts/validate.sh) ----------------------
def test_validate_passes_on_clean_data(db):
    r = _validate()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RESULT: PASS" in r.stdout


def _fails(db, setup: str, undo: str, check_id: str):
    db.execute(setup)
    try:
        r = _validate()
    finally:
        db.execute(undo)
    assert r.returncode == 1, r.stdout + r.stderr
    line = next(ln for ln in r.stdout.splitlines() if check_id in ln)
    assert "FAIL" in line


def test_v1_catches_a_row_counted_twice(db):
    _fails(
        db,
        "INSERT INTO site.gift SELECT donor_key, 'H4TN00004', cycle, amount, support, via, "
        "gift_date, source_url, sub_id FROM site.gift WHERE sub_id = 20",
        "DELETE FROM site.gift WHERE sub_id = 20 AND cand_id = 'H4TN00004'",
        "V1",
    )


def test_v2_checks_candidates_with_no_fec_summary(db):
    _fails(
        db,
        "UPDATE bulk.weball SET cand_id = 'X' WHERE cand_id = 'H4NY00001'",
        "UPDATE bulk.weball SET cand_id = 'H4NY00001' WHERE cand_id = 'X'",
        "V2",
    )


def test_v3_catches_a_large_gift_not_from_the_candidate(db):
    _fails(
        db,
        "UPDATE site.gift SET amount = 25000 WHERE sub_id = 33",
        "UPDATE site.gift SET amount = 10500 WHERE sub_id = 33",
        "V3",
    )


def test_v4_catches_placeholder_names_with_punctuation(db):
    _fails(
        db,
        "UPDATE site.donor SET has_page = true WHERE name = 'UNKNOWN-DONOR'",
        "UPDATE site.donor SET has_page = false WHERE name = 'UNKNOWN-DONOR'",
        "V4",
    )


def test_v5_catches_a_page_without_a_name(db):
    _fails(
        db,
        "UPDATE site.donor SET name = donor_key WHERE name = 'RICH, RITA'",
        "UPDATE site.donor SET name = 'RICH, RITA' WHERE name = donor_key AND kind = 'individual'",
        "V5",
    )


def test_validator_error_is_not_a_data_failure(db):
    db.execute("ALTER TABLE bulk.weball RENAME TO weball_x")
    try:
        r = _validate()
    finally:
        db.execute("ALTER TABLE bulk.weball_x RENAME TO weball")
    assert r.returncode == 2, r.stdout + r.stderr

-- =============================================================================
-- sql/15_sched_a.sql
-- Project : Campaign Donations
-- Date    : 2026-10-28
-- Purpose : Narrow Schedule A table: only the columns of the FEC's
--           disclosure.fec_fitem_sched_a that the site uses (types as in the
--           FEC dump). Partitions, one per cycle, are added by scripts/load.sh.
--           The filing link is built from image_num; the dump's pdf_url is the
--           same link (checked 2026-10-28), so it is not kept.
--           file_num, rpt_tp and rpt_yr identify the filing (report) each row
--           came from, so rows of superseded filings can be dropped (#1).
-- Usage   : psql -d fec -f sql/15_sched_a.sql   (via scripts/load.sh sched_a)
-- Change log:
--   2026-10-28  0.1.0  Initial version.
--   2026-10-29  0.1.0  file_num, rpt_tp, rpt_yr (amended reports, #1).
-- =============================================================================
\set ON_ERROR_STOP on
CREATE SCHEMA IF NOT EXISTS disclosure;

CREATE TABLE disclosure.sched_a (
  sub_id numeric(19, 0) NOT NULL,
  cmte_id varchar(9),
  two_year_transaction_period numeric(4, 0) NOT NULL,
  entity_tp varchar(3),
  is_individual boolean,
  receipt_tp varchar(3),
  memo_cd varchar(1),
  contbr_nm varchar(200),
  contbr_city varchar(30),
  contbr_st varchar(2),
  contbr_zip varchar(9),
  contbr_employer varchar(38),
  contbr_occupation varchar(38),
  contb_receipt_dt timestamp,
  contb_receipt_amt numeric(14, 2),
  image_num varchar(18),
  conduit_cmte_id varchar(9),
  file_num numeric(7, 0),
  rpt_tp varchar(3),
  rpt_yr numeric(4, 0)
) PARTITION BY LIST (two_year_transaction_period);

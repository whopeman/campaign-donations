-- =============================================================================
-- sql/10_bulk.sql
-- Project : Campaign Donations
-- Date    : 2026-10-26
-- Purpose : Tables for the FEC bulk files (pipe-delimited, no header). Each
--           row carries the cycle of the file it came from. Column order
--           follows the FEC data dictionaries:
--           https://www.fec.gov/campaign-finance-data/ (bulk data descriptions)
-- Usage   : psql -d fec -f sql/10_bulk.sql   (then scripts/load.sh copies data)
-- Change log:
--   2026-10-26  0.1.0  Initial version: cn, cm, ccl, pas2, weball.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS bulk;

DROP TABLE IF EXISTS bulk.cn, bulk.cm, bulk.ccl, bulk.pas2, bulk.weball;

CREATE TABLE bulk.cn (
  cycle int, cand_id text, cand_name text, cand_pty_affiliation text, cand_election_yr int,
  cand_office_st text, cand_office text, cand_office_district text, cand_ici text,
  cand_status text, cand_pcc text, cand_st1 text, cand_st2 text, cand_city text,
  cand_st text, cand_zip text
);

CREATE TABLE bulk.cm (
  cycle int, cmte_id text, cmte_nm text, tres_nm text, cmte_st1 text, cmte_st2 text,
  cmte_city text, cmte_st text, cmte_zip text, cmte_dsgn text, cmte_tp text,
  cmte_pty_affiliation text, cmte_filing_freq text, org_tp text, connected_org_nm text,
  cand_id text
);

CREATE TABLE bulk.ccl (
  cycle int, cand_id text, cand_election_yr int, fec_election_yr int, cmte_id text,
  cmte_tp text, cmte_dsgn text, linkage_id bigint
);

CREATE TABLE bulk.pas2 (
  cycle int, cmte_id text, amndt_ind text, rpt_tp text, transaction_pgi text, image_num text,
  transaction_tp text, entity_tp text, name text, city text, state text, zip_code text,
  employer text, occupation text, transaction_dt text, transaction_amt numeric(14, 2),
  other_id text, cand_id text, tran_id text, file_num bigint, memo_cd text, memo_text text,
  sub_id bigint
);

CREATE TABLE bulk.weball (
  cycle int, cand_id text, cand_name text, cand_ici text, pty_cd text,
  cand_pty_affiliation text, ttl_receipts numeric(14, 2), trans_from_auth numeric(14, 2),
  ttl_disb numeric(14, 2), trans_to_auth numeric(14, 2), coh_bop numeric(14, 2),
  coh_cop numeric(14, 2), cand_contrib numeric(14, 2), cand_loans numeric(14, 2),
  other_loans numeric(14, 2), cand_loan_repay numeric(14, 2), other_loan_repay numeric(14, 2),
  debts_owed_by numeric(14, 2), ttl_indiv_contrib numeric(14, 2), cand_office_st text,
  cand_office_district text, spec_election text, prim_election text, run_election text,
  gen_election text, gen_election_precent numeric, other_pol_cmte_contrib numeric(14, 2),
  pol_pty_contrib numeric(14, 2), cvg_end_dt text, indiv_refunds numeric(14, 2),
  cmte_refunds numeric(14, 2)
);

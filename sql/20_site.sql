-- =============================================================================
-- sql/20_site.sql
-- Project : Campaign Donations
-- Date    : 2026-10-26
-- Purpose : Build the "site" schema the page generator reads: candidates,
--           their committees, money for and against them, and donors.
-- Usage   : psql -d fec -v cycles='{2016,2018,2020,2022,2024,2026}' \
--                -v offices='{H,S}' -v threshold=1000 -f sql/20_site.sql
-- Notes   : - Individual donors have no FEC ID; they are keyed by normalised
--             name + 5-digit ZIP (see site.donor_key).
--           - Memo entries (memo_cd = 'X') are skipped to avoid double counts.
--           - Independent expenditures from 24/48-hour notices are skipped,
--             because the same spending is reported again on regular reports.
-- Change log:
--   2026-10-26  0.1.0  Initial version.
-- =============================================================================
\set ON_ERROR_STOP on
CREATE SCHEMA IF NOT EXISTS site;

-- Normalise an individual's name: upper case, punctuation to spaces, drop
-- titles and suffixes, collapse spaces. "Smith, John Q. Jr." -> "SMITH JOHN Q"
CREATE OR REPLACE FUNCTION site.norm_name(n text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT btrim(regexp_replace(
           regexp_replace(
             regexp_replace(upper(coalesce(n, '')), '[^A-Z ]+', ' ', 'g'),
             '\m(MR|MRS|MS|DR|JR|SR|II|III|IV|MD|PHD|ESQ)\M', ' ', 'g'),
           '\s+', ' ', 'g'))
$$;

CREATE OR REPLACE FUNCTION site.donor_key(n text, zip text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT 'i:' || left(md5(site.norm_name(n) || '|' || left(coalesce(zip, ''), 5)), 16)
$$;

-- Candidates -----------------------------------------------------------------
DROP TABLE IF EXISTS site.candidate CASCADE;
CREATE TABLE site.candidate AS
SELECT DISTINCT ON (cand_id, cycle)
       cand_id, cycle, cand_name AS name, cand_pty_affiliation AS party,
       cand_office AS office, cand_office_st AS state, cand_office_district AS district,
       cand_ici = 'I' AS incumbent, cand_pcc AS pcc
FROM bulk.cn
WHERE cycle = ANY (:'cycles'::int[]) AND cand_office = ANY (:'offices'::text[])
ORDER BY cand_id, cycle;
ALTER TABLE site.candidate ADD PRIMARY KEY (cand_id, cycle);

-- Principal and authorised committees of each candidate, per cycle.
DROP TABLE IF EXISTS site.cand_cmte;
CREATE TABLE site.cand_cmte AS
SELECT DISTINCT l.cand_id, l.cycle, l.cmte_id
FROM bulk.ccl l JOIN site.candidate c USING (cand_id, cycle)
WHERE l.cmte_dsgn IN ('P', 'A');
CREATE INDEX ON site.cand_cmte (cmte_id, cycle);

-- Gifts: one table for every kind of money for or against a candidate --------
DROP TABLE IF EXISTS site.gift;
CREATE TABLE site.gift (
  donor_key text NOT NULL,
  cand_id text NOT NULL,
  cycle int NOT NULL,
  amount numeric(14, 2) NOT NULL,
  support boolean NOT NULL,
  via text NOT NULL,
  gift_date date,
  source_url text,
  sub_id bigint
);

-- 1. Itemized individual contributions to the candidate's own committees.
INSERT INTO site.gift
SELECT site.donor_key(a.contbr_nm, a.contbr_zip), cc.cand_id, cc.cycle, a.contb_receipt_amt,
       true, 'Contribution', a.contb_receipt_dt::date,
       coalesce(a.pdf_url, 'https://docquery.fec.gov/cgi-bin/fecimg/?' || a.image_num), a.sub_id
FROM disclosure.fec_fitem_sched_a a
JOIN site.cand_cmte cc ON cc.cmte_id = a.cmte_id AND cc.cycle = a.two_year_transaction_period
WHERE a.is_individual AND a.memo_cd IS NULL;

-- 2. Contributions from PACs and party committees to candidates (bulk pas2).
--    Earmarked gifts passed through a conduit (WinRed, ActBlue, or a PAC that
--    forwards members' checks) are individuals' money: the candidate reports
--    them on Schedule A, so they are counted once, in step 1.
INSERT INTO site.gift
SELECT 'c:' || p.cmte_id, p.cand_id, p.cycle, p.transaction_amt, true,
       CASE p.transaction_tp WHEN '24Z' THEN 'In-kind contribution' ELSE 'PAC contribution' END,
       to_date(nullif(p.transaction_dt, ''), 'MMDDYYYY'),
       'https://docquery.fec.gov/cgi-bin/fecimg/?' || p.image_num, p.sub_id
FROM bulk.pas2 p JOIN site.candidate c ON c.cand_id = p.cand_id AND c.cycle = p.cycle
WHERE p.transaction_tp IN ('24K', '24Z') AND p.memo_cd IS NULL AND p.cmte_id IS DISTINCT FROM c.pcc
  AND p.cmte_id NOT IN ('C00694323', 'C00401224')  -- WinRed, ActBlue (conduits)
  AND coalesce(p.memo_text, '') NOT ILIKE '%EARMARK%';

-- 3. Independent expenditures for (S) or against (O) a candidate.
INSERT INTO site.gift
SELECT 'c:' || e.cmte_id, e.s_o_cand_id, c.cycle, e.exp_amt, e.s_o_ind = 'S',
       'Independent expenditure', coalesce(e.exp_dt, e.dissem_dt)::date,
       coalesce(e.pdf_url, 'https://docquery.fec.gov/cgi-bin/fecimg/?' || e.image_num), e.sub_id
FROM disclosure.fec_fitem_sched_e e
JOIN site.candidate c ON c.cand_id = e.s_o_cand_id AND c.cycle = e.election_cycle
WHERE e.s_o_ind IN ('S', 'O') AND e.memo_cd IS NULL AND coalesce(e.rpt_tp, '') NOT IN ('24', '48');

CREATE INDEX ON site.gift (cand_id, cycle);
CREATE INDEX ON site.gift (donor_key);

-- Totals per candidate and cycle (feeds the pie chart) -------------------------
DROP TABLE IF EXISTS site.cand_totals;
CREATE TABLE site.cand_totals AS
WITH g AS (
  SELECT cand_id, cycle,
         sum(amount) FILTER (WHERE via = 'Contribution') AS individual,
         sum(amount) FILTER (WHERE via IN ('PAC contribution', 'In-kind contribution')) AS committee,
         sum(amount) FILTER (WHERE via = 'Independent expenditure' AND support) AS ie_support,
         sum(amount) FILTER (WHERE via = 'Independent expenditure' AND NOT support) AS ie_oppose
  FROM site.gift GROUP BY cand_id, cycle
)
SELECT c.cand_id, c.cycle,
       coalesce(g.individual, 0) AS individual,
       coalesce(g.committee, 0) AS committee,
       coalesce(g.ie_support, 0) AS ie_support,
       coalesce(g.ie_oppose, 0) AS ie_oppose,
       greatest(coalesce(w.ttl_indiv_contrib, 0) - coalesce(g.individual, 0), 0) AS other_individual
FROM site.candidate c
LEFT JOIN g USING (cand_id, cycle)
LEFT JOIN bulk.weball w ON w.cand_id = c.cand_id AND w.cycle = c.cycle;
ALTER TABLE site.cand_totals ADD PRIMARY KEY (cand_id, cycle);

-- Donors -----------------------------------------------------------------------
DROP TABLE IF EXISTS site.donor;
CREATE TABLE site.donor AS
WITH ind AS (  -- most recent name/address seen for each individual key
  SELECT DISTINCT ON (k) k AS donor_key, contbr_nm AS name, contbr_city AS city,
         contbr_st AS state, contbr_employer AS employer, contbr_occupation AS occupation
  FROM (
    SELECT site.donor_key(a.contbr_nm, a.contbr_zip) AS k, a.*
    FROM disclosure.fec_fitem_sched_a a
    JOIN site.cand_cmte cc ON cc.cmte_id = a.cmte_id AND cc.cycle = a.two_year_transaction_period
    WHERE a.is_individual AND a.memo_cd IS NULL
  ) s
  ORDER BY k, contb_receipt_dt DESC
), cmte AS (
  SELECT DISTINCT ON (committee_id) 'c:' || committee_id AS donor_key, name, city, state,
         committee_id
  FROM disclosure.ofec_committee_history
  ORDER BY committee_id, cycle DESC
), cm AS (  -- bulk committee master, for committees newer than the history dump
  SELECT DISTINCT ON (cmte_id) 'c:' || cmte_id AS donor_key, cmte_nm AS name, cmte_city AS city,
         cmte_st AS state, cmte_id
  FROM bulk.cm
  ORDER BY cmte_id, cycle DESC
), peak AS (  -- best single-cycle total, for the page threshold
  SELECT donor_key, max(t) AS peak_cycle_total
  FROM (SELECT donor_key, cycle, sum(amount) AS t FROM site.gift GROUP BY 1, 2) x
  GROUP BY donor_key
)
SELECT p.donor_key,
       coalesce(i.name, m.name, b.name, p.donor_key) AS name,
       CASE WHEN p.donor_key LIKE 'c:%' THEN 'committee' ELSE 'individual' END AS kind,
       coalesce(i.city, m.city, b.city) AS city, coalesce(i.state, m.state, b.state) AS state,
       i.employer, i.occupation, coalesce(m.committee_id, b.cmte_id) AS cmte_id,
       p.donor_key LIKE 'c:%' OR p.peak_cycle_total >= :threshold AS has_page
FROM peak p
LEFT JOIN ind i ON i.donor_key = p.donor_key
LEFT JOIN cmte m ON m.donor_key = p.donor_key
LEFT JOIN cm b ON b.donor_key = p.donor_key;
ALTER TABLE site.donor ADD PRIMARY KEY (donor_key);

ANALYZE site.candidate, site.cand_cmte, site.gift, site.cand_totals, site.donor;

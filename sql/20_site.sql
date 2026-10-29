-- =============================================================================
-- sql/20_site.sql
-- Project : Campaign Donations
-- Date    : 2026-10-26
-- Purpose : Build the "site" schema the page generator reads: candidates,
--           their committees, money for and against them, and donors.
-- Usage   : psql -d fec -v cycles='{2016,2018,2020,2022,2024,2026}' \
--                -v offices='{H,S}' -v threshold=1000 -v max_gift=20000 \
--                -f sql/20_site.sql
-- Notes   : - Individual donors have no FEC ID; they are keyed by normalised
--             name + 5-digit ZIP (see site.donor_key).
--           - Memo entries (memo_cd = 'X') are skipped to avoid double counts.
--           - Independent expenditures from 24/48-hour notices are skipped,
--             because the same spending is reported again on regular reports.
--           - Rows of a filing that was later re-filed in full are skipped
--             (site.superseded_filing), so amendments are not counted twice.
--           - Implausible "individual" rows are kept out of totals and listed
--             in site.excluded_gift, without the contributor's name.
-- Change log:
--   2026-10-26  0.1.0  Initial version.
--   2026-10-28  0.1.0  Read the narrow disclosure.sched_a (sql/15_sched_a.sql);
--                      skip receipts with no amount.
--   2026-10-29  0.1.0  QA fixes: superseded filings (#1), one candidate per
--                      committee (#2), excluded implausible gifts (#3), data
--                      through-date in site.meta (#4), placeholder names and
--                      undated rows (#5).
--   2026-10-29  0.1.0  A committee in neither committee list is named by its
--                      FEC ID, not the internal key (V5 on real data).
-- =============================================================================
\set ON_ERROR_STOP on
CREATE SCHEMA IF NOT EXISTS site;
DROP VIEW IF EXISTS site.indiv_receipt;  -- depends on tables rebuilt below

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

-- Two "LAST, FIRST ..." names are the same person when the surnames match and
-- one first name starts the other: "ODE, FRED" and "ODE, FREDERICK J".
CREATE OR REPLACE FUNCTION site.same_person(a text, b text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT al <> '' AND al = bl AND af <> '' AND bf <> ''
         AND (af LIKE bf || '%' OR bf LIKE af || '%')
  FROM (SELECT site.norm_name(split_part(a, ',', 1)) AS al,
               split_part(site.norm_name(split_part(a, ',', 2)), ' ', 1) AS af,
               site.norm_name(split_part(b, ',', 1)) AS bl,
               split_part(site.norm_name(split_part(b, ',', 2)), ' ', 1) AS bf) p
$$;

-- Names filers use when they do not know the donor; not people (#5).
CREATE OR REPLACE FUNCTION site.is_placeholder(n text) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT site.norm_name(n) ~ '\m(ANONYMOUS|UNKNOWN|UNITEMIZED|REQUESTED)\M'
      OR site.norm_name(n) IN ('', 'N A', 'NONE', 'NOT PROVIDED')
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

-- The principal or authorised committee of each candidate, per cycle. A
-- committee is sometimes linked to two candidate IDs in one cycle (a candidate
-- who re-filed under a new ID, or ran for another seat). Its money goes to one
-- of them (#2): the candidate whose principal committee it is, then the link
-- for this cycle's election, then the one in the committee's state, then the
-- most recent election year and link.
DROP TABLE IF EXISTS site.cand_cmte;
CREATE TABLE site.cand_cmte AS
SELECT DISTINCT ON (l.cmte_id, l.cycle) l.cand_id, l.cycle, l.cmte_id
FROM bulk.ccl l
JOIN site.candidate c USING (cand_id, cycle)
LEFT JOIN (SELECT DISTINCT ON (cmte_id, cycle) cmte_id, cycle, cmte_st
           FROM bulk.cm ORDER BY cmte_id, cycle) m
  ON m.cmte_id = l.cmte_id AND m.cycle = l.cycle
WHERE l.cmte_dsgn IN ('P', 'A')
ORDER BY l.cmte_id, l.cycle,
         c.pcc IS NOT DISTINCT FROM l.cmte_id DESC,
         l.cand_election_yr IS NOT DISTINCT FROM l.cycle DESC,
         c.state IS NOT DISTINCT FROM m.cmte_st DESC,
         l.cand_election_yr DESC NULLS LAST, l.linkage_id DESC NULLS LAST;
CREATE INDEX ON site.cand_cmte (cmte_id, cycle);

-- Superseded filings (#1). The FEC's Schedule A holds the rows of every
-- filing, including reports that were later amended. An amendment normally
-- re-files the whole report, so a filing is superseded when a later filing of
-- the same report (committee, report year and type) has at least half as many
-- rows and overlapping receipt dates. Smaller later filings are partial
-- amendments (paper filers sent only the changed pages) or a separate report
-- of the same type for another period, and both are kept.
DROP TABLE IF EXISTS site.superseded_filing;
CREATE TABLE site.superseded_filing AS
WITH f AS (
  SELECT a.cmte_id, a.rpt_yr, a.rpt_tp, a.file_num, count(*) AS n,
         min(a.contb_receipt_dt) AS dmin, max(a.contb_receipt_dt) AS dmax
  FROM disclosure.sched_a a
  WHERE a.file_num IS NOT NULL AND a.cmte_id IN (SELECT cmte_id FROM site.cand_cmte)
  GROUP BY 1, 2, 3, 4
)
SELECT DISTINCT o.file_num
FROM f o
JOIN f n ON n.cmte_id = o.cmte_id AND n.rpt_yr IS NOT DISTINCT FROM o.rpt_yr
        AND n.rpt_tp IS NOT DISTINCT FROM o.rpt_tp AND n.file_num > o.file_num
        AND n.n >= 0.5 * o.n AND n.dmin <= o.dmax AND o.dmin <= n.dmax;
ALTER TABLE site.superseded_filing ADD PRIMARY KEY (file_num);

-- Individual receipts of candidate committees that count: not memo entries,
-- not from superseded filings. exclude_reason marks rows kept out (#3):
-- committees the filer flagged as individuals, and single gifts above
-- max_gift (either sign) unless the candidate gave them (entity type CAN, or
-- the candidate's name).
CREATE OR REPLACE VIEW site.indiv_receipt AS
SELECT a.*, cc.cand_id, cc.cycle,
       coalesce(a.entity_tp = 'CAN' OR (abs(a.contb_receipt_amt) > :max_gift
                                        AND site.same_person(a.contbr_nm, c.name)),
                false) AS self_funded,
       CASE WHEN a.entity_tp IN ('COM', 'PAC', 'CCM', 'PTY')
              THEN 'A committee reported as an individual'
            WHEN abs(a.contb_receipt_amt) > :max_gift AND a.entity_tp IS DISTINCT FROM 'CAN'
                 AND NOT site.same_person(a.contbr_nm, c.name)
              THEN 'Above the plausible limit for one person'
       END AS exclude_reason
FROM disclosure.sched_a a
JOIN site.cand_cmte cc ON cc.cmte_id = a.cmte_id AND cc.cycle = a.two_year_transaction_period
JOIN site.candidate c ON c.cand_id = cc.cand_id AND c.cycle = cc.cycle
WHERE a.is_individual AND a.memo_cd IS NULL
  AND a.contb_receipt_amt IS NOT NULL  -- a few FEC rows have no amount (5 in 2016-2026)
  AND NOT EXISTS (SELECT 1 FROM site.superseded_filing s WHERE s.file_num = a.file_num);

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
  sub_id bigint,
  self_funded boolean NOT NULL DEFAULT false  -- the candidate's own money
);

-- 1. Itemized individual contributions to the candidate's own committees.
INSERT INTO site.gift
SELECT site.donor_key(r.contbr_nm, r.contbr_zip), r.cand_id, r.cycle, r.contb_receipt_amt,
       true, 'Contribution', r.contb_receipt_dt::date,
       'https://docquery.fec.gov/cgi-bin/fecimg/?' || r.image_num, r.sub_id, r.self_funded
FROM site.indiv_receipt r
WHERE r.exclude_reason IS NULL;

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

-- Records left out (#3), listed on the site with their filing link. The
-- contributor's name is not kept: these rows are errors, so the name next to
-- the amount is most likely wrong.
DROP TABLE IF EXISTS site.excluded_gift;
CREATE TABLE site.excluded_gift AS
SELECT r.cand_id, r.cycle, r.contb_receipt_amt AS amount, r.contb_receipt_dt::date AS gift_date,
       'https://docquery.fec.gov/cgi-bin/fecimg/?' || r.image_num AS source_url,
       r.exclude_reason AS reason, r.sub_id::bigint AS sub_id
FROM site.indiv_receipt r
WHERE r.exclude_reason IS NOT NULL;

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
    SELECT site.donor_key(r.contbr_nm, r.contbr_zip) AS k, r.*
    FROM site.indiv_receipt r WHERE r.exclude_reason IS NULL
  ) s
  ORDER BY k, contb_receipt_dt DESC NULLS LAST  -- undated rows last (#5)
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
       coalesce(i.name, m.name, b.name,  -- a committee in neither list: its FEC ID
                CASE WHEN p.donor_key LIKE 'c:%' THEN 'Committee ' || substr(p.donor_key, 3) END,
                p.donor_key) AS name,
       CASE WHEN p.donor_key LIKE 'c:%' THEN 'committee' ELSE 'individual' END AS kind,
       coalesce(i.city, m.city, b.city) AS city, coalesce(i.state, m.state, b.state) AS state,
       i.employer, i.occupation,
       coalesce(m.committee_id, b.cmte_id,
                CASE WHEN p.donor_key LIKE 'c:%' THEN substr(p.donor_key, 3) END) AS cmte_id,
       p.donor_key LIKE 'c:%'
         OR (p.peak_cycle_total >= :threshold AND NOT site.is_placeholder(i.name)) AS has_page
FROM peak p
LEFT JOIN ind i ON i.donor_key = p.donor_key
LEFT JOIN cmte m ON m.donor_key = p.donor_key
LEFT JOIN cm b ON b.donor_key = p.donor_key;
ALTER TABLE site.donor ADD PRIMARY KEY (donor_key);

-- How current the data is (#4): the end of the last month of the newest cycle
-- whose itemized receipts are fully loaded, taken as having at least 40% of
-- that cycle's busiest month (late filings trickle in for months after).
DROP TABLE IF EXISTS site.meta;
CREATE TABLE site.meta (key text PRIMARY KEY, value text);
INSERT INTO site.meta
WITH newest AS (SELECT max(cycle) AS cycle FROM site.gift WHERE via = 'Contribution'),
m AS (
  SELECT (date_trunc('month', g.gift_date) + interval '1 month' - interval '1 day')::date AS d,
         count(*) AS n
  FROM site.gift g JOIN newest USING (cycle)
  WHERE g.via = 'Contribution' AND g.gift_date IS NOT NULL
  GROUP BY 1
)
SELECT k, v FROM (
  SELECT 'sched_a_through' AS k, max(d) FILTER (WHERE n >= 0.4 * busiest)::text AS v
  FROM (SELECT d, n, max(n) OVER () AS busiest FROM m) x
  UNION ALL
  SELECT 'sched_a_cycle', (SELECT cycle FROM newest)::text
) kv
WHERE v IS NOT NULL;

ANALYZE site.candidate, site.cand_cmte, site.superseded_filing, site.gift, site.excluded_gift,
        site.cand_totals, site.donor, site.meta;

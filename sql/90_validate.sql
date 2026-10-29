-- =============================================================================
-- sql/90_validate.sql
-- Project : Campaign Donations
-- Date    : 2026-10-29
-- Purpose : Data validation (QA). Checks the "site" schema for invariants that
--           should always hold, prints one PASS/FAIL/WARN line per check, and
--           exits non-zero if any check fails. Read-only.
-- Usage   : psql -d fec -X -q -f sql/90_validate.sql
--           Optional: -v max_lag_days=120 (data freshness warning, default 120)
-- Notes   : Checks against the FEC's published per-candidate totals (FEC API)
--           are in docs/qa/; this file only uses tables already in the database.
-- Change log:
--   2026-10-29  0.1.0  Initial version (QA, Riker).
-- =============================================================================
\set ON_ERROR_STOP on
\if :{?max_lag_days}
\else
  \set max_lag_days 120
\endif

CREATE TEMP TABLE qa_result (id text, status text, found bigint, detail text);

-- V1. A Schedule A row is counted at most once. A committee linked to two
--     candidate IDs in one cycle would count each gift for both.
INSERT INTO qa_result
SELECT 'V1 each Schedule A row counted once',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'Schedule A rows in site.gift more than once'
FROM (SELECT count(*) AS n FROM (SELECT sub_id FROM site.gift WHERE via = 'Contribution'
                                 GROUP BY sub_id HAVING count(*) > 1) d) x;

-- V2. Itemized individual money cannot exceed the FEC's total individual money
--     (itemized + unitemized) for the candidate. 2% + $1,000 slack for timing.
INSERT INTO qa_result
SELECT 'V2 itemized <= FEC total individual',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'candidate-cycles above bulk.weball ttl_indiv_contrib'
FROM (SELECT count(*) AS n FROM site.cand_totals t JOIN bulk.weball w USING (cand_id, cycle)
      WHERE t.individual > w.ttl_indiv_contrib * 1.02 + 1000) x;

-- V3. No single individual gift far above the legal limit, unless the donor is
--     the candidate (self-funding). Catches filer typos and committees
--     mis-flagged as individuals.
INSERT INTO qa_result
SELECT 'V3 no implausible individual gifts',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'individual gifts >= $20,000 not from the candidate'
FROM (SELECT count(*) AS n FROM site.gift g
      JOIN site.donor d USING (donor_key) JOIN site.candidate c USING (cand_id, cycle)
      WHERE g.via = 'Contribution' AND g.amount >= 20000
        AND split_part(d.name, ',', 1) <> split_part(c.name, ',', 1)) x;

-- V4. Placeholder names are not people and get no donor page.
INSERT INTO qa_result
SELECT 'V4 no pages for placeholder names',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'ANONYMOUS / UNKNOWN / UNITEMIZED donors with a page'
FROM (SELECT count(*) AS n FROM site.donor
      WHERE kind = 'individual' AND has_page
        AND name ~* '(^|[ ,])(ANONYMOUS|UNKNOWN|UNITEMIZED|REQUESTED)([ ,]|$)') x;

-- V5. Every gift points at a donor and a candidate the site knows.
INSERT INTO qa_result
SELECT 'V5 gifts reference known donors and candidates',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'orphan gifts'
FROM (SELECT count(*) AS n FROM site.gift g
      LEFT JOIN site.donor d USING (donor_key) LEFT JOIN site.candidate c USING (cand_id, cycle)
      WHERE d.donor_key IS NULL OR c.cand_id IS NULL) x;

-- V6. Every candidate has a totals row (feeds the pie chart).
INSERT INTO qa_result
SELECT 'V6 every candidate has totals',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'candidates without site.cand_totals'
FROM (SELECT count(*) AS n FROM site.candidate c LEFT JOIN site.cand_totals t USING (cand_id, cycle)
      WHERE t.cand_id IS NULL) x;

-- V7. Freshness (warning only): the last month of the newest cycle that is
--     fully loaded, taken as having at least 40% of the cycle's busiest month
--     (late-filed months trickle in and would otherwise look current).
INSERT INTO qa_result
SELECT 'V7 Schedule A is recent',
       CASE WHEN current_date - last_dt <= :max_lag_days THEN 'PASS' ELSE 'WARN' END,
       current_date - last_dt, 'days since the last fully loaded month ended: ' || last_dt
FROM (SELECT max(d) FILTER (WHERE n >= 0.4 * busiest) AS last_dt FROM (
        SELECT (date_trunc('month', gift_date) + interval '1 month' - interval '1 day')::date AS d,
               count(*) AS n, max(count(*)) OVER () AS busiest
        FROM site.gift WHERE via = 'Contribution' AND cycle = (SELECT max(cycle) FROM site.gift)
        GROUP BY 1) m) x;

SELECT status, id, found, detail FROM qa_result ORDER BY id;
-- With ON_ERROR_STOP, the raised error makes psql exit with status 3.
SELECT count(*) > 0 AS failed FROM qa_result WHERE status = 'FAIL' \gset
\if :failed
  DO $$ BEGIN RAISE EXCEPTION 'data validation failed'; END $$;
\endif
\echo all checks passed

-- =============================================================================
-- sql/90_validate.sql
-- Project : Campaign Donations
-- Date    : 2026-10-29
-- Purpose : Data validation (QA). Checks the "site" schema for invariants that
--           should always hold, prints one PASS/FAIL/WARN line per check and
--           a last line "RESULT: PASS" or "RESULT: FAIL". Read-only.
-- Usage   : scripts/validate.sh  (exit 0 pass, 1 a check failed, 2 the checks
--           could not run), or directly:
--           psql -d fec -X -q -v max_gift=20000 -f sql/90_validate.sql
--           Optional: -v max_lag_days=120 (data freshness warning, default 120)
-- Notes   : Checks against the FEC's published per-candidate totals (FEC API)
--           are in docs/qa/; this file only uses tables already in the database.
-- Change log:
--   2026-10-29  0.1.0  Initial version (QA, Riker).
--   2026-10-29  0.1.0  Review fixes: V2 also checks candidates with no FEC
--                      summary; V3 uses the candidate flag and either sign;
--                      V4 normalised names; V5 and V6 test something that can
--                      fail; V7 reads site.meta; RESULT line in place of an
--                      error, so a SQL error is not mistaken for a data FAIL.
-- =============================================================================
\set ON_ERROR_STOP on
\if :{?max_lag_days}
\else
  \set max_lag_days 120
\endif
\if :{?max_gift}
\else
  \set max_gift 20000
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
--     A candidate with itemized money but no FEC summary row counts as zero.
INSERT INTO qa_result
SELECT 'V2 itemized <= FEC total individual',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n,
       'candidate-cycles above bulk.weball ttl_indiv_contrib (or with none)'
FROM (SELECT count(*) AS n FROM site.cand_totals t
      LEFT JOIN bulk.weball w ON w.cand_id = t.cand_id AND w.cycle = t.cycle
      WHERE t.individual > coalesce(w.ttl_indiv_contrib, 0) * 1.02 + 1000) x;

-- V3. No single individual gift (either sign) above max_gift unless the
--     candidate gave it. sql/20_site.sql leaves such rows out, so any found
--     here means that rule broke.
INSERT INTO qa_result
SELECT 'V3 no implausible individual gifts',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n,
       'individual gifts over $' || :max_gift || ' not from the candidate'
FROM (SELECT count(*) AS n FROM site.gift
      WHERE via = 'Contribution' AND abs(amount) > :max_gift AND NOT self_funded) x;

-- V3b. Warning: one donor's net individual money to one candidate in a cycle
--      above twice max_gift (several mid-sized errors, or one person split).
INSERT INTO qa_result
SELECT 'V3b no implausible donor totals',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'WARN' END, n,
       'donor-candidate-cycles over $' || 2 * :max_gift || ' not from the candidate'
FROM (SELECT count(*) AS n FROM (
        SELECT donor_key FROM site.gift WHERE via = 'Contribution' AND NOT self_funded
        GROUP BY donor_key, cand_id, cycle HAVING abs(sum(amount)) > 2 * :max_gift) d) x;

-- V4. Placeholder names are not people and get no donor page. Names are
--     normalised first, so "ANONYMOUS." and "UNKNOWN-DONOR" are caught too.
INSERT INTO qa_result
SELECT 'V4 no pages for placeholder names',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'ANONYMOUS / UNKNOWN / N/A donors with a page'
FROM (SELECT count(*) AS n FROM site.donor
      WHERE kind = 'individual' AND has_page
        AND (site.norm_name(name) ~ '\m(ANONYMOUS|UNKNOWN|UNITEMIZED|REQUESTED)\M'
             OR site.norm_name(name) IN ('', 'N A', 'NONE', 'NOT PROVIDED'))) x;

-- V5. Every donor page has a real name (not the internal key), and every gift
--     belongs to a donor the site knows.
INSERT INTO qa_result
SELECT 'V5 donor pages have names',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'FAIL' END, n, 'donor pages named by key, or orphan gifts'
FROM (SELECT (SELECT count(*) FROM site.donor
              WHERE has_page AND (name IS NULL OR name = donor_key OR btrim(name) = ''))
           + (SELECT count(*) FROM site.gift g
              WHERE NOT EXISTS (SELECT 1 FROM site.donor d WHERE d.donor_key = g.donor_key))
           AS n) x;

-- V6. Warning: a candidate the FEC shows with real individual money (over
--     $50,000) but who has no itemized gifts here. Usually a committee that is
--     not linked, or filings not in the dump yet.
INSERT INTO qa_result
SELECT 'V6 candidates with FEC money have gifts',
       CASE WHEN n = 0 THEN 'PASS' ELSE 'WARN' END, n,
       'candidate-cycles with FEC individual money but no itemized gifts'
FROM (SELECT count(*) AS n FROM site.cand_totals t
      JOIN bulk.weball w ON w.cand_id = t.cand_id AND w.cycle = t.cycle
      WHERE w.ttl_indiv_contrib > 50000 AND t.individual = 0) x;

-- V7. Freshness (warning only): the through-date the site shows (site.meta,
--     set by sql/20_site.sql) is at most max_lag_days old.
INSERT INTO qa_result
SELECT 'V7 Schedule A is recent',
       CASE WHEN current_date - d <= :max_lag_days THEN 'PASS' ELSE 'WARN' END,
       current_date - d, 'days since the data through-date ' || coalesce(d::text, '(none)')
FROM (SELECT (SELECT value::date FROM site.meta WHERE key = 'sched_a_through') AS d) x;

SELECT status, id, found, detail FROM qa_result ORDER BY id;
\pset tuples_only on
\pset format unaligned
SELECT 'RESULT: ' || CASE WHEN count(*) FILTER (WHERE status = 'FAIL') > 0
                          THEN 'FAIL' ELSE 'PASS' END
FROM qa_result;

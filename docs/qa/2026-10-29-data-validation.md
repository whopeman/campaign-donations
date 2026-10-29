<!--
  docs/qa/2026-10-29-data-validation.md
  Project : Campaign Donations
  Date    : 2026-10-29
  Purpose : QA run report: whole-system check and data validation of the
            build deployed on 2026-10-29 (commit 6e92908).
  Change log:
    2026-10-29  0.1.0  Created (QA, Riker).
    2026-10-29  0.1.0  Verdict lists #5 too (code review of PR #6).
-->

# QA run, 2026-10-29: system check and data validation

**Build:** `main` at 6e92908, deployed 2026-10-29. FEC data downloaded 2026-10-26/27.
**Verdict:** the code checks pass, but **the data does not meet the test plan's exit criteria**. Three high-severity data bugs are filed (#1, #2, #3), one medium (#4) and one low (#5). In recent cycles (2020, 2024) the totals match the FEC within 0.3%. In 2016 and 2018 Senate, and in individual records, they don't.

## Results

| Area | Result | Notes |
| --- | --- | --- |
| Unit and integration tests | PASS | 77 passed, 1 skipped |
| ruff, shellcheck | PASS | Clean |
| pip-audit | PASS | No known vulnerabilities |
| Link check (local build) | PASS | 0 broken among 3,678,322 internal links, 66,774 pages |
| Live site: pages, 404, HTTPS | PASS | 200 on sampled pages; 404 for missing pages; http → 301 https; folders return 403 |
| Live site: headers | PASS | CSP (`script-src 'none'`, `frame-ancestors 'none'`), nosniff, Referrer-Policy, Permissions-Policy. No HSTS (low; SecOps to decide) |
| FEC usage notice | PASS | Present on home, candidate and donor pages |
| Pages match the database | PASS | Rubio 2016 page: $14,390,957 individual and $6,050,199 opposed, same as `site.cand_totals` |
| V1 each Schedule A row counted once | **FAIL** | 97,440 rows ($62M in all), see #2 |
| V2 itemized ≤ FEC total individual | **FAIL** | 181 candidate-cycles, mostly 2016 and 2018 Senate, see #1 |
| V3 no implausible individual gifts | **FAIL** | 126 gifts, see #3 |
| V4 no placeholder donor pages | **FAIL** | 4 pages, see #5 |
| V5 orphan gifts | PASS | 0 |
| V6 candidates without totals | PASS | 0 |
| V7 data freshness | WARN | Last fully loaded month ends 2026-06-30 (121 days), see #4 |

## Reconciliation with the FEC

Source: FEC API `/v1/candidates/totals/` with `election_full=false`, top 100 candidates by receipts per cycle and office, pulled 2026-10-29. The comparison is itemized individual money, ours against `individual_itemized_contributions`.

| Cycle | Office | Ours $M | FEC $M | Ratio | Within 1% | Off by >5% |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2016 | House | 154.9 | 157.0 | 0.986 | 51 | 8 |
| 2016 | Senate | 394.0 | 351.0 | **1.122** | 21 | 59 |
| 2020 | House | 374.7 | 375.6 | 0.998 | 92 | 0 |
| 2020 | Senate | 1,031.4 | 1,028.9 | 1.002 | 81 | 1 |
| 2024 | House | 383.6 | 384.2 | 0.999 | 74 | 3 |
| 2024 | Senate | 696.4 | 698.3 | 0.997 | 81 | 1 |
| 2026 | Senate | 378.8 | 597.9 | **0.634** | — | 79 |

PAC and party money against the FEC's `other_political_committee_contributions` was within 3.3% in every cycle checked (ratio 0.993–1.033).

**The 2016 question from the deploy.** The 2016 individual total ($876M) is not too low. It is the sum of itemized gifts only, and the FEC's $1,074M total includes unitemized ones. The real problem runs the other way: 2016 Senate is about 12% *high*, because superseded reports are counted along with their amendments (#1).

**2026** is low because the FEC's Schedule A dump runs only through 2026-06-30. Q3 reports are not processed yet (#4).

## Root causes found

1. **Amended reports (#1).** Cruz 2016 has two Q3 reports. Keeping only the latest filing per committee and report brings Cruz from 5.1× to 1.001×, and Rubio from 1.44× to 1.003×. The rule needs refining for report types that can be filed more than once a year.
2. **One committee, two candidate IDs (#2).** `site.cand_cmte` keeps every P/A link, so the gift is counted once per candidate. The 2024 cycle alone has $34.2M counted twice.
3. **Bad source rows (#3).** One example is a $3,958,610 "individual" gift to a DC House candidate whose FEC itemized total is $1,576. Others are joint fundraising committees flagged as individuals.

## Not covered in this run

- 2018, 2022 and 2026 House were not reconciled against the FEC API. The demo key allows 10 calls an hour. A personal api.data.gov key would allow a full run.
- Independent expenditures were not reconciled against the FEC's Schedule E totals by candidate.
- Donor matching (name + 5-digit ZIP) was not measured for split or merged donors. Known limitation.

## How to repeat

```sh
# in WSL, from the repo
uv run pytest -q && uv run ruff check . && shellcheck scripts/*.sh
psql -d fec -X -q -f sql/90_validate.sql          # exit 3 on any FAIL
```

For the FEC reconciliation:
1. Fetch `/v1/candidates/totals/?cycle=<c>&office=<H|S>&election_full=false&sort=-receipts&per_page=100`.
2. Load `candidate_id, cycle, individual_itemized_contributions, other_political_committee_contributions` into a scratch table.
3. Join it to `site.cand_totals` on `(cand_id, cycle)`.

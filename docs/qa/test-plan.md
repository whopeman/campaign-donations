<!--
  docs/qa/test-plan.md
  Project : Campaign Donations
  Date    : 2026-10-29
  Purpose : QA test plan: what is tested, how, and what must pass before a
            release or a monthly deploy.
  Change log:
    2026-10-29  0.1.0  Created (QA, Riker).
    2026-10-29  0.1.0  Checks revised after code review of PR #6; scripts/validate.sh
                       exit codes; validate step in scripts/monthly.sh.
-->

# Test plan

Owner: QA (Riker). The plan covers the whole system:
- the FEC data load (`scripts/load.sh`, `sql/`);
- aggregation (`sql/20_site.sql`);
- the renderer (`src/cdpipe`, `templates/`);
- the deployed site at <https://hopemanhorde.com/campaign-donations/>.

## Levels

| Level | What | How | When |
| --- | --- | --- | --- |
| Unit (white box) | Charts, formats, flags, models, paths, Schedule A projector | `uv run pytest` (`tests/`) | Every commit |
| Lint / static | Python, shell | `ruff check`, `ruff format --check`, `shellcheck scripts/*.sh` | Every commit |
| Dependency audit | Known vulnerabilities, licences | `uv run pip-audit` | Every release |
| Integration | Database to renderer, and the site SQL plus validation on made-up FEC rows | `CD_TEST_DSN="dbname=fec" uv run pytest` runs `tests/test_db.py` and `tests/test_sql.py` (skipped without it) | Every commit, in WSL |
| Data validation | Invariants on the loaded `site` schema | `scripts/validate.sh` (exit 0 pass, 1 a check failed, 2 the checks could not run); `scripts/monthly.sh` runs it as the `validate` step, and `deploy` needs it | After every load |
| Reconciliation | Our totals against the FEC's published figures | FEC API `/v1/candidates/totals/` vs `site.cand_totals` (method in the latest report under `docs/qa/`) | Every release, and after load-logic changes |
| End to end | Built site: links, HTML, page counts, file-name inode cost | Link check over every page; `html-validate` sample (`scripts/monthly.sh check`); file and inode count | Every render |
| Acceptance (black box) | Live site: pages load, figures match the database, notices present | HTTP checks against the live site; compare sample pages with `site.cand_totals` | Every deploy |
| Security | Headers, HTTPS, no directory listing, no secrets | `curl -I`, 301 to HTTPS, 403 on folders, `git grep` for keys | Every deploy |

## Data validation checks (`sql/90_validate.sql`)

| ID | Invariant | Why it matters |
| --- | --- | --- |
| V1 | Each Schedule A row is counted once | A committee linked to two candidates double-counts |
| V2 | Itemized individual money is at most the FEC's total individual money for the candidate (`bulk.weball`); a candidate with no FEC summary row counts as zero | Catches double counting from amendments or links |
| V3 | No single individual gift (either sign) above `max_individual_gift_usd` unless the candidate gave it (`site.gift.self_funded`: entity type CAN, or the candidate's name) | Catches filer typos and mis-flagged committees published under private names |
| V3b | Warning: one donor's net individual money to one candidate in a cycle above twice that limit | Several mid-sized errors, or one person split across rows |
| V4 | No donor pages for placeholder names (ANONYMOUS, UNKNOWN, N/A, ...), matched on normalised names | They are not people |
| V5 | Every donor page has a real name (not its internal key), and every gift belongs to a known donor | A page titled with a key, or an orphan, is a broken page |
| V6 | Warning: no candidate with over $50,000 of FEC individual money and no itemized gifts | Usually an unlinked committee or filings not loaded yet |
| V7 | Warning: the through-date the site shows (`site.meta`) is within 120 days | Readers need to know how current the data is |

## Reconciliation tolerances

Our figure is *itemized* individual money only (Schedule A, $200 and over). It is compared with the FEC's `individual_itemized_contributions`, not its total, which also includes unitemized gifts.

| Measure | Pass |
| --- | --- |
| Sum over the top 100 candidates by receipts, per cycle and office | Ours / FEC between 0.98 and 1.02 |
| Single candidate | Within 5%, or explained in the report |
| PAC and party money vs FEC `other_political_committee_contributions` | Within 5% (ours also includes party committees) |
| Current cycle | Judged only up to the data through-date (V7) |

## Exit criteria for a deploy

1. Unit, lint and integration tests pass.
2. `scripts/validate.sh` exits 0. Warnings are allowed but must be reported.
3. The link check finds no broken internal links.
4. Reconciliation is within tolerance, or each exception has an open issue.
5. After upload:
   - Folders are 755 and files 644.
   - Sample pages return 200.
   - Security headers are present.

## Recording results

- Each run is written up as `docs/qa/<date>-<topic>.md`.
- Each bug is filed as a GitHub issue labelled `bug`, with evidence, repro steps and a definition of done.
- QA re-tests an issue when a developer marks it fixed and closes it only when the check passes.

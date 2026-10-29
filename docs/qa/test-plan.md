<!--
  docs/qa/test-plan.md
  Project : Campaign Donations
  Date    : 2026-10-29
  Purpose : QA test plan: what is tested, how, and what must pass before a
            release or a monthly deploy.
  Change log:
    2026-10-29  0.1.0  Created (QA, Riker).
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
| Integration | Database to renderer on a fixture database | `tests/test_db.py` (skipped when PostgreSQL is not reachable) | Every commit, in WSL |
| Data validation | Invariants on the loaded `site` schema | `psql -d fec -X -q -f sql/90_validate.sql` (exit 3 on failure) | After every load |
| Reconciliation | Our totals against the FEC's published figures | FEC API `/v1/candidates/totals/` vs `site.cand_totals` (method in the latest report under `docs/qa/`) | Every release, and after load-logic changes |
| End to end | Built site: links, HTML, page counts, file-name inode cost | Link check over every page; `html-validate` sample (`scripts/monthly.sh check`); file and inode count | Every render |
| Acceptance (black box) | Live site: pages load, figures match the database, notices present | HTTP checks against the live site; compare sample pages with `site.cand_totals` | Every deploy |
| Security | Headers, HTTPS, no directory listing, no secrets | `curl -I`, 301 to HTTPS, 403 on folders, `git grep` for keys | Every deploy |

## Data validation checks (`sql/90_validate.sql`)

| ID | Invariant | Why it matters |
| --- | --- | --- |
| V1 | Each Schedule A row is counted once | A committee linked to two candidates double-counts |
| V2 | Itemized individual money is at most the FEC's total individual money for the candidate (`bulk.weball`) | Catches double counting from amendments or links |
| V3 | No individual gift of $20,000 or more unless it comes from the candidate | Catches filer typos and mis-flagged committees published under private names |
| V4 | No donor pages for placeholder names (ANONYMOUS, UNKNOWN, ...) | They are not people |
| V5 | Every gift references a known donor and candidate | Orphans would break pages |
| V6 | Every candidate has a totals row | Pie charts need it |
| V7 | The newest fully loaded month is within 120 days (warning) | Readers need to know how current the data is |

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
2. `sql/90_validate.sql` exits 0. Warnings are allowed but must be reported.
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

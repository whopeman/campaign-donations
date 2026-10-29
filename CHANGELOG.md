<!--
  CHANGELOG.md
  Project : Campaign Donations
  Date    : 2026-10-26
  Purpose : Release history, following Keep a Changelog and SemVer.
  Change log:
    2026-10-26  0.1.0  Created.
-->

# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project scaffold from the HopemanHorde hosted-project template.
- Feature flags in `config/flags.toml` with `CD_*` environment overrides.
- Colour-blind-safe SVG pie and stacked bar charts (Okabe-Ito colours plus patterns).
- Clickable US state map built from Census cartographic boundary files.
- Static page renderer: home, state, candidate, donor and about pages.
- `cdpipe demo` command for checking layout with made-up data.
- `scripts/fetch.sh` to download FEC dumps and bulk files.
- Security headers via `.htaccess` and a Content-Security-Policy meta tag.
- Database load (`scripts/load.sh`, `sql/`) and streaming renderer from PostgreSQL.
- Parallel range downloader for the 91 GB Schedule A dump.
- Monthly update job (`scripts/monthly.sh`) with a systemd user timer.
- Schedule A restore runs per partition and resumes where it stopped.
- Schedule A is loaded narrow (17 of about 80 columns) through `cdpipe.narrow`,
  with a free-space check before each cycle and a watchdog during the load.
- Schedule A keeps only rows filed by House and Senate candidate committees
  (`cdpipe.narrow --where-in`).
- Short page file names (FEC IDs and 11-character donor codes) so each name is one
  GoDaddy inode; individuals need $15,000 in a cycle for a donor page.
- The site refuses to write two pages to one path.
- QA test plan (`docs/qa/test-plan.md`), data validation checks
  (`sql/90_validate.sql`) and the first validation report.
- `scripts/validate.sh`: runs the data checks with exit codes 0 (pass), 1 (a check
  failed) and 2 (the checks could not run). `scripts/monthly.sh` runs it as a
  `validate` step, and `deploy` waits for it.
- "Records left out" page listing excluded Schedule A records with their filings,
  and the `max_individual_gift_usd` flag (default 20,000).
- Every page says how current the itemized data is ("Itemized gifts are loaded
  through ...").

### Fixed

- Amended reports were counted together with the reports they replace (#1).
  Schedule A now keeps `file_num`, `rpt_tp` and `rpt_yr`, and a filing re-filed in
  full by a later one is dropped.
- A committee linked to two candidate IDs in one cycle counted every gift twice (#2).
- Implausible "individual" gifts (filer typos, committees flagged as individuals)
  were published under private names (#3). They are now left out of totals and
  donor pages.
- No page said how current the data is (#4).
- Placeholder names got donor pages, and undated rows could supply a donor's
  details (#5).
- Data checks (code review of PR #6): V2 skipped candidates with no FEC summary;
  V3 compared raw surnames and ignored negative amounts; V4 missed punctuated
  placeholders; V5 and V6 could never fail; V7 could read a cycle with no
  Schedule A rows; a SQL error looked like a data failure.
- About 60% of the "FEC" links on state pages, and the "source" links on candidate
  pages, opened an FEC 404 page: fec.gov rejects `?cycle=` for years in which it
  does not count the person as a candidate. The links now open the candidate's
  FEC overview without a cycle.
- A committee missing from both FEC committee lists got a donor page titled with
  the internal key (`c:C00607698`). It is now named "Committee C00607698" and links
  to its FEC page.

### Fixed

- Earmarked gifts passed through WinRed, ActBlue and PAC conduits were counted twice.
- Page titles are shortened to 70 characters.

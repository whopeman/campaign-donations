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

### Fixed

- Earmarked gifts passed through WinRed, ActBlue and PAC conduits were counted twice.
- Page titles are shortened to 70 characters.

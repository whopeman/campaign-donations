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

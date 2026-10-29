<!--
  README.md
  Project : Campaign Donations
  Date    : 2026-10-26
  Purpose : Overview, setup, build, test and deploy instructions.
  Change log:
    2026-10-26  0.1.0  Created from the Framework_Website_HopemanHorde template, then
                       rewritten for the FEC pipeline.
-->

# Campaign Donations

Donor tracking and aggregation for federal campaigns, built from public
Federal Election Commission (FEC) data. Live at
<https://hopemanhorde.com/campaign-donations/>.

The site is plain static HTML with no JavaScript:

- **Home**: a clickable map of the US states.
- **State pages**: House and Senate candidates per cycle, and the state's top donors.
- **Candidate pages**: party, a pie chart of money for and against them per cycle,
  then every donor and outside spender, each linked to the FEC filing.
- **Donor pages**: totals by party and cycle (for and against), then every gift,
  linked to the candidate page and the FEC filing.

Charts use colour **and** fill patterns, and list every value as text, so they
can be read without telling colours apart.

## How it works

| Step      | Where             | What                                                        |
| --------- | ----------------- | ----------------------------------------------------------- |
| Fetch     | WSL, `scripts/`   | Download FEC PostgreSQL dumps and bulk files to `~/fec-data` |
| Load      | WSL, PostgreSQL   | Restore dumps, load bulk files, build summary tables (`sql/`) |
| Aggregate | WSL, PostgreSQL   | Donor matching and totals (`sql/20_site.sql`)               |
| Render    | WSL, Python       | Jinja2 templates to static HTML in `site/`                   |
| Deploy    | Windows, PowerShell | Framework deploy script uploads `site/` over SFTP          |

## Layout

| Path              | What it holds                                         |
| ----------------- | ----------------------------------------------------- |
| `config/flags.toml` | Feature flags (GPU, cycles, donor page threshold)   |
| `src/cdpipe/`     | Python package: flags, charts, models, renderer, CLI  |
| `templates/`      | Jinja2 page templates                                 |
| `static/`         | CSS and `.htaccess` (security headers)                |
| `data/`           | State map paths built from Census boundaries          |
| `sql/`            | Database load and summary SQL                         |
| `scripts/`        | Fetch and load scripts (bash, run in WSL)             |
| `tools/`          | One-off Node build tools (state map)                  |
| `tests/`          | pytest suite                                          |

## Prerequisites

- WSL (Ubuntu) with PostgreSQL 16+ and a role for your user that can create databases.
- [uv](https://docs.astral.sh/uv/) in WSL for Python (3.12+).
- Node.js 20+ on Windows for HTML validation and the one-off map build.
- About 250 GB free on the Windows drive that holds the WSL disk, for the raw
  dumps and the database. The WSL disk grows into that drive, so the Windows free
  space is the real limit; set the distro to sparse
  (`wsl --manage <distro> --set-sparse true`) so freed space is returned.
  `scripts/load.sh` stops a Schedule A load when free space drops below
  `CD_MIN_FREE_GB` (default 40).
- Optional: an NVIDIA GPU with the WSL CUDA driver, for `use_gpu`.

## Setup and build

```sh
# WSL, in the repo folder
export UV_PROJECT_ENVIRONMENT=~/venvs/cd   # keep the venv off the Windows drive
uv sync
scripts/fetch.sh all                        # several hours the first time
uv run cdpipe demo                          # layout check with made-up data
uv run cdpipe build                         # the real site, from PostgreSQL
```

## Test and lint

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pip-audit
npm install && npm run lint:html            # Windows or WSL
```

## Feature flags

Set in `config/flags.toml`, or override per run with `CD_<NAME>`, for example
`CD_USE_GPU=false uv run cdpipe build`.

| Flag                       | Default            | Effect                                      |
| -------------------------- | ------------------ | ------------------------------------------- |
| `use_gpu`                  | `true`             | GPU entity matching (Phase 2; unused in 0.1) |
| `cycles`                   | 2016 to 2026       | Election cycles to publish                  |
| `donor_page_threshold_usd` | `15000`            | Individuals need this much in a cycle for a page |
| `offices`                  | `["H", "S"]`       | Offices to include                          |
| `county_view`              | `false`            | County breakdown on state pages (preview)   |

## Deploy

Copy `deploy.example.json` to `deploy.local.json` (gitignored) and set `user`
and `keyPath`. Then, from the `Framework_Website_HopemanHorde` repo:

```sh
npm run deploy -- -ConfigPath ../campaign-donations/deploy.local.json            # dry run
npm run deploy -- -ConfigPath ../campaign-donations/deploy.local.json -Execute   # upload
```

Uploads go only into `public_html/campaign-donations/`.

## Monthly updates

`scripts/monthly.sh` runs the whole update as separate, logged steps
(`fetch-bulk`, `fetch-dumps`, `load-bulk`, `load-dumps`, `site`, `render`,
`check`, `deploy`, `renew-limit`). A failed step skips only the steps that
depend on it. Logs go to `~/fec-data/monthly/<date>.log`. Any step can be run
alone, for example `scripts/monthly.sh render check`.

The new site is rendered to `~/site-out.new` and swapped in only when the
render succeeds; the previous build is kept as `~/site-out.old`. Upload only
happens when `CD_AUTO_DEPLOY=true`.

A systemd user timer runs it on the first Sunday of each month at 03:00, after
the FEC's Saturday refresh. Install it once in WSL:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/systemd/fec-monthly.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fec-monthly.timer
loginctl enable-linger "$USER"   # keep user timers running when logged out
```

## Data use

FEC data is public. Federal law (52 U.S.C. 30111(a)(4)) says the names and
addresses of individual contributors may not be sold or used for commercial
purposes, or to solicit contributions. Every page carries this notice.

## Contributing

Issues and comments are limited to collaborators.

## License

Code: [MIT](LICENSE). Map data: US Census Bureau (public domain) via
[us-atlas](https://github.com/topojson/us-atlas) (ISC).

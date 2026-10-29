#!/usr/bin/env bash
# =============================================================================
# scripts/validate.sh
# Project : Campaign Donations
# Date    : 2026-10-29
# Purpose : Run the data validation checks (sql/90_validate.sql) on the loaded
#           "site" schema and turn the result into an exit code a pipeline can
#           act on. A data failure and a broken validator get different codes.
# Usage   : (WSL) scripts/validate.sh
#           Env: FEC_DB (default fec), CD_MAX_INDIVIDUAL_GIFT_USD (default from
#           config/flags.toml), CD_MAX_LAG_DAYS (default 120).
# Exit    : 0 every check passed (warnings allowed), 1 a check failed,
#           2 the checks could not run (SQL error, missing table, no result).
# Change log:
#   2026-10-29  0.1.0  Initial version.
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DB="${FEC_DB:-fec}"
MAX_GIFT="${CD_MAX_INDIVIDUAL_GIFT_USD:-$(awk -F' *= *' \
  '/^max_individual_gift_usd/ {print $2}' "$HERE/config/flags.toml")}"

out="$(psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -v max_gift="${MAX_GIFT:-20000}" \
  -v max_lag_days="${CD_MAX_LAG_DAYS:-120}" -f "$HERE/sql/90_validate.sql" 2>&1)"
rc=$?
printf '%s\n' "$out"
if (( rc != 0 )); then
  echo "validate: the checks could not run (psql exit $rc)" >&2
  exit 2
fi
if grep -q '^RESULT: FAIL' <<< "$out"; then
  exit 1
fi
if ! grep -q '^RESULT: PASS' <<< "$out"; then
  echo "validate: no RESULT line in the output" >&2
  exit 2
fi
exit 0

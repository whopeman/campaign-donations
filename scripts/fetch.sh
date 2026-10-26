#!/usr/bin/env bash
# =============================================================================
# scripts/fetch.sh
# Project : Campaign Donations
# Date    : 2026-10-26
# Purpose : Download the public FEC data the site is built from into
#           $FEC_DATA (default ~/fec-data). Resumable; safe to re-run.
#           - PostgreSQL dumps: Schedule A, Schedule E, committee history
#           - Bulk files per cycle: candidates (cn), committees (cm),
#             candidate-committee links (ccl), committee-to-candidate (pas2)
# Usage   : (WSL) scripts/fetch.sh [dumps|bulk|all] [cycles...]
#           scripts/fetch.sh bulk 2024 2026
# Change log:
#   2026-10-26  0.1.0  Initial version.
# =============================================================================
set -euo pipefail

DATA="${FEC_DATA:-$HOME/fec-data}"
DUMPS="https://cg-519a459a-0ea3-42c2-b7bc-fa1143481f74.s3-us-gov-west-1.amazonaws.com/bulk-downloads/data-dump/schedules"
BULK="https://www.fec.gov/files/bulk-downloads"
DICT="$BULK/data_dictionaries"
what="${1:-all}"
shift || true
cycles=("$@")
[ ${#cycles[@]} -eq 0 ] && cycles=(2016 2018 2020 2022 2024 2026)

get() {  # get <url> <dest>
  echo "$(date -Is) get $1"
  curl -fsS -L -C - --retry 10 --retry-delay 30 -o "$2" "$1"
}

if [ "$what" = dumps ] || [ "$what" = all ]; then
  mkdir -p "$DATA/dump"
  for f in README.txt ofec_committee_history.dump fec_fitem_sched_e.dump fec_fitem_sched_a.dump; do
    get "$DUMPS/$f" "$DATA/dump/$f"
  done
fi

if [ "$what" = bulk ] || [ "$what" = all ]; then
  mkdir -p "$DATA/bulk/headers"
  for h in cn cm ccl pas2; do
    get "$DICT/${h}_header_file.csv" "$DATA/bulk/headers/$h.csv"
  done
  for cy in "${cycles[@]}"; do
    yy="${cy:2:2}"
    mkdir -p "$DATA/bulk/$cy"
    for h in cn cm ccl pas2; do
      # Bulk zips are replaced in place by the FEC, so always fetch fresh.
      rm -f "$DATA/bulk/$cy/$h$yy.zip"
      get "$BULK/$cy/$h$yy.zip" "$DATA/bulk/$cy/$h$yy.zip"
      rm -rf "$DATA/bulk/$cy/$h"
      python3 -m zipfile -e "$DATA/bulk/$cy/$h$yy.zip" "$DATA/bulk/$cy/$h"
    done
  done
fi
echo "$(date -Is) done"

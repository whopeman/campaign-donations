#!/usr/bin/env bash
# =============================================================================
# scripts/fetch.sh
# Project : Campaign Donations
# Date    : 2026-10-26
# Purpose : Download the public FEC data the site is built from into
#           $FEC_DATA (default ~/fec-data). Resumable; safe to re-run.
#           - PostgreSQL dumps: Schedule A, Schedule E, committee history
#           - Bulk files per cycle: candidates (cn), committees (cm),
#             candidate-committee links (ccl), committee-to-candidate (pas2),
#             candidate financial summaries (weball)
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
  curl -fsS -L -C - --retry 10 --retry-delay 30 --retry-all-errors -o "$2" "$1"
}

# Large dumps: resume until the local size matches the server's. If the FEC
# has replaced the file since we started (new ETag), start over.
get_big() {  # get_big <url> <dest>
  local url="$1" dest="$2" etag_file="$2.etag" head want etag tries=0
  head="$(curl -fsSI "$url")"
  want="$(awk 'tolower($1)=="content-length:" {print $2}' <<< "$head" | tr -d '\r')"
  etag="$(awk 'tolower($1)=="etag:" {print $2}' <<< "$head" | tr -d '\r')"
  if [ -f "$etag_file" ] && [ "$(cat "$etag_file")" != "$etag" ]; then
    echo "$(date -Is) $dest changed on the server; starting over"
    rm -f "$dest"
  fi
  echo "$etag" > "$etag_file"
  while [ "$(stat -c %s "$dest" 2>/dev/null || echo 0)" != "$want" ]; do
    tries=$((tries + 1))
    [ "$tries" -gt 50 ] && { echo "giving up on $url" >&2; return 1; }
    get "$url" "$dest" || sleep 30
  done
  echo "$(date -Is) complete $dest ($want bytes)"
}

if [ "$what" = dumps ] || [ "$what" = all ]; then
  mkdir -p "$DATA/dump"
  for f in README.txt ofec_committee_history.dump fec_fitem_sched_e.dump fec_fitem_sched_a.dump; do
    get_big "$DUMPS/$f" "$DATA/dump/$f"
  done
fi

if [ "$what" = bulk ] || [ "$what" = all ]; then
  mkdir -p "$DATA/bulk/headers"
  # Header files are for reference only (sql/10_bulk.sql defines the columns).
  for h in cn cm ccl pas2; do
    get "$DICT/${h}_header_file.csv" "$DATA/bulk/headers/$h.csv" || true
  done
  for cy in "${cycles[@]}"; do
    yy="${cy:2:2}"
    mkdir -p "$DATA/bulk/$cy"
    for h in cn cm ccl pas2 weball; do
      # Bulk zips are replaced in place by the FEC, so always fetch fresh.
      rm -f "$DATA/bulk/$cy/$h$yy.zip"
      get "$BULK/$cy/$h$yy.zip" "$DATA/bulk/$cy/$h$yy.zip"
      rm -rf "$DATA/bulk/$cy/$h"
      python3 -m zipfile -e "$DATA/bulk/$cy/$h$yy.zip" "$DATA/bulk/$cy/$h"
    done
  done
fi
echo "$(date -Is) done"

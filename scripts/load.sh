#!/usr/bin/env bash
# =============================================================================
# scripts/load.sh
# Project : Campaign Donations
# Date    : 2026-10-26
# Purpose : Load the downloaded FEC data into PostgreSQL (database $FEC_DB,
#           default "fec") and build the "site" schema the pages are made from.
#           Steps can be run on their own, so a monthly update can redo only
#           what changed.
# Usage   : (WSL) scripts/load.sh [init|dumps|bulk|site|all]
# Needs   : a PostgreSQL role for the current user with CREATEDB.
# Change log:
#   2026-10-26  0.1.0  Initial version.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${FEC_DATA:-$HOME/fec-data}"
DB="${FEC_DB:-fec}"
CYCLES="${CD_CYCLES:-2016,2018,2020,2022,2024,2026}"
OFFICES="${CD_OFFICES:-H,S}"
THRESHOLD="${CD_DONOR_PAGE_THRESHOLD_USD:-1000}"
JOBS="${JOBS:-4}"
step="${1:-all}"
log() { echo "$(date -Is) $*"; }
psql_db() { psql -X -q -v ON_ERROR_STOP=1 -d "$DB" "$@"; }

init() {
  log "init database $DB"
  psql -X -q -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$DB'" | grep -q 1 \
    || createdb "$DB"
  psql_db -c "CREATE SCHEMA IF NOT EXISTS disclosure;
              CREATE EXTENSION IF NOT EXISTS pg_trgm;
              CREATE EXTENSION IF NOT EXISTS btree_gin;"
}

# Restore one dump, keeping only the tables we use and skipping the FEC's
# indexes (we build our own, smaller ones in sql/20_site.sql).
restore() {  # restore <dump file> <table-name regex>
  local dump="$1" keep="$2" list
  list="$(mktemp)"
  pg_restore -l "$dump" \
    | grep -E '(TABLE|TABLE DATA|TABLE ATTACH) disclosure ' \
    | grep -E " ($keep) " > "$list"
  log "restore $(basename "$dump"): $(wc -l < "$list") items"
  psql_db -c "DROP TABLE IF EXISTS disclosure.$(basename "$dump" .dump) CASCADE"
  pg_restore --no-acl --no-owner --jobs="$JOBS" -d "$DB" -L "$list" "$dump"
  rm -f "$list"
}

dumps() {
  restore "$DATA/dump/ofec_committee_history.dump" 'ofec_committee_history'
  restore "$DATA/dump/fec_fitem_sched_e.dump" 'fec_fitem_sched_e'
  # Schedule A is partitioned by two-year period; keep only the cycles we publish.
  local parts="fec_fitem_sched_a"
  IFS=',' read -ra cy <<< "$CYCLES"
  for c in "${cy[@]}"; do parts="$parts|fec_fitem_sched_a_$((c - 1))_$c"; done
  restore "$DATA/dump/fec_fitem_sched_a.dump" "$parts"
  psql_db -c "ANALYZE disclosure.fec_fitem_sched_a"
}

bulk() {
  log "load bulk files"
  psql_db -f "$HERE/sql/10_bulk.sql"
  IFS=',' read -ra cy <<< "$CYCLES"
  for c in "${cy[@]}"; do
    for t in cn cm ccl pas2 weball; do
      f="$(ls "$DATA/bulk/$c/$t/"*.txt)"
      # Pipe-delimited with no quoting; \x01 never appears, so it disables quotes.
      psql_db -c "\\copy bulk.$t FROM PROGRAM 'sed \"s/^/$c|/\" $f' WITH (FORMAT csv, DELIMITER '|', QUOTE E'\\x01', ENCODING 'LATIN1')"
    done
  done
  psql_db -c "ANALYZE bulk.cn, bulk.cm, bulk.ccl, bulk.pas2, bulk.weball"
}

site() {
  log "build site schema"
  psql_db -v cycles="{$CYCLES}" -v offices="{$OFFICES}" -v threshold="$THRESHOLD" \
    -f "$HERE/sql/20_site.sql"
}

case "$step" in
  init) init ;;
  dumps) dumps ;;
  bulk) bulk ;;
  site) site ;;
  all) init; dumps; bulk; site ;;
  *) echo "usage: $0 [init|dumps|bulk|site|all]" >&2; exit 2 ;;
esac
log "done $step"

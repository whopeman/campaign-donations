#!/usr/bin/env bash
# =============================================================================
# scripts/load.sh
# Project : Campaign Donations
# Date    : 2026-10-26
# Purpose : Load the downloaded FEC data into PostgreSQL (database $FEC_DB,
#           default "fec") and build the "site" schema the pages are made from.
#           Steps can be run on their own, so a monthly update can redo only
#           what changed.
# Usage   : (WSL) scripts/load.sh [init|small|sched_a|bulk|site|all]
# Needs   : a PostgreSQL role for the current user with CREATEDB.
# Change log:
#   2026-10-26  0.1.0  Initial version.
#   2026-10-28  0.1.0  Schedule A loads per partition and resumes after an interruption.
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

small_dumps() {
  restore "$DATA/dump/ofec_committee_history.dump" 'ofec_committee_history'
  restore "$DATA/dump/fec_fitem_sched_e.dump" 'fec_fitem_sched_e'
}

sched_a() {
  # Schedule A is partitioned by two-year period; keep only the cycles we publish.
  # Its restore takes hours, so each partition is loaded on its own and marked
  # done; a rerun after an interruption loads only the unfinished partitions.
  # Markers live under the dump's ETag, so a new FEC dump starts afresh.
  local dump="$DATA/dump/fec_fitem_sched_a.dump" parts="fec_fitem_sched_a" toc tag state
  IFS=',' read -ra cy <<< "$CYCLES"
  for c in "${cy[@]}"; do parts="$parts|fec_fitem_sched_a_$((c - 1))_$c"; done
  tag="$(tr -dc '0-9a-f-' < "$dump.etag")"
  state="$DATA/state/sched_a/${tag:-no-etag}"
  toc="$(mktemp)"
  pg_restore -l "$dump" | grep -E " disclosure ($parts) " > "$toc"

  if [[ ! -e "$state/schema.done" ]]; then
    log "restore sched_a tables (new dump $tag)"
    rm -rf "$DATA/state/sched_a"
    mkdir -p "$state"
    psql_db -c "DROP TABLE IF EXISTS disclosure.fec_fitem_sched_a CASCADE"
    grep -E '; [0-9]+ [0-9]+ TABLE disclosure ' "$toc" > "$toc.schema"
    pg_restore --no-acl --no-owner -d "$DB" -L "$toc.schema" "$dump"
    touch "$state/schema.done"
  fi

  # One line per partition still to load, run JOBS at a time.
  grep -E 'TABLE DATA disclosure ' "$toc" | while read -r entry; do
    t="$(awk '{print $(NF-1)}' <<< "$entry")"
    [[ -e "$state/$t.done" ]] || echo "$t"
  done > "$toc.todo"
  log "sched_a partitions to load: $(tr '\n' ' ' < "$toc.todo")"
  export -f log psql_db
  export DB dump toc state
  # shellcheck disable=SC2016  # expanded by the inner bash
  xargs -r -P "$JOBS" -n 1 bash -c '
    set -euo pipefail
    t="$1"
    grep -E "TABLE DATA disclosure $t " "$toc" > "$toc.$t"
    log "load $t"
    psql_db -c "TRUNCATE ONLY disclosure.$t"
    pg_restore --no-acl --no-owner -d "$DB" -L "$toc.$t" "$dump"
    touch "$state/$t.done"
    log "loaded $t"
  ' _ < "$toc.todo"
  rm -f "$toc" "$toc".*
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
  small) small_dumps ;;
  sched_a) sched_a ;;
  bulk) bulk ;;
  site) site ;;
  all) init; small_dumps; sched_a; bulk; site ;;
  *) echo "usage: $0 [init|small|sched_a|bulk|site|all]" >&2; exit 2 ;;
esac
log "done $step"

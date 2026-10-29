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
#   2026-10-28  0.1.0  Schedule A keeps only the columns the site uses, and stops
#                      before a partition when free space is short.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${FEC_DATA:-$HOME/fec-data}"
DB="${FEC_DB:-fec}"
CYCLES="${CD_CYCLES:-2016,2018,2020,2022,2024,2026}"
OFFICES="${CD_OFFICES:-H,S}"
THRESHOLD="${CD_DONOR_PAGE_THRESHOLD_USD:-1000}"
JOBS="${JOBS:-3}"
PY="${CD_PYTHON:-$HOME/venvs/cd/bin/python}"
# Free space (GB) required before each Schedule A partition, both inside WSL
# and on the Windows drive that holds the WSL disk (it grows into it).
MIN_FREE_GB="${CD_MIN_FREE_GB:-40}"
# Schedule A columns the site (sql/20_site.sql) and later phases use.
SCHED_A_COLS="sub_id,cmte_id,two_year_transaction_period,entity_tp,is_individual,receipt_tp,\
memo_cd,contbr_nm,contbr_city,contbr_st,contbr_zip,contbr_employer,contbr_occupation,\
contb_receipt_dt,contb_receipt_amt,image_num,conduit_cmte_id"
step="${1:-all}"
log() { echo "$(date -Is) $*"; }
psql_db() { psql -X -q -v ON_ERROR_STOP=1 -d "$DB" "$@"; }

# Fail unless every given mount has at least MIN_FREE_GB free.
space_ok() {
  local m gb
  for m in "$@"; do
    [[ -d "$m" ]] || continue
    gb=$(( $(df -Pk "$m" | awk 'NR==2 {print $4}') / 1048576 ))
    if (( gb < MIN_FREE_GB )); then
      log "STOP: only ${gb} GB free on $m (need $MIN_FREE_GB)"
      return 1
    fi
  done
}

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
  # Schedule A is about 50 GB per cycle restored whole, so it is streamed out
  # of the dump and cut down to SCHED_A_COLS (cdpipe.narrow) into
  # disclosure.sched_a, one partition per cycle. Each partition is marked done
  # when loaded; a rerun loads only unfinished ones. Markers live under the
  # dump's ETag and the column list, so a new dump or new columns start afresh.
  # Only rows filed by House and Senate candidate committees are kept (the
  # site reads nothing else), so bulk must be loaded first.
  local dump="$DATA/dump/fec_fitem_sched_a.dump" tag state todo watch c
  tag="$(tr -dc '0-9a-f-' < "$dump.etag")"
  state="$DATA/state/sched_a/${tag:-no-etag}-$(md5sum <<< "$SCHED_A_COLS|cmte:$OFFICES" | cut -c1-8)"
  IFS=',' read -ra cy <<< "$CYCLES"

  if [[ ! -e "$state/schema.done" ]]; then
    log "create sched_a tables (dump $tag)"
    rm -rf "$DATA/state/sched_a"
    mkdir -p "$state"
    psql_db -c "DROP TABLE IF EXISTS disclosure.fec_fitem_sched_a CASCADE" \
            -c "DROP TABLE IF EXISTS disclosure.sched_a CASCADE"
    psql_db -f "$HERE/sql/15_sched_a.sql"
    touch "$state/schema.done"
  fi

  # Committees whose receipts we keep: House/Senate committees by type, plus any
  # committee linked to a House/Senate candidate.
  psql_db -At -v offices="{$OFFICES}" > "$state/cmte_ids.txt" <<'SQL'
SELECT cmte_id FROM bulk.cm WHERE cmte_tp = ANY (:'offices'::text[])
UNION
SELECT l.cmte_id FROM bulk.ccl l JOIN bulk.cn c USING (cand_id, cycle)
WHERE c.cand_office = ANY (:'offices'::text[]);
SQL
  log "sched_a committee filter: $(wc -l < "$state/cmte_ids.txt") committees"
  [[ -s "$state/cmte_ids.txt" ]] || { log "no committees: load bulk first"; return 1; }

  todo="$(mktemp)"
  for c in "${cy[@]}"; do
    psql_db -c "CREATE TABLE IF NOT EXISTS disclosure.sched_a_$c
                PARTITION OF disclosure.sched_a FOR VALUES IN ($c)"
    [[ -e "$state/$c.done" ]] || echo "$c"
  done > "$todo"
  log "sched_a cycles to load: $(tr '\n' ' ' < "$todo")"

  # Watchdog: stop the load if free space falls to half the start margin.
  (
    while sleep 60; do
      MIN_FREE_GB=$((MIN_FREE_GB / 2)) space_ok / /mnt/c \
        || { pkill -f "pg_restore -a -n disclosure -t fec_fitem_sched_a_" || true; break; }
    done
  ) &
  watch=$!

  export -f log psql_db space_ok
  export DB dump state PY HERE SCHED_A_COLS MIN_FREE_GB
  # shellcheck disable=SC2016  # expanded by the inner bash
  xargs -r -P "$JOBS" -n 1 bash -c '
    set -euo pipefail
    c="$1"
    space_ok / /mnt/c
    log "load sched_a $c"
    psql_db -c "TRUNCATE disclosure.sched_a_$c"
    pg_restore -a -n disclosure -t "fec_fitem_sched_a_$((c - 1))_$c" -f - "$dump" \
      | PYTHONPATH="$HERE/src" "$PY" -m cdpipe.narrow --cols "$SCHED_A_COLS" \
          --where-in "cmte_id=$state/cmte_ids.txt" \
      | psql_db -c "\\copy disclosure.sched_a_$c ($SCHED_A_COLS) FROM pstdin"
    touch "$state/$c.done"
    log "loaded sched_a $c"
  ' _ < "$todo" || { kill "$watch" 2>/dev/null; rm -f "$todo"; return 1; }
  kill "$watch" 2>/dev/null || true
  rm -f "$todo"
  psql_db -c "ANALYZE disclosure.sched_a"
  psql_db -Atc "SELECT c.relname || ': ' || pg_size_pretty(pg_total_relation_size(c.oid))
                FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
                WHERE i.inhparent = 'disclosure.sched_a'::regclass ORDER BY 1"
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
  all) init; small_dumps; bulk; sched_a; site ;;
  *) echo "usage: $0 [init|small|sched_a|bulk|site|all]" >&2; exit 2 ;;
esac
log "done $step"

#!/usr/bin/env bash
# =============================================================================
# scripts/monthly.sh
# Project : Campaign Donations
# Date    : 2026-10-27
# Purpose : Monthly update. Each step runs on its own and is logged; a failed
#           step stops only the steps that depend on it:
#             fetch-bulk -> load-bulk --------+
#             fetch-dumps --(+ load-bulk)-> load-dumps -> site -> render -> check -+-> deploy
#                                                         site -> validate --------+
#           (Schedule A is filtered by the committee list in the bulk files.)
#           validate runs the data checks (scripts/validate.sh); the site is
#           still rendered when it fails, for review, but not deployed.
#           Deploy runs only when CD_AUTO_DEPLOY=true (off by default).
# Usage   : (WSL) scripts/monthly.sh            # all steps
#           scripts/monthly.sh render check     # just these steps
# Logs    : ~/fec-data/monthly/<date>.log
# Change log:
#   2026-10-27  0.1.0  Initial version.
#   2026-10-28  0.1.0  load-dumps waits for load-bulk.
#   2026-10-29  0.1.0  validate step; deploy needs it (QA test plan exit criteria).
# =============================================================================
# Step functions are called through run(), which shellcheck cannot follow.
# shellcheck disable=SC2329
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${FEC_DATA:-$HOME/fec-data}"
OUT="${CD_SITE_OUT:-$HOME/site-out}"
UV="${UV:-$HOME/.local/bin/uv}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/venvs/cd}"
LOGDIR="$DATA/monthly"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/$(date +%F).log"
declare -A ok

run() {  # run <step> <command...>
  local step="$1"; shift
  echo "$(date -Is) START $step" >> "$LOG"
  if "$@" >> "$LOG" 2>&1; then
    ok[$step]=1; echo "$(date -Is) OK    $step" >> "$LOG"
  else
    ok[$step]=0; echo "$(date -Is) FAIL  $step" >> "$LOG"
  fi
}
needs() {
  local dep
  for dep in "$@"; do
    [ "${ok[$dep]:-1}" = 1 ] || { echo "$(date -Is) SKIP  (needs $dep)" >> "$LOG"; return 1; }
  done
}

render() {
  local tmp="$OUT.new"
  rm -rf "$tmp"
  (cd "$HERE" && "$UV" run -q cdpipe build --out "$tmp") || return 1
  rm -rf "$OUT.old"; [ -d "$OUT" ] && mv "$OUT" "$OUT.old"
  mv "$tmp" "$OUT"
}

check() {
  local pages
  pages="$(find "$OUT" -type f | wc -l)"
  echo "files: $pages"
  [ "$pages" -gt 1000 ] || { echo "too few pages"; return 1; }
  # Validate a sample of each page type (all 30,000+ would take hours).
  local sample
  sample="$(cd "$OUT" && { echo index.html about.html states/ny/index.html;
    find candidates -type f | shuf -n 20; find donors -type f | shuf -n 20; })"
  # Node runs on the Windows side (node.exe through WSL interop), and its file
  # globbing does not read \\wsl paths, so validate a copy on the Windows drive.
  local tmp="$HERE/.check-sample" f
  rm -rf "$tmp"
  for f in $sample; do mkdir -p "$tmp/$(dirname "$f")"; cp "$OUT/$f" "$tmp/$f"; done
  (cd "$HERE" && node.exe node_modules/html-validate/bin/html-validate.mjs ".check-sample/**/*.html")
  local rc=$?
  rm -rf "$tmp"
  return "$rc"
}

deploy() {
  [ "${CD_AUTO_DEPLOY:-false}" = true ] || { echo "auto deploy is off"; return 0; }
  local fw
  fw="$(wslpath -w "$HERE/../Framework_Website_HopemanHorde")"
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
    "Set-Location '$fw'; npm run deploy -- -ConfigPath ../campaign-donations/deploy.local.json -SkipChecks -Execute"
}

# GitHub only limits issues/comments to collaborators for up to 6 months, so
# renew the limit every month. The token never leaves this machine.
renew_limit() {
  local token_file="${CD_GITHUB_TOKEN_FILE:-$HERE/../.ssh/github_repo_token}"
  [ -f "$token_file" ] || { echo "no token file; skipping"; return 0; }
  curl -fsS -X PUT -H "Authorization: Bearer $(tr -d '\r\n' < "$token_file")" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/repos/whopeman/campaign-donations/interaction-limits \
    -d '{"limit":"collaborators_only","expiry":"six_months"}'
}

steps=("$@")
[ ${#steps[@]} -eq 0 ] && steps=(fetch-bulk fetch-dumps load-bulk load-dumps site validate render check deploy renew-limit)
for s in "${steps[@]}"; do
  case "$s" in
    fetch-bulk)  run "$s" bash "$HERE/scripts/fetch.sh" bulk ;;
    fetch-dumps) run "$s" bash "$HERE/scripts/fetch.sh" dumps ;;
    load-bulk)   needs fetch-bulk && run "$s" bash "$HERE/scripts/load.sh" bulk ;;
    load-dumps)  needs fetch-dumps load-bulk && run "$s" bash -c "'$HERE/scripts/load.sh' small && '$HERE/scripts/load.sh' sched_a" ;;
    site)        needs load-bulk load-dumps && run "$s" bash "$HERE/scripts/load.sh" site ;;
    validate)    needs site && run "$s" bash "$HERE/scripts/validate.sh" ;;
    render)      needs site && run "$s" render ;;
    check)       needs render && run "$s" check ;;
    deploy)      needs check validate && run "$s" deploy ;;
    renew-limit) run "$s" renew_limit ;;
    *) echo "unknown step $s" >&2; exit 2 ;;
  esac
done
grep -q "FAIL" "$LOG" && exit 1
exit 0

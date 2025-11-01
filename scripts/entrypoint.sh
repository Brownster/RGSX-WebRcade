#!/bin/bash
set -euo pipefail

log() {
  printf '[rgsx-entrypoint] %s\n' "$*" >&2
}

if [[ "${FEED_RUN_ON_START:-1}" != "0" ]]; then
  log "Running initial feed build..."
  if ! /opt/rgsx/run-feed.sh --once; then
    log "Initial feed build failed (continuing so cron can retry)."
  fi
fi

if command -v cron >/dev/null 2>&1; then
  log "Starting cron daemon."
  cron
else
  log "cron binary not found; feed updates will not be scheduled."
fi

log "Handing off to base image command."
exec "$@"

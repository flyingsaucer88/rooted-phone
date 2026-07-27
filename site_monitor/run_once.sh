#!/data/data/com.termux/files/usr/bin/bash
# Run one site-monitor crawl now (foreground). Intended to be run inside Termux.
# Usage: ./run_once.sh [extra args passed to run_site_monitor.py]
set -euo pipefail
cd "$(dirname "$0")"
OUTDIR="${SITE_MONITOR_OUTDIR:-$HOME/site_monitor_reports}"
mkdir -p "$OUTDIR"
exec python run_site_monitor.py \
  --config config/sites.yaml \
  --output-dir "$OUTDIR" \
  --open-report false \
  "$@"

#!/data/data/com.termux/files/usr/bin/bash
# View the latest site-monitor report on the phone.
# - opens report_latest.html via termux-open if available
# - otherwise prints report_latest.md to the terminal
set -euo pipefail
OUTDIR="${SITE_MONITOR_OUTDIR:-$HOME/site_monitor_reports}"
HTML="$OUTDIR/report_latest.html"
MD="$OUTDIR/report_latest.md"

if command -v termux-open >/dev/null 2>&1 && [ -f "$HTML" ]; then
  echo "Opening $HTML …"
  termux-open "$HTML" || true
fi
if [ -f "$MD" ]; then
  echo "----- report_latest.md -----"
  cat "$MD"
else
  echo "No report yet. Run ./run_once.sh first." >&2
  exit 1
fi

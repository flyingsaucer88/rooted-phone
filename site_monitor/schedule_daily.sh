#!/data/data/com.termux/files/usr/bin/bash
# Install (or show) the daily 10:00 AM crontab entry for the Ambimat site monitor.
# Run this INSIDE Termux. It does NOT install Termux:Boot (see README limitation:
# cron only runs while crond is alive; it does not auto-start after reboot).
#
# Usage:
#   ./schedule_daily.sh install   # add the 10 AM cron entry + start crond
#   ./schedule_daily.sh show      # print current crontab + crond status
#   ./schedule_daily.sh remove    # remove the entry (disable the daily job)
set -euo pipefail

HOME_DIR="/data/data/com.termux/files/home"
WRAPPER="$HOME_DIR/site_monitor/run_daily.sh"
CRON_LOG="$HOME_DIR/site_monitor_reports/cron.log"
CRON_LINE="0 10 * * * $WRAPPER >> $CRON_LOG 2>&1"
MARKER="# ambimat-site-monitor"

cmd="${1:-show}"

ensure_cronie() {
  if ! command -v crond >/dev/null 2>&1 || ! command -v crontab >/dev/null 2>&1; then
    echo "cronie not installed. Install with: pkg install -y cronie" >&2
    exit 1
  fi
}

case "$cmd" in
  install)
    ensure_cronie
    chmod +x "$WRAPPER"
    mkdir -p "$(dirname "$CRON_LOG")"
    # rebuild crontab without any previous entry for this job, then append ours
    current="$(crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "site_monitor/run_daily.sh" || true)"
    { printf '%s\n' "$current"; echo "$CRON_LINE $MARKER"; } | sed '/^$/d' | crontab -
    echo "Installed cron entry:"
    echo "  $CRON_LINE $MARKER"
    # start crond for this session if not running
    if ! pgrep -x crond >/dev/null 2>&1; then
      crond
      echo "Started crond for this session."
    else
      echo "crond already running."
    fi
    echo
    echo "NOTE: cron runs only while Termux + crond stay alive. It does NOT survive a reboot"
    echo "unless Termux:Boot is installed later (not done now, by policy)."
    ;;
  remove)
    ensure_cronie
    crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "site_monitor/run_daily.sh" | sed '/^$/d' | crontab - || true
    echo "Removed the daily site-monitor cron entry (if it existed)."
    echo "crond may still be running; stop it with: pkill crond"
    ;;
  show|*)
    echo "=== crontab -l ==="
    crontab -l 2>/dev/null || echo "(empty or no crontab)"
    echo "=== crond process ==="
    pgrep -x crond >/dev/null 2>&1 && echo "crond RUNNING" || echo "crond NOT running"
    ;;
esac

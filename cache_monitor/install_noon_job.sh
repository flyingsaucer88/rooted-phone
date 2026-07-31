#!/data/data/com.termux/files/usr/bin/bash
# Install / show / remove ONLY the 12:00 IST cache-monitor cron line.
#
# Deliberately narrow: it touches exactly one crontab line, tagged
# "# ambimat-cache-monitor". Every other crontab line — including the 10:00
# site-monitor, the 11:00 SEO job and the */30 watchdog — is passed through
# untouched. Removing this line disables the noon job and nothing else.
#
# Reboot persistence needs no change here: Termux:Boot already runs
# ensure_scheduler.sh, whose catch-up block covers this job.
set -euo pipefail

HOME_DIR="${AMBIMAT_HOME:-/data/data/com.termux/files/home}"
CM="${CACHE_MONITOR_HOME:-$HOME_DIR/cache_monitor}"
REPORTS="$HOME_DIR/cache_monitor_reports"
LOGDIR="$HOME_DIR/ambimat_job_logs"
MARKER="# ambimat-cache-monitor"
CRON_LINE="0 12 * * * $CM/run_cache_monitor_daily.sh >> $REPORTS/cron.log 2>&1 $MARKER"

cmd="${1:-show}"

ensure_cronie() {
  if ! command -v crond >/dev/null 2>&1 || ! command -v crontab >/dev/null 2>&1; then
    echo "cronie not installed. Install with: pkg install -y cronie" >&2
    exit 1
  fi
}

_strip_ours() { crontab -l 2>/dev/null | grep -v 'ambimat-cache-monitor' | grep -v 'run_cache_monitor_daily.sh' || true; }

case "$cmd" in
  install)
    ensure_cronie
    chmod +x "$CM/run_cache_monitor_daily.sh"
    mkdir -p "$REPORTS" "$LOGDIR"
    chmod 700 "$REPORTS"
    current="$(_strip_ours)"
    { printf '%s\n' "$current"; echo "$CRON_LINE"; } | sed '/^$/d' | crontab -
    echo "Installed noon cron entry:"
    echo "  $CRON_LINE"
    if ! pgrep -x crond >/dev/null 2>&1; then crond && echo "Started crond."; else echo "crond already running."; fi
    ;;
  remove)
    ensure_cronie
    _strip_ours | sed '/^$/d' | crontab -
    echo "Removed the 12:00 cache-monitor cron entry. The 10:00, 11:00 and watchdog lines are untouched."
    echo "Also remove the watchdog catch-up by deleting the front_page_cache block in"
    echo "  $HOME_DIR/seo_tracker/phone/ensure_scheduler.sh"
    ;;
  show|*)
    echo "=== crontab -l ==="
    crontab -l 2>/dev/null || echo "(empty or no crontab)"
    echo "=== crond ==="
    pgrep -x crond >/dev/null 2>&1 && echo "crond RUNNING" || echo "crond NOT running"
    echo "=== last completed inspection (Asia/Kolkata date) ==="
    cat "$LOGDIR/front_page_cache_last_success_date" 2>/dev/null || echo "(never)"
    ;;
esac

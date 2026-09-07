#!/data/data/com.termux/files/usr/bin/bash
# Self-healing scheduler watchdog. Runs from cron every 30 min, at boot, and on
# demand. Each invocation:
#   1. single-flights (won't stack)
#   2. (Termux) holds a wake-lock so Android is less likely to kill Termux/crond
#   3. (Termux) restarts crond if it died, and reinstalls crontab lines if missing
#   4. catches up the 10:00 site-monitor and 11:00 SEO jobs if they're due & unrun
#
# This is what makes the schedule survive Termux being killed WITHOUT a reboot:
# as long as any watchdog tick runs (cron while alive, or boot), crond is revived.
#
# Flags/env: AMBIMAT_DRYRUN=1 → report what it would do without running jobs.
DIR="$(cd "$(dirname "$0")" && pwd)"
. "$DIR/lib_common.sh"

[ "${1:-}" = "--dry-run" ] && export AMBIMAT_DRYRUN=1
WLOG="$AMBIMAT_LOGDIR/scheduler_watchdog.log"

# 1. single-flight (short stale window — ticks are frequent)
if ! amb_acquire_lock watchdog 25; then
  amb_log "$WLOG" "watchdog: another instance active; exit"
  exit 0
fi
trap 'amb_release_lock watchdog' EXIT

# 2. keep Termux alive (best-effort; kept held, not released)
amb_wake_lock "$WLOG"

# 3. crond + crontab self-heal (Termux only; skipped where crond absent, e.g. CI)
if command -v crond >/dev/null 2>&1; then
  if ! pgrep -x crond >/dev/null 2>&1; then
    if crond 2>/dev/null; then amb_log "$WLOG" "crond was DEAD — restarted"; else amb_log "$WLOG" "crond restart FAILED"; fi
  fi
  if command -v crontab >/dev/null 2>&1; then
    have="$(crontab -l 2>/dev/null)"
    if ! printf '%s\n' "$have" | grep -q 'ambimat-seo-tracker' \
       || ! printf '%s\n' "$have" | grep -q 'ambimat-site-monitor' \
       || ! printf '%s\n' "$have" | grep -q 'ambimat-scheduler-watchdog'; then
      amb_log "$WLOG" "crontab missing required line(s) — reinstalling"
      bash "$DIR/schedule_daily.sh" install >> "$WLOG" 2>&1
    fi
  fi
else
  amb_log "$WLOG" "crond not found — crontab self-heal skipped (non-Termux host?)"
fi

# 4. catch up due jobs — site (10:00) before SEO (11:00) so heavy runs stagger.
SITE_RUNNER="${AMBIMAT_SITE_RUNNER_CMD:-$DIR/run_site_monitor_daily.sh}"
SEO_RUNNER="${AMBIMAT_SEO_RUNNER_CMD:-$DIR/run_daily.sh}"
amb_run_if_due site_monitor 0800 "$SITE_RUNNER" "$WLOG"
amb_run_if_due seo          0900 "$SEO_RUNNER"  "$WLOG"

# --- ambimat-cache-monitor: 12:00 catch-up (added 2026-07-31) ------------------
#
# This is the EXACT block appended to ~/seo_tracker/phone/ensure_scheduler.sh, kept
# here as the versioned copy of that edit. It is additive: it changes nothing about
# the 10:00 site-monitor or the 11:00 SEO job, which run above it unchanged.
#
# amb_run_if_due already provides everything the noon job needs:
#   - runs at most once per Asia/Kolkata day (the front_page_cache marker)
#   - never runs before 12:00 local
#   - defers while the network is down
#   - after a reboot at any time past noon, the watchdog's next tick (or the
#     Termux:Boot startup call) runs it exactly once — and only for today, never
#     replaying missed historical dates
#
# The runner it calls is inspect-and-report only. This block adds no capability.
CACHE_HOME="${AMBIMAT_CACHE_HOME:-$AMBIMAT_HOME/cache_monitor}"
CACHE_RUNNER="${AMBIMAT_CACHE_RUNNER_CMD:-$CACHE_HOME/run_cache_monitor_daily.sh}"
if [ -x "$CACHE_RUNNER" ]; then
  # Self-heal the noon crontab line the same way the three existing lines are healed.
  if command -v crontab >/dev/null 2>&1; then
    if ! crontab -l 2>/dev/null | grep -q 'ambimat-cache-monitor'; then
      amb_log "$WLOG" "crontab missing the 12:00 cache-monitor line — reinstalling"
      bash "$CACHE_HOME/install_noon_job.sh" install >> "$WLOG" 2>&1
    fi
  fi
  amb_run_if_due front_page_cache 1000 "$CACHE_RUNNER" "$WLOG"
else
  amb_log "$WLOG" "front_page_cache: runner not installed at $CACHE_RUNNER; skipping"
fi


exit 0

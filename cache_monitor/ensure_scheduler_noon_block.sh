#!/data/data/com.termux/files/usr/bin/bash
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
  amb_run_if_due front_page_cache 1200 "$CACHE_RUNNER" "$WLOG"
else
  amb_log "$WLOG" "front_page_cache: runner not installed at $CACHE_RUNNER; skipping"
fi

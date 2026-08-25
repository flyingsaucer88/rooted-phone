# --- ambimat-measurement-queue: one-shot dated jobs (added 2026-08-25) --------
#
# Versioned copy of the block appended to ~/seo_tracker/phone/ensure_scheduler.sh.
# Purely additive: the 10:00 site-monitor, 11:00 SEO and 12:00 cache-monitor
# blocks above are untouched, and this runs only after them so the daily jobs
# always win the locks (master prompt §23).
#
# The queue runner does its own date/blackout/dependency/idempotency gating, so
# the watchdog just ticks it every 30 minutes.
MQ_HOME="${AMBIMAT_MEASURE_HOME:-$AMBIMAT_HOME/measurement_queue}"
MQ_RUNNER="${AMBIMAT_MEASURE_RUNNER_CMD:-$MQ_HOME/run_measurement_queue.sh}"
if [ -x "$MQ_RUNNER" ]; then
  bash "$MQ_RUNNER" >> "$AMBIMAT_LOGDIR/measurement_queue.log" 2>&1 || \
    amb_log "$WLOG" "measurement_queue: runner exited non-zero (see measurement_queue.log)"
else
  amb_log "$WLOG" "measurement_queue: runner not installed at $MQ_RUNNER; skipping"
fi

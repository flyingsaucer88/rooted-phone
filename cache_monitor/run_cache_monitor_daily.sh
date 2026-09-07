#!/data/data/com.termux/files/usr/bin/bash
# 10:00 IST ambimat.com front-page cache inspection — INSPECT AND REPORT ONLY.
#
# Invoked by the 10:00 cron line (# ambimat-cache-monitor) and by the existing
# scheduler watchdog / Termux:Boot catch-up path. It observes; it never repairs.
# There is no flag, environment variable or code path in this file or in
# front_page_cache_monitor.py that changes anything on the server.
#
# Behaviour, matching the conventions already used by the 08:00 and 09:00 jobs:
#   - defers (exit 0, no marker) when the network is down, so the watchdog retries
#   - defers (exit 0, no marker) while the 08:00 or 09:00 job still holds its lock
#   - takes its own dedicated non-blocking lock so two inspections cannot overlap
#   - skips when today's inspection already completed (Asia/Kolkata date marker)
#   - writes the success marker for any CONCLUSIVE inspection, including a stale ALERT:
#     a stale finding is a completed inspection, not a failed scheduling run
#
# Env (for tests): AMBIMAT_HOME, AMBIMAT_LIB, CACHE_MONITOR_DIR, CACHE_MONITOR_REPORTS,
#                  CACHE_MONITOR_RUN_KIND, CACHE_MONITOR_PY, AMBIMAT_NET_CMD.

PREFIX="/data/data/com.termux/files/usr"
export PATH="$PREFIX/bin:$PREFIX/bin/applets:${PATH}:/system/bin:/system/xbin"
: "${TZ:=Asia/Kolkata}"; export TZ
export LANG="${LANG:-en_US.UTF-8}"

JOB="front_page_cache"
DUE_HM="1000"   # 10:00 IST (was 12:00 until 2026-09-07)

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
: "${AMBIMAT_HOME:=/data/data/com.termux/files/home}"
export AMBIMAT_HOME
export HOME="$AMBIMAT_HOME"
: "${AMBIMAT_LIB:=$AMBIMAT_HOME/seo_tracker/phone/lib_common.sh}"
: "${CACHE_MONITOR_DIR:=$SELF_DIR}"
: "${CACHE_MONITOR_REPORTS:=$AMBIMAT_HOME/cache_monitor_reports}"
: "${CACHE_MONITOR_RUN_KIND:=scheduled}"
: "${CACHE_MONITOR_PY:=python}"

# ---------------------------------------------------------------------------
# Shared scheduler helpers. The existing lib_common.sh IS the scheduler
# architecture; it is reused unchanged. The fallbacks below exist only so this
# script is testable on a host that has no phone tree.
# ---------------------------------------------------------------------------
if [ -f "$AMBIMAT_LIB" ]; then
  # shellcheck disable=SC1090
  . "$AMBIMAT_LIB"
else
  : "${AMBIMAT_LOGDIR:=$AMBIMAT_HOME/ambimat_job_logs}"
  mkdir -p "$AMBIMAT_LOGDIR" 2>/dev/null || true
  amb_now_date() { echo "${AMBIMAT_NOW_DATE:-$(date +%Y-%m-%d)}"; }
  amb_log() { local f="$1"; shift; case "$f" in /*) : ;; *) f="$AMBIMAT_LOGDIR/$f" ;; esac
              echo "$(date '+%F %T %z') $*" >> "$f" 2>/dev/null || true; }
  amb_marker_file() { echo "$AMBIMAT_LOGDIR/${1}_last_success_date"; }
  amb_marker_is_today() { [ "$(cat "$(amb_marker_file "$1")" 2>/dev/null)" = "$(amb_now_date)" ]; }
  amb_set_marker() { amb_now_date > "$(amb_marker_file "$1")" 2>/dev/null || true; }
  amb_acquire_lock() {
    local name="$1" stale="${2:-120}" d="$AMBIMAT_LOGDIR/.${name}.lock" pid fresh=1
    if mkdir "$d" 2>/dev/null; then echo "$$" > "$d/pid"; return 0; fi
    pid="$(cat "$d/pid" 2>/dev/null)"
    [ -n "$(find "$d" -maxdepth 0 -mmin +"$stale" 2>/dev/null)" ] && fresh=0
    if [ "$fresh" = 1 ] && [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then return 1; fi
    rm -rf "$d" 2>/dev/null; mkdir "$d" 2>/dev/null && { echo "$$" > "$d/pid"; return 0; }
    return 1
  }
  amb_release_lock() { rm -rf "$AMBIMAT_LOGDIR/.${1}.lock" 2>/dev/null || true; }
  amb_network_ready() {
    if [ -n "${AMBIMAT_NET_CMD:-}" ]; then eval "$AMBIMAT_NET_CMD"; return $?; fi
    return 0
  }
fi

LOG="$AMBIMAT_LOGDIR/cache_monitor_daily.log"
mkdir -p "$CACHE_MONITOR_REPORTS" 2>/dev/null || true
chmod 700 "$CACHE_MONITOR_REPORTS" 2>/dev/null || true

notify() {  # notify <content>
  command -v termux-notification >/dev/null 2>&1 || return 0
  termux-notification --id ambimat_cache_monitor \
    --title "$1" --content "$2" >/dev/null 2>&1 </dev/null || true
}

# --- 1. duplicate suppression (Asia/Kolkata date) --------------------------
MARKER_BEFORE="$(cat "$(amb_marker_file "$JOB")" 2>/dev/null || echo none)"
if amb_marker_is_today "$JOB"; then
  amb_log "$LOG" "cache_monitor: SKIPPED_ALREADY_COMPLETED for $(amb_now_date)"
  exit 0
fi

# --- 2. network gate (defer, do not mark) ----------------------------------
if ! amb_network_ready; then
  amb_log "$LOG" "cache_monitor: network unavailable; deferring (no marker, watchdog retries)"
  exit 0
fi

# --- 3. global maintenance lock: never collide with the 08:00 / 09:00 work --
MAINT="clear"
for other in site_run seo_run; do
  d="$AMBIMAT_LOGDIR/.${other}.lock"
  if [ -d "$d" ]; then
    opid="$(cat "$d/pid" 2>/dev/null)"
    if [ -n "$opid" ] && kill -0 "$opid" 2>/dev/null; then MAINT="held_by_$other"; break; fi
  fi
done
if [ "$MAINT" != "clear" ]; then
  amb_log "$LOG" "cache_monitor: DEFERRED_MAINTENANCE_LOCK ($MAINT); no inspection, no marker"
  exit 0
fi

# --- 4. dedicated non-blocking lock ----------------------------------------
if ! amb_acquire_lock cache_monitor_run 60; then
  amb_log "$LOG" "cache_monitor: own lock held by a live run; skipping this invocation"
  exit 0
fi
trap 'amb_release_lock cache_monitor_run' EXIT

# --- 5. the inspection ------------------------------------------------------
EV_DIR="$CACHE_MONITOR_REPORTS/noon-cache-inspection-$(date -u '+%Y%m%dT%H%M%SZ')"
amb_log "$LOG" "cache_monitor: start (kind=$CACHE_MONITOR_RUN_KIND, evidence=$EV_DIR)"

"$CACHE_MONITOR_PY" "$CACHE_MONITOR_DIR/front_page_cache_monitor.py" \
  --config "$CACHE_MONITOR_DIR/config/expected_metadata.json" \
  --server-config "$CACHE_MONITOR_DIR/config/server_inspection.json" \
  --evidence-dir "$EV_DIR" \
  --run-kind "$CACHE_MONITOR_RUN_KIND" \
  --lock-result "acquired:cache_monitor_run" \
  --maintenance-lock "$MAINT" \
  --marker-date-before "$MARKER_BEFORE" \
  >> "$LOG" 2>&1
rc=$?

RESULT_JSON="$EV_DIR/result.json"
_field() {  # _field <json key> <fallback>
  "$CACHE_MONITOR_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
    "$RESULT_JSON" "$1" 2>/dev/null || echo "$2"
}
CLASS="$(_field classification ERROR_MONITOR_INTERNAL)"
CONCLUSIVE="$(_field conclusive_inspection False)"
STALE="$(_field stale_or_obsolete_detected False)"
NOTE="$(cat "$EV_DIR/notification.txt" 2>/dev/null || echo "cache inspection finished (rc=$rc) — see $EV_DIR")"

amb_log "$LOG" "cache_monitor: end rc=$rc classification=$CLASS conclusive=$CONCLUSIVE stale=$STALE"

# --- 6. duplicate-suppression marker ---------------------------------------
# Set for ANY conclusive public observation (healthy, warning, stale ALERT, mismatch,
# blocked-server). This is what stops the catch-up system re-inspecting the same stale
# page all afternoon. NOT set for FAIL_PUBLIC_REQUEST or ERROR_MONITOR_INTERNAL.
if [ "$CONCLUSIVE" = "True" ]; then
  amb_set_marker "$JOB"
  amb_log "$LOG" "cache_monitor: inspection recorded as completed for $(amb_now_date) ($CLASS)"
fi

# --- 7. notification --------------------------------------------------------
if [ "$STALE" = "True" ]; then
  notify "!! Ambimat cache ALERT — manual review required" "$NOTE"
else
  notify "Ambimat front-page cache" "$NOTE"
fi

# A stale ALERT is a finding, not a job failure: exit 0 so the watchdog does not retry.
if [ "$CONCLUSIVE" = "True" ]; then
  exit 0
fi
exit "$rc"

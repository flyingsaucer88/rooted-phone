#!/data/data/com.termux/files/usr/bin/bash
# Shared helpers for the Ambimat phone scheduler. SOURCE this file; don't exec.
#
# Everything is env-overridable so the scripts can be unit-tested on any machine
# (point AMBIMAT_HOME at a temp dir, inject AMBIMAT_NOW_*/AMBIMAT_NET_CMD). On the
# phone the defaults resolve to the real Termux paths.
#
# Design goals: idempotent, safe under repeated/concurrent invocation, never
# marks success on failure/offline, cleans stale locks, logs everything.

# --- configuration (all overridable) ---------------------------------------
: "${AMBIMAT_HOME:=/data/data/com.termux/files/home}"
: "${AMBIMAT_REPO:=$AMBIMAT_HOME/seo_tracker}"
: "${AMBIMAT_LOGDIR:=$AMBIMAT_HOME/ambimat_job_logs}"
: "${AMBIMAT_SEO_REPORTS:=$AMBIMAT_HOME/seo_tracker_reports}"
: "${AMBIMAT_SITE_REPORTS:=$AMBIMAT_HOME/site_monitor_reports}"
: "${AMBIMAT_SITE_REPO:=$AMBIMAT_HOME/site_monitor}"
: "${AMBIMAT_DRYRUN:=0}"

# Keep a Termux-friendly PATH without breaking non-Termux (test) hosts: the
# Termux dirs simply don't exist elsewhere, and the existing PATH is preserved.
export PATH="/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/bin/applets:${PATH}:/system/bin:/system/xbin"
export HOME="$AMBIMAT_HOME"
: "${TZ:=Asia/Kolkata}"; export TZ   # explicit IST (req: never depend on ambiguous default/UTC)

mkdir -p "$AMBIMAT_LOGDIR" 2>/dev/null || true

# --- time (overridable for tests) ------------------------------------------
amb_now_hm()   { echo "${AMBIMAT_NOW_HM:-$(date +%H%M)}"; }
amb_now_date() { echo "${AMBIMAT_NOW_DATE:-$(date +%Y-%m-%d)}"; }

# --- logging ---------------------------------------------------------------
amb_log() {  # amb_log <logfile|path> <message...>
  local f="$1"; shift
  case "$f" in /*) : ;; *) f="$AMBIMAT_LOGDIR/$f" ;; esac
  echo "$(date '+%F %T %z') $*" >> "$f" 2>/dev/null || true
}

# --- success markers (per job) ---------------------------------------------
# job is "seo" or "site_monitor"
amb_marker_file()    { echo "$AMBIMAT_LOGDIR/${1}_last_success_date"; }
amb_marker_is_today(){ [ "$(cat "$(amb_marker_file "$1")" 2>/dev/null)" = "$(amb_now_date)" ]; }
amb_set_marker()     { amb_now_date > "$(amb_marker_file "$1")" 2>/dev/null || true; }

# --- locking (dir-based, atomic) with stale recovery -----------------------
# amb_acquire_lock <name> [stale_minutes]  -> 0 acquired, 1 busy
amb_acquire_lock() {
  local name="$1" stale="${2:-120}" d
  d="$AMBIMAT_LOGDIR/.${name}.lock"
  if mkdir "$d" 2>/dev/null; then echo "$$" > "$d/pid" 2>/dev/null; return 0; fi
  # Lock exists — is it live and fresh?
  local pid; pid="$(cat "$d/pid" 2>/dev/null)"
  local fresh=1
  [ -n "$(find "$d" -maxdepth 0 -mmin +"$stale" 2>/dev/null)" ] && fresh=0
  if [ "$fresh" = 1 ] && [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    return 1   # held by a live, recent process
  fi
  # Stale (old, or owner dead/unknown) — reclaim.
  rm -rf "$d" 2>/dev/null
  if mkdir "$d" 2>/dev/null; then echo "$$" > "$d/pid" 2>/dev/null; return 0; fi
  return 1
}
amb_release_lock() { rm -rf "$AMBIMAT_LOGDIR/.${1}.lock" 2>/dev/null || true; }

# --- network readiness ------------------------------------------------------
# Override with AMBIMAT_NET_CMD (e.g. "true"/"false") for tests.
amb_network_ready() {
  if [ -n "${AMBIMAT_NET_CMD:-}" ]; then eval "$AMBIMAT_NET_CMD"; return $?; fi
  bash "$AMBIMAT_REPO/phone/network_ready.sh" >/dev/null 2>&1
}

# --- best-effort wake lock (never fails the caller) ------------------------
amb_wake_lock() {
  if command -v termux-wake-lock >/dev/null 2>&1; then
    if termux-wake-lock 2>/dev/null; then amb_log "$1" "wake-lock acquired"; else amb_log "$1" "wake-lock present/failed (continuing)"; fi
  else
    amb_log "$1" "termux-wake-lock unavailable; skipped"
  fi
}

# --- the core due-check -----------------------------------------------------
# amb_run_if_due <job> <due_hm> <runner_script> <logfile>
# Runs the (self-locking, self-marking) runner exactly once if: not already
# done today, current time >= due, and network is up. Logs the reason otherwise.
amb_run_if_due() {
  local job="$1" due="$2" runner="$3" logf="$4"
  if amb_marker_is_today "$job"; then
    amb_log "$logf" "$job: already succeeded today ($(amb_now_date)); skip"; return 0
  fi
  local now_i due_i; now_i=$((10#$(amb_now_hm))); due_i=$((10#$due))
  if [ "$now_i" -lt "$due_i" ]; then
    amb_log "$logf" "$job: before due time (now=$(amb_now_hm) < $due); skip"; return 0
  fi
  if ! amb_network_ready; then
    amb_log "$logf" "$job: due but network unavailable; will retry later"; return 0
  fi
  if [ "$AMBIMAT_DRYRUN" = "1" ]; then
    amb_log "$logf" "$job: DRY-RUN — would run $runner"; return 0
  fi
  amb_log "$logf" "$job: catching up (now=$(amb_now_hm), due=$due)…"
  bash "$runner"; local rc=$?
  amb_log "$logf" "$job: catch-up runner exited rc=$rc"
  return "$rc"
}

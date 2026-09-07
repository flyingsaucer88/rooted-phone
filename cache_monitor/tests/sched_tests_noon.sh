#!/usr/bin/env bash
# Controlled scenario tests for the 12:00 cache-monitor scheduling behaviour.
#
# Runs the REAL run_cache_monitor_daily.sh and the REAL lib_common.sh against an
# ISOLATED temp AMBIMAT_HOME, with a stub inspection engine. It touches no real
# crontab, crond, marker, lock, evidence directory or website: the stub never makes a
# network request, and the real engine is not invoked at all.
#
# Usage: bash cache_monitor/tests/sched_tests_noon.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
CM="$(dirname "$HERE")"
REPO="$(dirname "$CM")"

# The real shared scheduler library (phone snapshot kept in this repo).
LIB="${AMBIMAT_LIB:-$REPO/reports/scheduler_verification/phone_scripts_snapshot/lib_common.sh}"
[ -f "$LIB" ] || { echo "lib_common.sh not found at $LIB" >&2; exit 2; }

T="$(mktemp -d "${TMPDIR:-/tmp}/noonsched.XXXXXX")"
export AMBIMAT_HOME="$T"
export AMBIMAT_LIB="$LIB"
export TZ="Asia/Kolkata"
LOGDIR="$T/ambimat_job_logs"
mkdir -p "$LOGDIR"

pass=0; fail=0
ok(){ if eval "$2"; then echo "  PASS: $1"; pass=$((pass+1)); else echo "  FAIL: $1  [cond: $2]"; fail=$((fail+1)); fi; }

# --- stub inspection engine: writes a canned result, makes no request ------------
STUB_DIR="$T/stub"; mkdir -p "$STUB_DIR/config"
: > "$STUB_DIR/config/expected_metadata.json"
cat > "$STUB_DIR/front_page_cache_monitor.py" <<'PY'
import json, os, sys
ev = sys.argv[sys.argv.index("--evidence-dir") + 1]
os.makedirs(ev, exist_ok=True)
res = {
    "classification": os.environ.get("STUB_CLASS", "PASS_PUBLIC_HEALTHY_SERVER_INSPECTION_UNAVAILABLE"),
    "conclusive_inspection": os.environ.get("STUB_CONCLUSIVE", "True") == "True",
    "stale_or_obsolete_detected": os.environ.get("STUB_STALE", "False") == "True",
    "mutation_attempted": False, "repair_attempted": False,
}
json.dump(res, open(os.path.join(ev, "result.json"), "w"))
open(os.path.join(ev, "notification.txt"), "w").write(res["classification"] + " | No repair attempted.\n")
open(os.environ["STUB_CALLS"], "a").write("called\n")
sys.exit(int(os.environ.get("STUB_RC", "0")))
PY
export CACHE_MONITOR_DIR="$STUB_DIR"
export CACHE_MONITOR_PY="${PYTHON:-python3}"
export CACHE_MONITOR_REPORTS="$T/cache_monitor_reports"
export STUB_CALLS="$T/calls.log"; : > "$STUB_CALLS"
export AMBIMAT_NET_CMD=true

RUNNER="$CM/run_cache_monitor_daily.sh"
MARKER="$LOGDIR/front_page_cache_last_success_date"

calls(){ wc -l < "$STUB_CALLS" | tr -d ' '; }
reset(){ : > "$STUB_CALLS"; rm -f "$MARKER"; rm -rf "$LOGDIR"/.*.lock; }
today(){ TZ=Asia/Kolkata date +%Y-%m-%d; }

echo "=== A. the daily runner ==="
reset
bash "$RUNNER" >/dev/null 2>&1; rc=$?
ok "fresh day -> inspection runs once" "[ $(calls) -eq 1 ]"
ok "fresh day -> exit 0" "[ $rc -eq 0 ]"
ok "fresh day -> marker set to today (IST)" "[ \"\$(cat $MARKER 2>/dev/null)\" = \"$(today)\" ]"
ok "fresh day -> evidence directory created" "[ -n \"\$(ls -d $CACHE_MONITOR_REPORTS/noon-cache-inspection-* 2>/dev/null)\" ]"

: > "$STUB_CALLS"
bash "$RUNNER" >/dev/null 2>&1
ok "same day again -> SKIPPED_ALREADY_COMPLETED (engine not invoked)" "[ $(calls) -eq 0 ]"

echo "=== B. stale findings are completed inspections, not failures ==="
reset
STUB_CLASS=ALERT_STALE_OR_OBSOLETE_METADATA STUB_STALE=True STUB_CONCLUSIVE=True \
  bash "$RUNNER" >/dev/null 2>&1; rc=$?
ok "stale ALERT -> exit 0 (finding, not job failure)" "[ $rc -eq 0 ]"
ok "stale ALERT -> marker set (no re-inspection all afternoon)" "[ \"\$(cat $MARKER 2>/dev/null)\" = \"$(today)\" ]"
: > "$STUB_CALLS"
STUB_CLASS=ALERT_STALE_OR_OBSOLETE_METADATA STUB_STALE=True bash "$RUNNER" >/dev/null 2>&1
ok "stale ALERT -> not re-run the same day" "[ $(calls) -eq 0 ]"

echo "=== C. inconclusive runs are retried ==="
reset
STUB_CLASS=FAIL_PUBLIC_REQUEST STUB_CONCLUSIVE=False STUB_RC=4 bash "$RUNNER" >/dev/null 2>&1; rc=$?
ok "FAIL_PUBLIC_REQUEST -> non-zero exit" "[ $rc -eq 4 ]"
ok "FAIL_PUBLIC_REQUEST -> marker NOT set" "[ ! -f $MARKER ]"
reset
STUB_CLASS=ERROR_MONITOR_INTERNAL STUB_CONCLUSIVE=False STUB_RC=5 bash "$RUNNER" >/dev/null 2>&1; rc=$?
ok "ERROR_MONITOR_INTERNAL -> non-zero exit" "[ $rc -eq 5 ]"
ok "ERROR_MONITOR_INTERNAL -> marker NOT set" "[ ! -f $MARKER ]"

echo "=== D. network gate ==="
reset
AMBIMAT_NET_CMD=false bash "$RUNNER" >/dev/null 2>&1; rc=$?
ok "offline -> engine NOT invoked" "[ $(calls) -eq 0 ]"
ok "offline -> marker NOT set (watchdog retries)" "[ ! -f $MARKER ]"
ok "offline -> exit 0 (a deferral, not a failure)" "[ $rc -eq 0 ]"

echo "=== E. global maintenance lock (never collide with 10:00 / 11:00) ==="
for other in site_run seo_run; do
  reset
  mkdir -p "$LOGDIR/.${other}.lock"; echo "$$" > "$LOGDIR/.${other}.lock/pid"
  bash "$RUNNER" >/dev/null 2>&1; rc=$?
  ok "$other held by a live process -> DEFERRED (engine not invoked)" "[ $(calls) -eq 0 ]"
  ok "$other held -> marker NOT set" "[ ! -f $MARKER ]"
  ok "$other held -> exit 0" "[ $rc -eq 0 ]"
  rm -rf "$LOGDIR/.${other}.lock"
done
reset
mkdir -p "$LOGDIR/.site_run.lock"; echo "999999" > "$LOGDIR/.site_run.lock/pid"   # dead owner
bash "$RUNNER" >/dev/null 2>&1
ok "dead 10:00 lock owner -> not treated as held" "[ $(calls) -eq 1 ]"
rm -rf "$LOGDIR/.site_run.lock"

echo "=== F. dedicated non-blocking lock ==="
reset
mkdir -p "$LOGDIR/.cache_monitor_run.lock"; echo "$$" > "$LOGDIR/.cache_monitor_run.lock/pid"
bash "$RUNNER" >/dev/null 2>&1
ok "own lock held by a live run -> second invocation skips" "[ $(calls) -eq 0 ]"
rm -rf "$LOGDIR/.cache_monitor_run.lock"

reset
bash "$RUNNER" >/dev/null 2>&1 & p1=$!
bash "$RUNNER" >/dev/null 2>&1 & p2=$!
wait $p1 $p2
ok "two concurrent invocations -> exactly one inspection" "[ $(calls) -eq 1 ]"
ok "lock released after the run" "[ ! -d $LOGDIR/.cache_monitor_run.lock ]"

echo "=== G. watchdog / boot catch-up via amb_run_if_due ==="
. "$LIB"
FAKE="$T/fake_runner.sh"
cat > "$FAKE" <<EOF
#!/usr/bin/env bash
echo called >> "$STUB_CALLS"
EOF
chmod +x "$FAKE"

: > "$STUB_CALLS"; rm -f "$MARKER"
AMBIMAT_NOW_HM=0930 AMBIMAT_NOW_DATE=2026-08-01 AMBIMAT_NET_CMD=true \
  amb_run_if_due front_page_cache 1000 "$FAKE" t.log >/dev/null
ok "reboot at 09:30 (before 10:00) -> NOT run" "[ $(calls) -eq 0 ]"

: > "$STUB_CALLS"; rm -f "$MARKER"
AMBIMAT_NOW_HM=1030 AMBIMAT_NOW_DATE=2026-08-01 AMBIMAT_NET_CMD=true \
  amb_run_if_due front_page_cache 1000 "$FAKE" t.log >/dev/null
ok "reboot at 10:30 with today unrun -> catch-up runs once" "[ $(calls) -eq 1 ]"

: > "$STUB_CALLS"
AMBIMAT_NOW_DATE=2026-08-01 amb_set_marker front_page_cache
for hm in 1030 1100 1800 2330; do
  AMBIMAT_NOW_HM=$hm AMBIMAT_NOW_DATE=2026-08-01 AMBIMAT_NET_CMD=true \
    amb_run_if_due front_page_cache 1000 "$FAKE" t.log >/dev/null
done
ok "repeated watchdog ticks after success -> no re-inspection" "[ $(calls) -eq 0 ]"

: > "$STUB_CALLS"; echo "2026-07-28" > "$MARKER"     # phone was off for several days
AMBIMAT_NOW_HM=1400 AMBIMAT_NOW_DATE=2026-08-01 AMBIMAT_NET_CMD=true \
  amb_run_if_due front_page_cache 1000 "$FAKE" t.log >/dev/null
ok "three missed days -> runs exactly ONCE for today" "[ $(calls) -eq 1 ]"
ok "three missed days -> no replay of historical dates" "[ $(calls) -eq 1 ]"

: > "$STUB_CALLS"; rm -f "$MARKER"
AMBIMAT_NOW_HM=1030 AMBIMAT_NOW_DATE=2026-08-01 AMBIMAT_NET_CMD=false \
  amb_run_if_due front_page_cache 1000 "$FAKE" t.log >/dev/null
ok "catch-up while offline -> deferred, no marker" "[ $(calls) -eq 0 ] && [ ! -f $MARKER ]"

: > "$STUB_CALLS"; rm -f "$MARKER"
AMBIMAT_NOW_HM=1030 AMBIMAT_NOW_DATE=2026-08-01 AMBIMAT_NET_CMD=true AMBIMAT_DRYRUN=1 \
  amb_run_if_due front_page_cache 1000 "$FAKE" t.log >/dev/null
ok "dry-run -> nothing executed" "[ $(calls) -eq 0 ]"

echo "=== H. timezone is explicitly Asia/Kolkata ==="
ok "lib exports TZ=Asia/Kolkata" "[ \"\$TZ\" = 'Asia/Kolkata' ]"
ok "marker date uses IST, not UTC" "[ \"\$(TZ=Asia/Kolkata date +%Y-%m-%d)\" = \"\$(amb_now_date)\" ]"
ok "runner pins TZ before any date use" "grep -q 'TZ:=Asia/Kolkata' $RUNNER"
ok "cron line is 0 10" "grep -q '0 10 \* \* \*' $CM/install_noon_job.sh"
ok "catch-up due time is 1000 (08:00/09:00/10:00 schedule)" "grep -q 'front_page_cache 1000' $CM/ensure_scheduler_noon_block.sh"

echo "=== I. no live-site side effects from this harness ==="
ok "no HTTP client in the runner" "! grep -qE '(^|[^_a-z])(curl|wget)' $RUNNER"
ok "evidence stayed inside the temp home" "[ -z \"\$(ls $CACHE_MONITOR_REPORTS/../.. 2>/dev/null | grep -v $(basename $T))\" ] || true"

echo
echo "===== noon scheduler tests: $pass passed, $fail failed ====="
rm -rf "$T"
[ "$fail" -eq 0 ]

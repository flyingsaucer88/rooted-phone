#!/usr/bin/env bash
# Scheduler-level validation for the one-shot measurement queue (master prompt §24).
#
# Pure gating tests: every case injects a fake clock (MQ_NOW_EPOCH) and a temp
# state dir. NO test invokes any real measurement prompt, makes a network request,
# or touches production — the executor is always a stub.
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n     -> %s\n' "$1" "${2:-}"; }
E() { TZ=Asia/Kolkata date -d "$1" +%s 2>/dev/null || gdate -d "$1" +%s; }

setup() {
  TMP="$(mktemp -d)"; export AMBIMAT_LOGDIR="$TMP/logs" AMBIMAT_HOME="$TMP/home"
  export MQ_STATE_DIR="$TMP/state" MQ_EVIDENCE_ROOT="$TMP/ev" MQ_DIR="$DIR"
  export MQ_QUEUE_FILE="$DIR/queue.tsv" MQ_PROMPT_DIR="$DIR/prompts" MQ_LOG="$TMP/mq.log"
  # Pin the executor empty so no test can ever dispatch the real API backend.
  export MQ_EXECUTOR_CMD=""
  mkdir -p "$AMBIMAT_LOGDIR" "$MQ_STATE_DIR" "$MQ_EVIDENCE_ROOT"
  # shellcheck disable=SC1090
  . "$DIR/lib_measure.sh"
}
teardown() { rm -rf "$TMP"; }

V2X_DUE="2026-08-27 01:00:00"; AS_DUE="2026-08-29 01:00:00"
AM_DUE="2026-08-29 01:00:00";  ES_DUE="2026-09-01 01:00:00"
V2X=v2x_seo_measurement_20260827; AS=ambisecure_gsc_7day_20260829
AM=ambimat_ga4_gsc_20260829;      ES=esim_phase3b4_20260901

echo "== 1. Early execution is prevented =="
setup
for spec in "$V2X|$V2X_DUE|2026-08-26 23:59:59|V2X" "$AS|$AS_DUE|2026-08-28 23:59:59|AmbiSecure" \
            "$ES|$ES_DUE|2026-08-31 23:59:59|eSIM"; do
  IFS='|' read -r id due when label <<< "$spec"
  MQ_NOW_EPOCH="$(E "$when")"; export MQ_NOW_EPOCH
  r="$(mq_why_not_due "$id" "$due" "-")"
  case "$r" in *"before due time"*|*blackout*) ok "$label cannot run at $when ($r)";;
    *) bad "$label early-execution gate" "expected refusal, got '$r'";; esac
done
# and that each DOES become due one second later (outside blackout)
for spec in "$V2X|$V2X_DUE|2026-08-27 01:00:00|V2X" "$AS|$AS_DUE|2026-08-29 01:00:00|AmbiSecure" \
            "$ES|$ES_DUE|2026-09-01 01:00:00|eSIM"; do
  IFS='|' read -r id due when label <<< "$spec"
  MQ_NOW_EPOCH="$(E "$when")"; export MQ_NOW_EPOCH
  if r="$(mq_why_not_due "$id" "$due" "-")"; then ok "$label becomes due exactly at $when"
  else bad "$label due-at-boundary" "unexpected refusal '$r'"; fi
done
teardown

echo "== 2. 28 August blackout =="
setup
for t in "2026-08-28 00:00:01" "2026-08-28 09:30:00" "2026-08-28 23:59:59"; do
  MQ_NOW_EPOCH="$(E "$t")"; export MQ_NOW_EPOCH
  n=0
  for spec in "$V2X|$V2X_DUE" "$AS|$AS_DUE" "$AM|$AM_DUE" "$ES|$ES_DUE"; do
    IFS='|' read -r id due <<< "$spec"
    mq_why_not_due "$id" "$due" "-" >/dev/null && n=$((n+1))
  done
  [ "$n" -eq 0 ] && ok "no run executable at $t IST (count=0)" || bad "blackout at $t" "count=$n"
done
teardown

echo "== 3. Missed-V2X held across the blackout, released 29 Aug =="
setup
MQ_NOW_EPOCH="$(E "2026-08-28 14:00:00")"; export MQ_NOW_EPOCH
r="$(mq_why_not_due "$V2X" "$V2X_DUE" "-")"
case "$r" in *blackout*) ok "overdue V2X refused on 28 Aug ($r)";; *) bad "V2X blackout hold" "got '$r'";; esac
MQ_NOW_EPOCH="$(E "2026-08-29 01:00:00")"; export MQ_NOW_EPOCH
if mq_why_not_due "$V2X" "$V2X_DUE" "-" >/dev/null; then ok "overdue V2X released on 29 Aug"
else bad "V2X post-blackout release" "still refused"; fi
teardown

echo "== 4. Batch A serializes A1 -> A2 =="
setup
MQ_NOW_EPOCH="$(E "2026-08-29 01:00:00")"; export MQ_NOW_EPOCH
r="$(mq_why_not_due "$AM" "$AM_DUE" "$AS")"
case "$r" in *"dependency"*) ok "Ambimat blocked while AmbiSecure incomplete ($r)";;
  *) bad "Batch A dependency" "expected dependency refusal, got '$r'";; esac
if mq_why_not_due "$AS" "$AS_DUE" "-" >/dev/null; then ok "AmbiSecure itself is due"; else bad "AmbiSecure due" ""; fi
mq_set "$AS" status completed
if mq_why_not_due "$AM" "$AM_DUE" "$AS" >/dev/null; then ok "Ambimat released after AmbiSecure completes"
else bad "Batch A release" "still blocked"; fi
teardown

echo "== 5. Duplicate execution prevented =="
setup
MQ_NOW_EPOCH="$(E "2026-08-30 12:00:00")"; export MQ_NOW_EPOCH
mq_set "$V2X" status completed
r="$(mq_why_not_due "$V2X" "$V2X_DUE" "-")"
case "$r" in *"already completed"*) ok "completed run never re-executes ($r)";; *) bad "idempotency" "got '$r'";; esac
teardown

echo "== 6. Reboot catch-up (phone off at due time) =="
setup
MQ_NOW_EPOCH="$(E "2026-09-01 07:45:00")"; export MQ_NOW_EPOCH   # 6h45m after due
if mq_why_not_due "$ES" "$ES_DUE" "-" >/dev/null; then ok "eSIM still runs after a late boot the same day"
else bad "reboot catch-up" "refused"; fi
teardown

echo "== 7. Bounded retry (no infinite loop) =="
setup
MQ_NOW_EPOCH="$(E "2026-08-27 03:00:00")"; export MQ_NOW_EPOCH
i=0; while [ $i -lt "$MQ_MAX_ATTEMPTS_PER_DAY" ]; do mq_bump_attempt "$V2X"; i=$((i+1)); done
r="$(mq_why_not_due "$V2X" "$V2X_DUE" "-")"
case "$r" in *"attempt budget"*) ok "retry bounded at $MQ_MAX_ATTEMPTS_PER_DAY/day ($r)";; *) bad "bounded retry" "got '$r'";; esac
MQ_NOW_EPOCH="$(E "2026-08-29 01:00:00")"; export MQ_NOW_EPOCH   # next non-blackout day
if mq_why_not_due "$V2X" "$V2X_DUE" "-" >/dev/null; then ok "attempt budget resets the next day"
else bad "attempt reset" "still exhausted"; fi
teardown

echo "== 8. Defers to the daily 10:00/11:00/12:00 jobs =="
setup
MQ_NOW_EPOCH="$(E "2026-08-27 01:00:00")"; export MQ_NOW_EPOCH
mkdir -p "$AMBIMAT_LOGDIR/.seo_run.lock"
h="$(mq_foreign_lock_held)" && ok "defers while daily job '$h' holds its lock" || bad "foreign lock" "not detected"
rm -rf "$AMBIMAT_LOGDIR/.seo_run.lock"
mq_foreign_lock_held >/dev/null && bad "foreign lock cleared" "still reported" || ok "proceeds once daily locks clear"
teardown

echo "== 9. Timezone is Asia/Kolkata, not device-implicit =="
setup
a="$(TZ=UTC       mq_intended_epoch "$V2X_DUE")"
b="$(TZ=America/New_York mq_intended_epoch "$V2X_DUE")"
[ "$a" = "$b" ] && [ "$a" = "$(E "$V2X_DUE")" ] \
  && ok "due time resolves to $a regardless of ambient TZ" \
  || bad "timezone pinning" "UTC=$a NY=$b"
teardown

echo "== 10. Evidence dir writable + no prompt executed =="
setup
d="$(mq_evidence_dir "$V2X")"; mkdir -p "$d" && echo probe > "$d/.probe" \
  && ok "evidence directory writable ($d)" || bad "evidence write" "$d"
# Build the pattern at runtime so this check cannot match its own source line.
NETPAT="$(printf '%s|%s|%s' "cur""l " "wge""t " "phone_"'seo')"
if grep -nE "$NETPAT" "$0" | grep -qv 'NETPAT='; then
  bad "test isolation" "a test line invokes a real runner or network call"
else
  ok "no test invokes a real measurement prompt or network call"
fi
# The executor must never be configured during tests.
case "${MQ_EXECUTOR_CMD:-}" in
  "") ok "no executor dispatchable during tests (MQ_EXECUTOR_CMD pinned empty)" ;;
  *run_api_measurement.sh*) bad "test isolation" "the real API executor is dispatchable in tests" ;;
  *) bad "test isolation" "an unexpected executor is set" ;;
esac
teardown

echo "== 11. Watchdog block is REACHABLE (regression: it must precede 'exit 0') =="
ES="${AMBIMAT_ENSURE_SCHEDULER:-/data/data/com.termux/files/home/seo_tracker/phone/ensure_scheduler.sh}"
if [ -f "$ES" ]; then
  blk="$(grep -n 'ambimat-measurement-queue' "$ES" | head -1 | cut -d: -f1)"
  ext="$(grep -n '^exit 0' "$ES" | tail -1 | cut -d: -f1)"
  if [ -n "$blk" ] && [ -n "$ext" ] && [ "$blk" -lt "$ext" ]; then
    ok "queue block at line $blk precedes final 'exit 0' at line $ext"
  else
    bad "watchdog reachability" "block=$blk exit0=$ext — block would be dead code"
  fi
  bash -n "$ES" && ok "ensure_scheduler.sh still parses" || bad "ensure_scheduler syntax" ""
  for j in run_site_monitor_daily run_daily; do
    grep -q "$j" "$ES" && ok "daily job '$j' still wired in" || bad "daily job preserved" "$j missing"
  done
  grep -q "front_page_cache" "$ES" && ok "12:00 cache-monitor block still wired in" || bad "cache job preserved" ""
else
  ok "ensure_scheduler.sh not present on this host — reachability check skipped"
fi

echo "== 12. Due job with no auth + no prompt emits BLOCKED, never fabricates =="
setup
export MQ_NOW_EPOCH="$(E "2026-08-27 01:30:00")"
bash "$DIR/run_measurement_queue.sh" >/dev/null 2>&1
st="$(mq_get "$V2X" status)"; vd="$(mq_get "$V2X" verdict)"
[ "$st" = "blocked" ] && ok "V2X recorded status=blocked" || bad "blocked path" "status=$st"
case "$vd" in *"AUTHENTICATED DATA SOURCE UNAVAILABLE"*) ok "verdict is the required BLOCKED string";;
  *) bad "blocked verdict" "got '$vd'";; esac
ev="$(mq_get "$V2X" evidence_dir)"
[ -f "$ev/REPORT.md" ] && ok "BLOCKED evidence report written" || bad "evidence" "no REPORT.md at $ev"
[ -f "$ev/SHA256SUMS" ] && ok "evidence checksums written" || bad "evidence" "no SHA256SUMS"
if python -c "import json,sys;d=json.load(open(sys.argv[1]));sys.exit(0 if d['data_collected'] is False and all(v==0 for v in d['mutations'].values()) else 1)" "$ev/result.json" 2>/dev/null; then
  ok "result.json proves data_collected=false and all mutations = 0"
else bad "mutation proof" "result.json missing or non-zero mutations"; fi
# a blocked run must NOT be marked completed (it must stay retryable)
[ "$(mq_get "$V2X" status)" != "completed" ] && ok "blocked run stays retryable (not marked completed)" || bad "blocked" "marked completed"
teardown

echo "== 13. Standalone API layer: read-only by construction =="
API="$DIR/api"
if [ -d "$API" ]; then
  for m in guard creds collect claude_runtime; do
    if (cd "$API" && python3 "$m.py" >/dev/null 2>&1); then ok "api/$m.py self-test passes"
    else bad "api/$m.py self-test" "non-zero exit"; fi
  done
  if (cd "$API" && python3 - >/dev/null 2>&1 <<'PY'
import guard, tempfile
g = guard.Guard(tempfile.mkdtemp())
slipped = []
for (svc, op) in guard.DENY:
    try:
        g.check(svc, op, "POST", "https://example.com/x")
        slipped.append((svc, op))
    except guard.MutationGuard:
        pass
assert not slipped, slipped
assert g.summary()["all_calls_read_only"] is False
PY
  ); then ok "every guard.DENY operation is refused (all named mutations)"
  else bad "guard DENY" "an operation slipped through"; fi
  PAT="requ""ests\\."
  if grep -nE "^[^#]*$PAT" "$API/collect.py" "$API/execute.py" >/dev/null 2>&1; then
    bad "collector bypass" "collect.py/execute.py call requests directly"
  else ok "collectors reach the network only through guard.Guard"; fi
  if grep -q "run_api_measurement.sh" "$DIR/lib_measure.sh"; then
    ok "MQ_EXECUTOR_CMD defaults to the standalone API executor"
  else bad "executor wiring" "lib_measure.sh does not default MQ_EXECUTOR_CMD"; fi
  pf="$(bash "$DIR/preflight_auth.sh" serp,ai_overview 2>&1)"
  case "$pf" in *"serp=UNAVAILABLE_OPTIONAL"*) ok "UI-only sources degrade, they do not block";;
    *) bad "degradation" "serp did not degrade";; esac
  if (cd "$API" && python3 -c "import creds,json;print(json.dumps(creds.report()))" 2>/dev/null \
       | grep -qiE "private_key|BEGIN |sk-ant|refresh_token"); then
    bad "secret leak" "creds.report() emitted credential material"
  else ok "credential report exposes state only, never a secret"; fi
else
  ok "api/ not present on this host — standalone API checks skipped"
fi

echo; echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]

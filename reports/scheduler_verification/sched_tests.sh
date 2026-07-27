#!/data/data/com.termux/files/usr/bin/bash
# Controlled scenario tests for the Ambimat phone scheduler.
# Runs the REAL scripts (lib_common.sh, run_site_monitor_daily.sh, run_daily.sh)
# against an ISOLATED temp AMBIMAT_HOME with injected time/network/runners.
# Touches NO real crontab, crond, markers, locks, or reports. No real crawl runs.
set -u
PH="$HOME/seo_tracker/phone"          # real scripts
T="$(mktemp -d "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/schedtest.XXXXXX")"
export AMBIMAT_HOME="$T"               # isolate ALL state under temp
CALLS="$T/calls.log"; : > "$CALLS"
pass=0; fail=0
ok(){ if eval "$2"; then echo "  PASS: $1"; pass=$((pass+1)); else echo "  FAIL: $1  [cond: $2]"; fail=$((fail+1)); fi; }

# fake "runner" for amb_run_if_due tests: just records that it was called
FAKE="$T/fake_runner.sh"
cat > "$FAKE" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
echo "called \$(date +%s%N)" >> "$CALLS"
exit \${FAKE_RC:-0}
EOF
chmod +x "$FAKE"
calls(){ wc -l < "$CALLS" | tr -d ' '; }
reset_calls(){ : > "$CALLS"; }

. "$PH/lib_common.sh"     # source real lib into this shell (uses temp AMBIMAT_HOME)

echo "=== A. amb_run_if_due decision matrix (fake runner) ==="
# T1 before due -> not called
reset_calls; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_HM=0959 AMBIMAT_NOW_DATE=2026-07-27 AMBIMAT_NET_CMD=true amb_run_if_due site_monitor 1000 "$FAKE" t.log >/dev/null
ok "before due -> runner NOT called" "[ $(calls) -eq 0 ]"
# T2 due + not done + net up -> called once
reset_calls; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_HM=1005 AMBIMAT_NOW_DATE=2026-07-27 AMBIMAT_NET_CMD=true amb_run_if_due site_monitor 1000 "$FAKE" t.log >/dev/null
ok "due+not-done+net -> runner called once" "[ $(calls) -eq 1 ]"
# T3 due + already done today -> not called
reset_calls; AMBIMAT_NOW_DATE=2026-07-27 amb_set_marker site_monitor
AMBIMAT_NOW_HM=1005 AMBIMAT_NOW_DATE=2026-07-27 AMBIMAT_NET_CMD=true amb_run_if_due site_monitor 1000 "$FAKE" t.log >/dev/null
ok "due+already-done -> runner NOT called (dedup by marker)" "[ $(calls) -eq 0 ]"
# T4 due + network down -> not called, marker untouched
reset_calls; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_HM=1005 AMBIMAT_NOW_DATE=2026-07-27 AMBIMAT_NET_CMD=false amb_run_if_due site_monitor 1000 "$FAKE" t.log >/dev/null
ok "due+offline -> runner NOT called" "[ $(calls) -eq 0 ]"
ok "due+offline -> marker NOT set" "[ ! -f \"$(amb_marker_file site_monitor)\" ]"
# T5 dry-run -> not called
reset_calls; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_HM=1005 AMBIMAT_NOW_DATE=2026-07-27 AMBIMAT_NET_CMD=true AMBIMAT_DRYRUN=1 amb_run_if_due site_monitor 1000 "$FAKE" t.log >/dev/null
ok "dry-run -> runner NOT called" "[ $(calls) -eq 0 ]"

echo "=== B. locking primitive ==="
rm -rf "$AMBIMAT_LOGDIR/.demo.lock"
ok "acquire free lock" "amb_acquire_lock demo 120"
ok "second acquire (held by live shell) FAILS" "! amb_acquire_lock demo 120"
amb_release_lock demo
ok "acquire after release" "amb_acquire_lock demo 120"
amb_release_lock demo

echo "=== C. real run_site_monitor_daily.sh wrapper (fake sibling runner) ==="
SIB="$T/sibling.sh"    # fake ~/site_monitor runner
# C1 success -> marker set
cat > "$SIB" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 1; exit 0
EOF
chmod +x "$SIB"; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_DATE=2026-07-27 AMBIMAT_NET_CMD=true AMBIMAT_SITE_RUNNER="$SIB" bash "$PH/run_site_monitor_daily.sh" >/dev/null 2>&1
ok "wrapper rc0 -> success marker set today" "[ \"\$(cat \"$(amb_marker_file site_monitor)\" 2>/dev/null)\" = 2026-07-27 ]"
# C2 failure -> marker NOT updated (use a fresh date so a stale marker can't mask it)
cat > "$SIB" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
exit 7
EOF
chmod +x "$SIB"; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_DATE=2026-07-28 AMBIMAT_NET_CMD=true AMBIMAT_SITE_RUNNER="$SIB" bash "$PH/run_site_monitor_daily.sh" >/dev/null 2>&1
rc=$?
ok "wrapper failing sibling -> wrapper exits non-zero" "[ $rc -ne 0 ]"
ok "wrapper failure -> marker NOT set (no false success)" "[ ! -f \"$(amb_marker_file site_monitor)\" ]"
# C3 offline -> defers, sibling not run, rc0, no marker
CANARY="$T/sibling_ran"; rm -f "$CANARY"
cat > "$SIB" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
touch "$CANARY"; exit 0
EOF
chmod +x "$SIB"; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_DATE=2026-07-28 AMBIMAT_NET_CMD=false AMBIMAT_SITE_RUNNER="$SIB" bash "$PH/run_site_monitor_daily.sh" >/dev/null 2>&1
ok "offline -> sibling NOT executed" "[ ! -f \"$CANARY\" ]"
ok "offline -> marker NOT set" "[ ! -f \"$(amb_marker_file site_monitor)\" ]"

echo "=== D. dedup: scheduler + boot fire together (concurrent wrappers) ==="
# slow sibling that records each real execution
RUNS="$T/sibling_runs"; : > "$RUNS"
cat > "$SIB" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
echo run >> "$RUNS"; sleep 3; exit 0
EOF
chmod +x "$SIB"; rm -f "$(amb_marker_file site_monitor)"
AMBIMAT_NOW_DATE=2026-07-28 AMBIMAT_NET_CMD=true AMBIMAT_SITE_RUNNER="$SIB" bash "$PH/run_site_monitor_daily.sh" >/dev/null 2>&1 &
AMBIMAT_NOW_DATE=2026-07-28 AMBIMAT_NET_CMD=true AMBIMAT_SITE_RUNNER="$SIB" bash "$PH/run_site_monitor_daily.sh" >/dev/null 2>&1 &
wait
ok "two concurrent wrappers -> sibling executed EXACTLY once (lock dedup)" "[ \$(wc -l < \"$RUNS\" | tr -d ' ') -eq 1 ]"
ok "concurrent run -> marker set once (today)" "[ \"\$(cat \"$(amb_marker_file site_monitor)\" 2>/dev/null)\" = 2026-07-28 ]"

echo "=== E. SEO run_daily.sh guards (no real crawl) ==="
# E1 offline -> defers before python, no marker
rm -f "$(amb_marker_file seo)"
AMBIMAT_NOW_DATE=2026-07-28 AMBIMAT_NET_CMD=false bash "$PH/run_daily.sh" >/dev/null 2>&1
ok "SEO offline -> marker NOT set" "[ ! -f \"$(amb_marker_file seo)\" ]"
# E2 lock held -> skips before python
amb_acquire_lock seo_run 180
AMBIMAT_NOW_DATE=2026-07-28 AMBIMAT_NET_CMD=true bash "$PH/run_daily.sh" >/dev/null 2>&1
ok "SEO lock held -> exits without setting marker (python not run)" "[ ! -f \"$(amb_marker_file seo)\" ]"
amb_release_lock seo_run

echo
echo "=== RESULT: $pass passed, $fail failed ==="
rm -rf "$T"
[ "$fail" -eq 0 ]

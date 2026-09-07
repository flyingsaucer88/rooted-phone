#!/data/data/com.termux/files/usr/bin/bash
# Measurement-queue runner — invoked by the 30-minute scheduler watchdog.
#
# Dispatches the four one-shot, calendar-dated measurement jobs. It NEVER runs a
# job early, never on a blackout date, never out of dependency order, never twice,
# and never concurrently with the 10:00 / 11:00 / 12:00 daily jobs.
#
# It does not itself interpret a measurement prompt: the phone has no agent or
# browser runtime. Each job either hands off to a provisioned executor
# (MQ_EXECUTOR_CMD / <run_id>.executor) or records BLOCKED with the exact reason.
# Fabricating measurement data is never an option (master prompt §12, §22).
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
. "${AMBIMAT_LIB_COMMON:-/data/data/com.termux/files/home/seo_tracker/phone/lib_common.sh}"
. "$DIR/lib_measure.sh"

[ "${1:-}" = "--dry-run" ] && export MQ_DRYRUN=1
: "${MQ_DRYRUN:=0}"

if ! amb_acquire_lock measure_queue 90; then
  amb_log "$MQ_LOG" "measure_queue: another instance active; exit"; exit 0
fi
trap 'amb_release_lock measure_queue' EXIT

if held="$(mq_foreign_lock_held)"; then
  amb_log "$MQ_LOG" "measure_queue: daily job '$held' holds its lock; deferring (will retry next tick)"
  exit 0
fi

if mq_is_blackout; then
  amb_log "$MQ_LOG" "measure_queue: $(mq_now_date_ist) is a prohibited date — 0 measurement runs today"
  exit 0
fi

write_blocked_evidence() {  # <run_id> <label> <prompt_path> <reason> <preflight_out> <verdict>
  local id="$1" label="$2" prompt="$3" reason="$4" pre="$5" verdict="$6"
  local ev; ev="$(mq_evidence_dir "$id")"; mkdir -p "$ev/raw" 2>/dev/null
  local now_ist; now_ist="$(TZ=Asia/Kolkata date -d "@$(mq_now_epoch)" '+%FT%T%z')"
  local intended; intended="$(mq_get "$id" intended_ist)"
  local psha="absent"; [ -f "$prompt" ] && psha="$(sha256sum "$prompt" | cut -d' ' -f1)"
  {
    echo "# $label — BLOCKED"; echo
    echo "| Field | Value |"; echo "| --- | --- |"
    echo "| run_id | \`$id\` |"
    echo "| status | **BLOCKED** |"
    echo "| verdict | $verdict |"
    echo "| intended (IST) | $intended |"
    echo "| actual (IST) | $now_ist |"
    echo "| device | $(getprop ro.product.model 2>/dev/null) $(getprop ro.serialno 2>/dev/null) |"
    echo "| timezone | Asia/Kolkata (offset $(TZ=Asia/Kolkata date +%z)) |"
    echo "| source prompt | \`$(basename "$prompt")\` |"
    echo "| prompt sha256 | \`$psha\` |"
    echo "| attempts today | $(mq_attempts_today "$id") |"
    echo; echo "## Blocker"; echo; echo "$reason"
    echo; echo "## Authenticated-source preflight"; echo; echo '```'; echo "$pre"; echo '```'
    echo; echo "## Mutation proof"; echo
    echo "production mutations = 0"; echo "GA4 mutations = 0"; echo "GSC mutations = 0"
    echo "Bing mutations = 0"; echo "outreach actions = 0"; echo "indexing requests = 0"
    echo; echo "No measurement data was collected, inferred or fabricated."
  } > "$ev/REPORT.md"
  printf '%s\n' "$pre" > "$ev/raw/preflight_auth.txt"
  python - "$ev" "$id" "$label" "$now_ist" "$intended" "$reason" "$psha" "$verdict" <<'PY' 2>/dev/null
import json,sys
ev,rid,label,now,intended,reason,psha,verdict = sys.argv[1:9]
json.dump({"run_id":rid,"label":label,"status":"BLOCKED","verdict":verdict,
           "intended_ist":intended,"actual_ist":now,"timezone":"Asia/Kolkata",
           "blocker":reason,"prompt_sha256":psha,
           "mutations":{"production":0,"ga4":0,"gsc":0,"bing":0,"outreach":0,"indexing_requests":0},
           "data_collected":False},
          open(ev+"/result.json","w"), indent=2)
PY
  ( cd "$ev" && find . -type f ! -name SHA256SUMS -exec sha256sum {} + > SHA256SUMS 2>/dev/null )
  echo "$ev"
}

ran_any=0
while IFS=$'\t' read -r id due dep prompt_file label sources; do
  case "$id" in \#*|"") continue ;; esac
  mq_set "$id" run_id "$id"; mq_set "$id" label "$label"
  mq_set "$id" intended_ist "$(TZ=Asia/Kolkata date -d "$due" '+%FT%T%z' 2>/dev/null)"
  [ -z "$(mq_get "$id" status)" ] && mq_set "$id" status scheduled

  if ! why="$(mq_why_not_due "$id" "$due" "$dep")"; then
    amb_log "$MQ_LOG" "$id: skip — $why"; continue
  fi

  amb_log "$MQ_LOG" "$id: DUE (intended $(mq_get "$id" intended_ist))"
  if [ "$MQ_DRYRUN" = "1" ]; then amb_log "$MQ_LOG" "$id: DRY-RUN — would dispatch"; ran_any=1; continue; fi

  mq_bump_attempt "$id"; mq_set "$id" status running
  mq_set "$id" actual_start "$(TZ=Asia/Kolkata date -d "@$(mq_now_epoch)" '+%FT%T%z')"

  prompt_path="$MQ_PROMPT_DIR/$prompt_file"
  pre="$(bash "$DIR/preflight_auth.sh" "$sources" 2>&1)"; pre_rc=$?
  executor="$(mq_get "$id" executor "${MQ_EXECUTOR_CMD:-}")"

  # Each blocker reports its OWN cause. A missing prompt or a missing executor is
  # NOT an authentication failure, and must never be labelled as one — that sent
  # the owner hunting for expired credentials that were never the problem.
  reason=""; verdict=""
  if [ ! -f "$prompt_path" ]; then
    verdict="BLOCKED — SOURCE PROMPT NOT INSTALLED"
    reason="Source prompt not installed at \`$prompt_path\`. The immutable copy was never supplied, so there is nothing authoritative to execute."
  elif [ "$pre_rc" -ne 0 ]; then
    verdict="BLOCKED — AUTHENTICATED DATA SOURCE UNAVAILABLE"
    reason="One or more required sources ($sources) cannot be reached unattended from this device."
  elif [ -z "$executor" ]; then
    verdict="BLOCKED — NO EXECUTOR CONFIGURED"
    reason="No executor configured. This device has no agent/browser runtime, so it can gate and hand off but cannot interpret a measurement prompt itself. Set MQ_EXECUTOR_CMD or <run_id>.executor."
  fi

  if [ -n "$reason" ]; then
    ev="$(write_blocked_evidence "$id" "$label" "$prompt_path" "$reason" "$pre" "$verdict")"
    mq_set "$id" status blocked; mq_set "$id" verdict "$verdict"
    mq_set "$id" evidence_dir "$ev"
    mq_set "$id" actual_end "$(TZ=Asia/Kolkata date -d "@$(mq_now_epoch)" '+%FT%T%z')"
    amb_log "$MQ_LOG" "$id: ${verdict} — $reason"
    mq_notify "$id" "$label — ${verdict#BLOCKED — }" "$reason $ev"
    ran_any=1; continue
  fi

  # Executor provisioned and preflight clean: hand off. Exit status is authoritative.
  ev="$(mq_evidence_dir "$id")"; mkdir -p "$ev/raw"
  MQ_RUN_ID="$id" MQ_EVIDENCE_DIR="$ev" MQ_PROMPT="$prompt_path" \
    bash -c "$executor" >> "$ev/raw/executor.log" 2>&1; erc=$?
  mq_set "$id" actual_end "$(TZ=Asia/Kolkata date -d "@$(mq_now_epoch)" '+%FT%T%z')"
  mq_set "$id" evidence_dir "$ev"; mq_set "$id" exit_status "$erc"
  if [ "$erc" -eq 0 ]; then
    mq_set "$id" status completed; mq_set "$id" verdict "$(mq_get "$id" verdict COMPLETE)"
    amb_log "$MQ_LOG" "$id: COMPLETED (rc=0)"
    mq_notify "$id" "$label — PASS" "Measurement complete. $ev"
  else
    mq_set "$id" status failed; mq_set "$id" verdict "FAILED (rc=$erc)"
    amb_log "$MQ_LOG" "$id: FAILED rc=$erc"
    mq_notify "$id" "$label — FAILED" "rc=$erc. $ev"
  fi
  ran_any=1
done < "$MQ_QUEUE_FILE"

# Batch-A completion notification once both A1 and A2 have left the pending state.
if [ "$(mq_get ambisecure_gsc_7day_20260829 status)" != "scheduled" ] && \
   [ "$(mq_get ambimat_ga4_gsc_20260829 status)" != "scheduled" ] && \
   [ "$(mq_get ambimat_ga4_gsc_20260829 batch_notified)" != "1" ] && \
   [ -n "$(mq_get ambimat_ga4_gsc_20260829 actual_end)" ]; then
  mq_notify batch_a "29 AUG SEO/GA4 MEASUREMENT BATCH COMPLETE" \
    "AmbiSecure=$(mq_get ambisecure_gsc_7day_20260829 status) Ambimat=$(mq_get ambimat_ga4_gsc_20260829 status)"
  mq_set ambimat_ga4_gsc_20260829 batch_notified 1
fi

bash "$DIR/write_index.sh" 2>/dev/null || true
exit 0

#!/data/data/com.termux/files/usr/bin/bash
# One-shot (calendar-dated) measurement-queue primitives.
#
# The existing lib_common.sh amb_run_if_due() is DAILY-recurring: it keys off an
# HHMM due time plus a <job>_last_success_date marker, so it cannot express
# "run once on 2026-08-27 at 01:00 and never again". This file adds exactly that,
# reusing lib_common's PATH/TZ/logging/locking rather than replacing any of it.
#
# Everything is env-overridable so the tests can run on any host.
: "${MQ_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
: "${MQ_STATE_DIR:=$AMBIMAT_LOGDIR/measurement_state}"
: "${MQ_EVIDENCE_ROOT:=$AMBIMAT_HOME/scheduled_measurements}"
: "${MQ_QUEUE_FILE:=$MQ_DIR/queue.tsv}"
: "${MQ_PROMPT_DIR:=$MQ_DIR/prompts}"
: "${MQ_LOG:=$AMBIMAT_LOGDIR/measurement_queue.log}"
# Deliberate no-run dates (Asia/Kolkata). Space-separated. See master prompt §3.
: "${MQ_BLACKOUT_DATES:=2026-08-28}"
# Bounded retry: at most this many attempts per run_id per IST day (§22).
: "${MQ_MAX_ATTEMPTS_PER_DAY:=6}"
# Daily jobs whose locks we must never compete with (§15, §23).
: "${MQ_FOREIGN_LOCKS:=seo_run site_run cache_monitor_run}"

mkdir -p "$MQ_STATE_DIR" "$MQ_EVIDENCE_ROOT" 2>/dev/null || true

mq_state_file() { echo "$MQ_STATE_DIR/$1.state"; }
mq_get() {  # mq_get <run_id> <key> [default]
  local f; f="$(mq_state_file "$1")"
  [ -f "$f" ] || { echo "${3:-}"; return 0; }
  local v; v="$(grep -m1 "^$2=" "$f" 2>/dev/null | cut -d= -f2-)"
  [ -n "$v" ] && echo "$v" || echo "${3:-}"
}
mq_set() {  # mq_set <run_id> <key> <value>
  local f; f="$(mq_state_file "$1")"; touch "$f" 2>/dev/null || return 1
  grep -v "^$2=" "$f" > "$f.tmp" 2>/dev/null || true
  echo "$2=$3" >> "$f.tmp"; mv "$f.tmp" "$f"
}

# Intended run time -> epoch, always resolved in Asia/Kolkata (§16).
mq_intended_epoch() { TZ=Asia/Kolkata date -d "$1" +%s 2>/dev/null; }
mq_now_epoch()      { echo "${MQ_NOW_EPOCH:-$(date +%s)}"; }
mq_now_date_ist()   { echo "${MQ_NOW_DATE:-$(TZ=Asia/Kolkata date -d "@$(mq_now_epoch)" +%F)}"; }

mq_is_blackout() {  # 0 = today IS a prohibited date
  local d; d="$(mq_now_date_ist)"
  case " $MQ_BLACKOUT_DATES " in *" $d "*) return 0 ;; *) return 1 ;; esac
}

mq_foreign_lock_held() {  # 0 = a daily job holds its lock; defer to it
  local n
  for n in $MQ_FOREIGN_LOCKS; do
    [ -d "$AMBIMAT_LOGDIR/.${n}.lock" ] && { echo "$n"; return 0; }
  done
  return 1
}

mq_attempts_today() {
  local d; d="$(mq_now_date_ist)"
  [ "$(mq_get "$1" attempts_date)" = "$d" ] && mq_get "$1" attempts 0 || echo 0
}
mq_bump_attempt() {
  local d n
  d="$(mq_now_date_ist)"
  n=$(( $(mq_attempts_today "$1") + 1 ))
  mq_set "$1" attempts_date "$d"; mq_set "$1" attempts "$n"
  mq_set "$1" last_attempt "$(TZ=Asia/Kolkata date -d "@$(mq_now_epoch)" '+%FT%T%z')"
}

# mq_why_not_due <run_id> <due_ist> <depends_on>
# echoes "" and returns 0 when the job SHOULD run now; else echoes the reason.
mq_why_not_due() {
  local id="$1" due="$2" dep="$3" st intended now
  st="$(mq_get "$id" status scheduled)"
  [ "$st" = "completed" ] && { echo "already completed"; return 1; }
  mq_is_blackout && { echo "blackout date $(mq_now_date_ist) — prohibited (master prompt §3)"; return 1; }
  intended="$(mq_intended_epoch "$due")"; now="$(mq_now_epoch)"
  [ -z "$intended" ] && { echo "unparseable due time '$due'"; return 1; }
  [ "$now" -lt "$intended" ] && { echo "before due time (now=$now < due=$intended)"; return 1; }
  if [ -n "$dep" ] && [ "$dep" != "-" ]; then
    [ "$(mq_get "$dep" status)" = "completed" ] || { echo "dependency '$dep' not completed"; return 1; }
  fi
  [ "$(mq_attempts_today "$id")" -ge "$MQ_MAX_ATTEMPTS_PER_DAY" ] && \
    { echo "attempt budget exhausted for $(mq_now_date_ist)"; return 1; }
  echo ""; return 0
}

mq_evidence_dir() {  # deterministic per run_id
  echo "$MQ_EVIDENCE_ROOT/$1"
}

mq_notify() {  # mq_notify <id-suffix> <title> <content>   (§21 — detached, never holds stdout)
  command -v termux-notification >/dev/null 2>&1 || return 0
  termux-notification --id "ambimat_measure_$1" --title "$2" --content "$3" \
    >/dev/null 2>&1 </dev/null || true
}

#!/data/data/com.termux/files/usr/bin/bash
# Standalone API executor — the MQ_EXECUTOR_CMD backend for the measurement queue.
#
# Called by run_measurement_queue.sh with MQ_RUN_ID / MQ_EVIDENCE_DIR / MQ_PROMPT
# in the environment.  Label and sources come from queue.tsv, so the queue runner
# itself needs no change.  Everything downstream of here is read-only by
# construction: see api/guard.py.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
QUEUE="${MQ_QUEUE_FILE:-$DIR/queue.tsv}"
ID="${MQ_RUN_ID:?MQ_RUN_ID not set}"
EV="${MQ_EVIDENCE_DIR:?MQ_EVIDENCE_DIR not set}"
PROMPT="${MQ_PROMPT:-}"

row="$(awk -F'\t' -v id="$ID" '$1==id {print; exit}' "$QUEUE")"
[ -z "$row" ] && { echo "run_id $ID not in $QUEUE"; exit 2; }
LABEL="$(printf '%s' "$row" | cut -f5)"
SOURCES="$(printf '%s' "$row" | cut -f6)"

# Keep the CPU awake for the duration; the daily jobs use the same primitive.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock 2>/dev/null || true
cd "$DIR/api" || exit 2
python3 execute.py "$ID" "$LABEL" "$PROMPT" "$EV" "$SOURCES"
rc=$?
command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock 2>/dev/null || true
exit $rc

#!/usr/bin/env bash
# pull_logs.sh — copy telemetry logs from the phone to the Mac over the USB SSH bridge.
# Safe & repeatable: read-only on the phone side (scp copy), never deletes remote files.
set -u

PHONE_USER="u0_a122"
KEY="${HOME}/.ssh/id_moto_playground"
PORT=8022
REMOTE_DIR="moto_playground_logs"          # ~/moto_playground_logs on the phone
DEST="$(cd "$(dirname "$0")/.." && pwd)/logs"   # repo logs/ on the Mac

mkdir -p "$DEST"

# Ensure a device + USB port-forward (idempotent).
if ! adb get-state >/dev/null 2>&1; then
  echo "No adb device connected. Plug in the phone and retry." >&2
  exit 1
fi
adb forward tcp:${PORT} tcp:${PORT} >/dev/null
echo "USB forward active: localhost:${PORT} -> phone:${PORT}"

echo "Pulling ~/${REMOTE_DIR}/ -> ${DEST}/ ..."
scp -i "$KEY" -P "$PORT" \
    -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
    -r "${PHONE_USER}@127.0.0.1:${REMOTE_DIR}/*" "${DEST}/" 2>&1

echo
echo "Local logs now in: ${DEST}"
ls -lt "${DEST}" | head -20

#!/data/data/com.termux/files/usr/bin/bash
# check_termux_api.sh — probe Termux:API one-shot commands (runs inside Termux).
# Each call is wrapped in a timeout so a MISSING companion app cannot hang the shell.
# Does NOT start continuous sensor streams. Does NOT start continuous GPS.
set -u

TIMEOUT_BIN="$(command -v timeout || true)"
to() { if [ -n "$TIMEOUT_BIN" ]; then "$TIMEOUT_BIN" "$@"; else shift; "$@"; fi; }
have() { command -v "$1" >/dev/null 2>&1; }

echo "== Termux:API probe =="
echo "Note: these commands need BOTH the 'termux-api' package AND the Termux:API"
echo "companion app (APK). If a call times out or errors, the app is likely missing"
echo "or a runtime permission has not been granted."
echo

echo "--- termux-battery-status (8s timeout) ---"
if have termux-battery-status; then to 8 termux-battery-status 2>&1 || echo "[FAILED/timeout: companion app or permission missing]"
else echo "[not installed]"; fi

echo
echo "--- termux-wifi-connectioninfo (8s timeout) ---"
if have termux-wifi-connectioninfo; then to 8 termux-wifi-connectioninfo 2>&1 || echo "[FAILED/timeout]"
else echo "[not installed]"; fi

echo
echo "--- termux-sensor -l  (list sensors only, 8s timeout) ---"
if have termux-sensor; then to 8 termux-sensor -l 2>&1 || echo "[FAILED/timeout]"
else echo "[not installed]"; fi

echo
echo "--- termux-location -p network (single fix, 20s timeout) ---"
echo "    Only attempted as a one-shot NETWORK fix (no continuous GPS)."
echo "    If a location permission prompt appears on the phone, STOP and approve it there."
if have termux-location; then to 20 termux-location -p network 2>&1 || echo "[FAILED/timeout: needs location permission granted to Termux:API app]"
else echo "[not installed]"; fi

echo
echo "== probe complete =="

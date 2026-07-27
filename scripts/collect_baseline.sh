#!/data/data/com.termux/files/usr/bin/bash
# collect_baseline.sh — one-shot, no-root device telemetry for the Moto G4 Plus.
#
# Runs INSIDE Termux (app uid, unrooted). It collects everything reachable
# without root and degrades gracefully when a source is unavailable.
#
# Reality of an unrooted Termux app uid on this device (verified):
#   WORKS : getprop, df, /proc/meminfo, /system/bin/ip, ifconfig, uname
#   NEEDS Termux:API app : battery, wifi RSSI, sensors, location
#   BLOCKED for app uid : dumpsys (perm denied), /sys/.../power_supply (perm denied)
#     -> those richer items are best captured from the Mac via `adb shell dumpsys ...`
#
# Safe & repeatable: read-only, no root, no wakelocks, no continuous sampling.
# set -u to catch typos; NOT set -e because several probes are expected to fail.
set -u

LOGDIR="${HOME}/moto_playground_logs"
mkdir -p "$LOGDIR"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="${LOGDIR}/baseline_${TS}.txt"

# Prefer Termux coreutils `timeout` so a missing Termux:API app can't hang us.
TIMEOUT_BIN="$(command -v timeout || true)"
run_to() {  # run_to <seconds> <cmd...>  -> run with timeout if available
  if [ -n "$TIMEOUT_BIN" ]; then "$TIMEOUT_BIN" "$@"; else shift; "$@"; fi
}

section() { printf '\n===== %s =====\n' "$1"; }

# have <name-or-path> : is it a runnable command or executable path?
have() { command -v "$1" >/dev/null 2>&1 || [ -x "$1" ]; }

# Everything below is tee'd to both stdout and the timestamped file.
{
  echo "Moto Playground baseline telemetry"
  echo "collected_at: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "epoch: $(date +%s)"
  echo "host_uid: $(id -u) ($(id -un 2>/dev/null || echo '?'))"

  section "uname"
  uname -a 2>&1

  section "device identity (getprop)"
  for p in ro.product.manufacturer ro.product.model ro.product.device \
           ro.build.version.release ro.build.version.sdk \
           ro.build.version.security_patch ro.product.cpu.abi ro.build.fingerprint; do
    printf '%-32s %s\n' "$p" "$(getprop "$p" 2>/dev/null)"
  done

  section "storage (df -h)"
  df -h 2>&1 || echo "[df failed]"

  section "memory (/proc/meminfo, first 20)"
  head -20 /proc/meminfo 2>&1 || echo "[meminfo unreadable]"

  section "network — ip addr"
  if have /system/bin/ip; then /system/bin/ip -o addr 2>&1
  elif have ifconfig; then ifconfig 2>&1
  else echo "[no ip/ifconfig available]"; fi

  section "network — default route"
  if have /system/bin/ip; then /system/bin/ip route 2>&1; else echo "[ip route unavailable]"; fi

  section "battery — termux-battery-status (needs Termux:API app)"
  if have termux-battery-status; then
    run_to 8 termux-battery-status 2>&1 || echo "[termux-battery-status failed/timed out — is the Termux:API app installed & permitted?]"
  else
    echo "[unavailable: termux-battery-status not installed]"
  fi

  section "wifi — termux-wifi-connectioninfo (needs Termux:API app)"
  if have termux-wifi-connectioninfo; then
    run_to 8 termux-wifi-connectioninfo 2>&1 || echo "[termux-wifi-connectioninfo failed/timed out]"
  else
    echo "[unavailable: termux-wifi-connectioninfo not installed]"
  fi

  section "sensors — termux-sensor -l (list only, no streaming)"
  if have termux-sensor; then
    run_to 8 termux-sensor -l 2>&1 || echo "[termux-sensor failed/timed out]"
  else
    echo "[unavailable: termux-sensor not installed]"
  fi

  section "dumpsys (expected UNAVAILABLE from app uid — informational)"
  if have /system/bin/dumpsys; then
    run_to 6 /system/bin/dumpsys battery 2>&1 | head -8 || echo "[dumpsys blocked for app uid — use adb shell dumpsys from the Mac]"
  else
    echo "[dumpsys not on PATH for app uid — use 'adb shell dumpsys ...' from the Mac instead]"
  fi

  section "cameras (metadata only — no capture)"
  # Camera feature flags via getprop are limited; report what pm knows if reachable.
  if have /system/bin/pm; then
    run_to 6 /system/bin/pm list features 2>&1 | grep -i camera || echo "[pm not permitted from app uid]"
  else
    echo "[camera inventory best read via adb: 'adb shell dumpsys media.camera']"
  fi

  echo
  echo "===== END (file: ${OUT}) ====="
} 2>&1 | tee "$OUT"

echo
echo "Saved: $OUT"

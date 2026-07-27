#!/data/data/com.termux/files/usr/bin/env python3
"""telemetry_loop.py — safe, no-root periodic telemetry logger for the Moto G4 Plus.

Runs INSIDE Termux (Python 3). Writes both JSONL and CSV. Conservative by default
(60s interval, 10min duration) to avoid draining the battery. Foreground only —
no wakelocks, no background daemon, no root. Ctrl+C stops cleanly and flushes.

Data per sample (each source degrades to null if unavailable):
  ts_iso, ts_epoch          always
  battery_*                 via termux-battery-status if the Termux:API app is present
  wifi_*                    via termux-wifi-connectioninfo if available
  mem_avail_kb, mem_total_kb  from /proc/meminfo (always)
  disk_avail_kb (/data)     from statvfs (always)
  ip_wlan0                  from /system/bin/ip (usually available)
  sensor_*                  one-shot reads via termux-sensor if available (unless --no-sensors)

Usage:
  python telemetry_loop.py [--interval N] [--duration N] [--output-dir DIR]
                           [--no-location] [--no-sensors]
"""
import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
DEFAULT_OUTDIR = os.path.join(HOME, "moto_playground_logs")

_stop = False
# Set once at startup by probe_termux_api(): True only if the Termux:API companion
# app actually responds. When False we skip battery/wifi/sensor calls entirely so a
# missing app can't add ~8s of timeout per source on every single sample.
API_AVAILABLE = False


def _handle_sigint(signum, frame):
    global _stop
    _stop = True
    print("\n[telemetry] stop requested — finishing current sample and flushing…",
          file=sys.stderr)


def have(cmd):
    return shutil.which(cmd) is not None


def run_json(cmd, timeout):
    """Run a command expected to emit JSON; return dict or None on any failure."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return json.loads(out.stdout)
    except Exception:
        return None


def run_text(cmd, timeout):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if out.returncode != 0:
            return None
        return out.stdout
    except Exception:
        return None


def read_meminfo():
    """Return (total_kb, avail_kb). This device's 3.10 kernel has no 'MemAvailable:'
    (added in kernel 3.14), so fall back to 'MemFree:' when it is absent."""
    total = avail = free = None
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
                elif line.startswith("MemFree:"):
                    free = int(line.split()[1])
    except Exception:
        pass
    return total, (avail if avail is not None else free)


def disk_avail_kb(path="/data"):
    try:
        st = os.statvfs(path)
        return (st.f_bavail * st.f_frsize) // 1024
    except Exception:
        return None


def wlan_ip():
    for ipbin in ("/system/bin/ip", "ip"):
        out = run_text([ipbin, "-o", "-f", "inet", "addr", "show", "wlan0"], 6)
        if out:
            for tok in out.split():
                if "/" in tok and tok[0].isdigit():
                    return tok.split("/")[0]
    return None


def probe_termux_api():
    """One-shot check: does the Termux:API companion app actually respond?
    Sets the module-level API_AVAILABLE so per-sample calls are skipped when it's absent."""
    global API_AVAILABLE
    if not have("termux-battery-status"):
        API_AVAILABLE = False
        return False
    API_AVAILABLE = run_json(["termux-battery-status"], 6) is not None
    return API_AVAILABLE


def collect_battery():
    if not API_AVAILABLE or not have("termux-battery-status"):
        return {}
    d = run_json(["termux-battery-status"], 8)
    if not d:
        return {}
    return {
        "battery_pct": d.get("percentage"),
        "battery_status": d.get("status"),
        "battery_temp_c": d.get("temperature"),
        "battery_current_ua": d.get("current"),
        "battery_plugged": d.get("plugged"),
    }


def collect_wifi():
    if not API_AVAILABLE or not have("termux-wifi-connectioninfo"):
        return {}
    d = run_json(["termux-wifi-connectioninfo"], 8)
    if not d:
        return {}
    return {
        "wifi_ssid": d.get("ssid"),
        "wifi_rssi": d.get("rssi"),
        "wifi_link_mbps": d.get("link_speed_mbps"),
        "wifi_freq_mhz": d.get("frequency_mhz"),
        "wifi_ip": d.get("ip"),
    }


def collect_sensors():
    """One-shot read of a couple of low-cost sensors (accelerometer, light) if available.
    Uses termux-sensor -n 1 so it never streams continuously."""
    if not API_AVAILABLE or not have("termux-sensor"):
        return {}
    out = {}
    for name, key in (("accelerometer", "accel"), ("light", "light")):
        d = run_json(["termux-sensor", "-s", name, "-n", "1"], 8)
        if isinstance(d, dict):
            # termux-sensor returns {"<Full Sensor Name>": {"values": [...]}}
            try:
                first = next(iter(d.values()))
                out[f"sensor_{key}"] = first.get("values")
            except Exception:
                out[f"sensor_{key}"] = None
    return out


def collect_sample(args):
    now = datetime.now(timezone.utc).astimezone()
    total, avail = read_meminfo()
    row = {
        "ts_iso": now.isoformat(timespec="seconds"),
        "ts_epoch": int(now.timestamp()),
        "mem_total_kb": total,
        "mem_avail_kb": avail,
        "disk_avail_kb": disk_avail_kb("/data"),
        "ip_wlan0": wlan_ip(),
    }
    row.update(collect_battery())
    row.update(collect_wifi())
    if not args.no_sensors:
        row.update(collect_sensors())
    return row


def main():
    ap = argparse.ArgumentParser(description="Safe no-root telemetry loop (Termux).")
    ap.add_argument("--interval", type=int, default=60, help="seconds between samples (default 60)")
    ap.add_argument("--duration", type=int, default=600, help="total seconds to run (default 600)")
    ap.add_argument("--output-dir", default=DEFAULT_OUTDIR, help="where to write logs")
    ap.add_argument("--no-location", action="store_true", help="(reserved) never sample GPS")
    ap.add_argument("--no-sensors", action="store_true", help="skip one-shot sensor reads")
    args = ap.parse_args()

    # We never sample location in this script regardless of the flag (safety default).
    if not args.no_location:
        print("[telemetry] note: location sampling is disabled in this script by design; "
              "use check_termux_api.sh for a supervised one-shot fix.", file=sys.stderr)

    # Probe the Termux:API app once; if absent, battery/wifi/sensor are skipped so
    # each sample stays fast instead of burning ~8s per source on timeouts.
    probe_termux_api()
    print(f"[telemetry] Termux:API companion app: "
          f"{'available' if API_AVAILABLE else 'NOT available (battery/wifi/sensors skipped)'}",
          file=sys.stderr)

    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = os.path.join(args.output_dir, f"telemetry_{stamp}.jsonl")
    csv_path = os.path.join(args.output_dir, f"telemetry_{stamp}.csv")

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)

    # Fixed CSV header (superset of possible keys) so columns stay stable.
    fields = ["ts_iso", "ts_epoch", "battery_pct", "battery_status", "battery_temp_c",
              "battery_current_ua", "battery_plugged", "wifi_ssid", "wifi_rssi",
              "wifi_link_mbps", "wifi_freq_mhz", "wifi_ip", "mem_total_kb",
              "mem_avail_kb", "disk_avail_kb", "ip_wlan0", "sensor_accel", "sensor_light"]

    print(f"[telemetry] interval={args.interval}s duration={args.duration}s "
          f"-> {jsonl_path}")
    start = time.time()
    n = 0
    with open(jsonl_path, "w") as jf, open(csv_path, "w", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        while not _stop:
            row = collect_sample(args)
            jf.write(json.dumps(row) + "\n"); jf.flush()
            writer.writerow(row); cf.flush()
            n += 1
            bat = row.get("battery_pct")
            print(f"[{row['ts_iso']}] #{n} mem_avail={row['mem_avail_kb']}kB "
                  f"disk_avail={row['disk_avail_kb']}kB ip={row['ip_wlan0']} "
                  f"batt={bat if bat is not None else 'n/a'} "
                  f"rssi={row.get('wifi_rssi', 'n/a')}")
            if _stop:
                break
            if time.time() - start + args.interval > args.duration:
                break
            # Sleep in small slices so Ctrl+C is responsive.
            slept = 0.0
            while slept < args.interval and not _stop:
                time.sleep(min(1.0, args.interval - slept))
                slept += 1.0

    print(f"[telemetry] done: {n} samples")
    print(f"[telemetry] jsonl: {jsonl_path}")
    print(f"[telemetry] csv:   {csv_path}")


if __name__ == "__main__":
    main()

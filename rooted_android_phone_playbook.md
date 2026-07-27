# Rooted Android Phone Playbook

> **Canonical repo (2026-07-01):** `/Users/neelshah/Documents/git_repo/rooted-phone/`. Scripts in `scripts/`, docs in `docs/`, Mac-side logs in `logs/`, downloaded APKs in `downloads/`. Historical references below to `~/moto_playground/...` are the pre-migration location, now mirrored here. Phone-side logs remain in Termux at `~/moto_playground_logs/`.

> ⚠️ **Key correction from discovery:** Despite the "rooted phone" premise, this device shows **NO root** (no `su` binary, no root-manager app, verified boot = `green`, `ro.secure=1`, `ro.debuggable=0`). See Findings + Phase 2. All root-dependent plans are gated on this.

## Device Summary

* Date: 2026-07-01
* Mac host: macOS (Darwin 25.5.0, x86_64), adb at /usr/local/bin/adb
* ADB available: YES — Android Debug Bridge 1.0.41 (platform-tools 37.0.0)
* Device detected: YES — serial `ZY22382BFL`, state `device` (authorized), USB
* Manufacturer: motorola
* Model: Moto G (4) — hardware indicates **Moto G4 Plus** (fingerprint sensor + ~3 GB RAM present)
* Device codename: athene_f (athene family)
* Android version: 7.0 (Nougat)
* SDK level: 24
* Build fingerprint: motorola/athene_f/athene_f:7.0/NPJS25.93-14-18/3:user/release-keys
* Security patch: 2018-04-01 (⚠️ ~7 years old — treat as internet-unsafe)
* CPU ABI: armeabi-v7a (32-bit ARM); abilist: armeabi-v7a,armeabi. SoC: Qualcomm msm8952 (Snapdragon 617)
* Root state: **MISSING / not detected** (see Findings)
* Bootloader state: **likely LOCKED** — `ro.boot.verifiedbootstate=green`; `ro.bootloader=0xB107`; `flash.locked`/`vbmeta.device_state` empty (not exposed on this build)
* Storage: /data 25 GB (21 GB free, 17% used); /system 2.3 GB (75% used); shared storage = /storage/emulated (25 GB)
* Battery: 49%, AC-charging, health GOOD, Li-ion, 4.144 V, 30.7 °C, present
* Network: Wi-Fi ENABLED + connected (SSID Ambimat_Guest, RSSI -57 dBm, 2.4 GHz, 72 Mbps); BT ENABLED (STATE_ON, "Moto G (4)"); Wi-Fi Direct + BLE supported; GSM+CDMA telephony hardware present
* Sensors: 21 h/w sensors — accel, gyro (+uncal), light, proximity (+rear), step detector/counter, gravity, linear-accel, game-rotation-vector (fusion), Moto gesture sensors. **NO magnetometer/compass, NO barometer, NO ambient temp/humidity.**
* Cameras: 2 — Camera 0 BACK, Camera 1 FRONT (legacy HAL v0x100); autofocus + flash present
* NFC: **ABSENT** — no `android.hardware.nfc` feature, no NFC in feature list
* GPS/location: GPS + network + passive + fused providers all present; `android.hardware.location.gps` feature present
* Notes: USB currently in `mtp,adb`; USB **host/OTG** + accessory features present. Fingerprint hardware present.

## Safety Rules

* No wipe/factory reset
* No flashing
* No partition writes
* No bootloader changes
* No Magisk/module changes without approval
* No personal accounts or sensitive data
* Prefer LAN-only experiments

## Command Log

| Phase | Command | Purpose | Result |
| ----- | ------- | ------- | ------ |
| 1 | `which adb; adb version` | Confirm ADB present | Found /usr/local/bin/adb, v1.0.41 / pt 37.0.0 |
| 1 | `adb kill-server; adb start-server; adb devices -l` | Restart daemon, list devices | 1 device `ZY22382BFL` authorized (`device`), athene_f |
| 2 | `adb shell getprop <ro.product.*, ro.build.*, ro.boot.*, ro.bootloader>` | Device identity, build, bootloader | Moto G(4) athene_f, Android 7.0, SDK 24, patch 2018-04-01, verifiedbootstate=green |
| 2 | `adb shell uname -a` | Kernel | Linux 3.10.84 SMP armv7l (built 2018-03-28) |
| 2 | `adb shell id` | Shell privilege | uid=2000(shell) — unprivileged |
| 2 | `adb shell command -v su` / broad `ls` of su paths | Detect root binary | none found (`/sbin` denied but no su elsewhere) |
| 2 | `adb shell pm list packages \| grep -i magisk/supersu/...` | Detect root manager | none installed |
| 2 | `adb shell su -c id` | Test root | `su: not found` (exit 127) |
| 2 | `adb shell getprop ro.debuggable/ro.secure/service.adb.root` | Debug/secure flags | ro.debuggable=0, ro.secure=1 |
| 3 | `adb shell dumpsys battery` | Battery health | 49%, AC charging, health GOOD, 30.7°C |
| 3 | `adb shell df -h` | Storage | /data 21 GB free of 25 GB |
| 3 | `adb shell cat /proc/meminfo` | RAM | MemTotal ~2.95 GB, ~403 MB free, 512 MB swap |
| 3 | `adb shell dumpsys wifi` | Wi-Fi state | Enabled, connected -57 dBm 2.4 GHz |
| 3 | `adb shell dumpsys bluetooth_manager` | BT state | STATE_ON, addr A4:70:D6:7A:4D:A6 |
| 3 | `adb shell dumpsys media.camera` | Cameras | 2 (back+front), legacy HAL |
| 3 | `adb shell dumpsys location` | Location providers | gps/network/passive/fused present |
| 3 | `adb shell dumpsys usb` | USB mode | mtp,adb; connected+configured; host state present |
| 3 | `adb shell pm list features \| grep -i nfc` | NFC | NO NFC FEATURE |
| 4 | `adb shell dumpsys sensorservice` | Sensor inventory | 21 sensors (list below) |
| 4 | `adb shell pm list features` | Hardware feature flags | see Capability Matrix |
| 6 | `adb shell pm list packages \| grep termux/fdroid; ip addr wlan0` | Pre-install check + phone IP | none installed; phone IP 192.168.5.197 |
| 6 | `curl -sL <termux GitHub release> ; shasum -a 256` | Fetch + verify official Termux APK | SHA-256 matched published sums ✅ |
| 6 | `adb install -r termux-v7a.apk` | Install Termux (approved) | Success — com.termux 0.118.3 |
| 6 | `adb shell monkey -p com.termux ... LAUNCHER` | First-run bootstrap | Bootstrap OK, prompt reached |
| 6 | `adb shell input text ... keyevent 66` | Drive Termux over USB (pkg install openssh, key inject, sshd) | openssh installed; authorized_keys byte-exact; sshd up |
| 6 | `ssh-keygen -t ed25519 -f ~/.ssh/id_moto_playground -N ""` | Dedicated Mac keypair | Created |
| 6 | `adb forward tcp:8022 tcp:8022` | USB bridge for SSH | Forward active |
| 6 | `ssh -i ~/.ssh/id_moto_playground -p 8022 u0_a122@127.0.0.1` | Verify SSH login | ✅ SSH_LOGIN_OK (key auth) |

## Findings

| Area | Finding | Status | Notes |
| ---- | ------- | ------ | ----- |
| ADB link | Authorized `device` over USB | ✅ OK | serial ZY22382BFL |
| Identity | Moto G4 Plus (athene_f), Android 7.0, SDK 24 | ✅ OK | msm8952 / SD617, armv7 32-bit |
| Root | No su, no root manager, `su: not found` | ❌ NOT ROOTED | Contradicts "rooted" premise — confirm with user |
| Bootloader | verifiedbootstate=green | 🔒 Likely LOCKED | flash.locked prop not exposed; inconclusive but green ⇒ locked+verified |
| Security patch | 2018-04-01 | ⚠️ Stale | ~7 yrs old; keep off untrusted networks, LAN-only |
| Battery | Charging, health GOOD, 30.7°C | ✅ OK | 49% at inspection |
| Storage | 21 GB free on /data | ✅ Ample | good for logging/server use |
| RAM | ~2.95 GB total | ✅ Good | comfortable for Termux/servers |
| Wi-Fi | Enabled + connected, Wi-Fi Direct | ✅ OK | 2.4 GHz link |
| Bluetooth | STATE_ON, BLE supported | ✅ OK | good for BLE scanner |
| Cameras | 2 (front/back), flash, autofocus | ✅ OK | IP-cam / QR viable |
| GPS | gps provider + hardware feature | ✅ OK | GPS logger viable |
| USB OTG | usb.host + usb.accessory features | ✅ Present | serial/OTG experiments viable |
| Fingerprint | android.hardware.fingerprint | ✅ Present | confirms G4 Plus |
| NFC | absent | ❌ None | rules out NFC projects |
| Magnetometer | absent | ❌ None | no compass; no true 9-axis orientation/AR heading |
| Barometer | absent | ❌ None | no altitude/pressure logging |
| Temp/Humidity sensor | absent | ❌ None | no environmental logging |

## Capability Matrix

| Capability | Available | Evidence | Possible Uses |
| ---------- | --------: | -------- | ------------- |
| Wi-Fi | ✅ | feature wifi + connected -57 dBm | Pocket server, RSSI logger, dashboard |
| Wi-Fi Direct | ✅ | feature wifi.direct | P2P experiments |
| Bluetooth / BLE | ✅ | feature bluetooth, bluetooth_le; STATE_ON | BLE scanner/beacon test |
| Camera (back+front) | ✅ | media.camera: 2 devices; flash, AF | IP camera, QR/barcode scanner |
| GPS | ✅ | feature location.gps; gps provider | GPS logger |
| Network location | ✅ | feature location.network | assisted location |
| Accelerometer | ✅ | Bosch, 100 Hz | motion logging, tilt |
| Gyroscope | ✅ | Bosch, 200 Hz (+uncalibrated) | rotation sensing |
| Light sensor | ✅ | TAOS ambient light | lux logger |
| Proximity (+rear) | ✅ | TAOS + rear proximity | presence detect |
| Step detector/counter | ✅ | Bosch; feature stepcounter/stepdetector | pedometer logger |
| Gravity / Linear accel | ✅ | Motorola fusion sensors | motion analytics |
| Game rotation vector | ✅ (no-mag) | fusion; 9-axis disabled | relative orientation only |
| Moto gesture sensors | ✅ | flat/stowed/chopchop/glance/motion | novelty automation |
| Fingerprint | ✅ | feature fingerprint | local auth experiments |
| USB host / OTG | ✅ | feature usb.host + usb.accessory | serial terminal, OTG peripherals |
| Telephony (GSM/CDMA) | ✅ (hw) | feature telephony.gsm/cdma | SMS/cell only if SIM inserted |
| Magnetometer / compass | ❌ | not in sensor list; 9-axis fusion disabled | — rules out compass/AR heading |
| Barometer | ❌ | absent | — |
| Ambient temp / humidity | ❌ | absent | — |
| NFC | ❌ | no nfc feature | — rules out NFC read/write |
| Root (su) | ❌ | su not found; ro.secure=1 | — blocks root-only projects |

## Project Backlog

Scores reflect *this* phone: Moto G4 Plus, Android 7.0, **unrooted**, locked bootloader, no NFC/mag/baro, good Wi-Fi/BT/camera/GPS/sensors, 21 GB free, charging.

| Priority | Project | Difficulty | Value | Risk | Requirements | Suitability | Status |
| -------: | ------- | ---------- | ----- | ---- | ------------ | ----------- | ------ |
| 1 | Termux mini Linux box | Low | High | Low | Termux (F-Droid) | ✅ Ideal — no root needed, ample RAM/storage | ✅ DONE (v0.118.3) |
| 2 | SSH-accessible pocket server | Low | High | Low | Termux + openssh, LAN | ✅ Ideal — key auth working over USB bridge | ✅ DONE (verify LAN needs same non-guest net) |
| 3 | Wi-Fi RSSI / scan logger | Low | Med | Low | Termux `termux-wifi-*` or app | ✅ Good — Wi-Fi strong, API on A7 works | Backlog |
| 4 | Sensor data logger (accel/gyro/light/steps) | Low | Med-High | Low | Termux:API or SensorLogger app | ✅ Good — rich sensor set (minus mag/baro) | Backlog |
| 5 | BLE scanner / test node | Med | Med | Low | nRF Connect (F-Droid) or Termux | ✅ Good — BLE supported | Backlog |
| 6 | GPS logger | Med | Med | Low | GPSLogger (F-Droid) | ✅ Good — outdoors/window needed | Backlog |
| 7 | IP camera / lab camera | Med | Med-High | Med | IP Webcam-style app, LAN | ✅ Good — 2 cams + flash; keep LAN-only | Backlog |
| 8 | Wall dashboard / status display | Med | Med | Low | Fully Kiosk / browser + old-device concerns | ✅ OK — plug-in, screen-on | Backlog |
| 9 | Home Assistant companion/dashboard | Med | Med | Med | HA app or WallPanel; needs HA server | ⚠️ App may target newer API; usable as display | Backlog |
| 10 | Serial terminal over USB-OTG | Med-High | Med | Med | OTG cable + USB-serial app; no root ⇒ limited | ⚠️ Partial — many USB-serial apps need root/driver | Backlog |
| 11 | Barcode/QR scanner station | Low | Med | Low | Binary Eye (F-Droid) | ✅ Good — cameras fine | Backlog |
| 12 | Local automation controller | Med | Med | Med | Termux + Tasker/自动化; some hooks need root | ⚠️ Partial without root | Backlog |
| 13 | MQTT sensor node | Med | Med | Low | Termux mosquitto/python + broker | ✅ Good on LAN | Backlog |
| 14 | GitHub/open-source experiment device | Low | Med | Low | Termux + git | ✅ Good | Backlog |
| 15 | NFC reader/writer | — | — | — | NFC hardware | ❌ Not possible — no NFC | Rejected |
| 16 | Custom ROM playground | High | Med | **High** | Unlocked bootloader + flashing | ❌ Blocked by rules + locked bootloader | Rejected/gated |

## Experiment Log

### Phase 1 — ADB connection
ADB present (1.0.41). `adb devices -l` shows one authorized device `ZY22382BFL` (athene_f) over USB. No unauthorized/offline state. ✅ Connected.

### Phase 2 — OS and root inventory
Moto G (4) / athene_f, Android **7.0 (SDK 24)**, security patch **2018-04-01**, build `NPJS25.93-14-18` user/release-keys. SoC Qualcomm msm8952 (SD617), ABI **armeabi-v7a** (32-bit). Kernel 3.10.84 armv7l.
Root: `command -v su` empty; no su in xbin/bin/sbin/vendor/su paths; no Magisk/SuperSU/Superuser/KingRoot package; `su -c id` → `su: not found`; `ro.secure=1`, `ro.debuggable=0`. **Conclusion: NOT rooted / root missing.**
Bootloader: `ro.boot.verifiedbootstate=green` (⇒ verified boot intact, bootloader almost certainly **locked**); `ro.bootloader=0xB107`; `ro.boot.flash.locked` and `ro.boot.vbmeta.device_state` return empty on this build (not conclusive on their own).

### Phase 3 — Hardware checks
Battery: 49%, AC charging, health GOOD, 30.7 °C, 4.144 V — healthy. Storage: /data 25 GB (21 GB free). RAM ~2.95 GB (403 MB free, 512 MB swap). Wi-Fi enabled + connected (-57 dBm, 72 Mbps, 2.4 GHz). Bluetooth STATE_ON. Cameras: 2 (back+front, flash, AF). Location providers gps/network/passive/fused present. USB = mtp,adb, connected+configured; host/accessory features present (OTG-capable). **NFC absent.** All inspected read-only; nothing toggled.

### Phase 4 — Sensor inventory
21 h/w sensors via Motorola sensor HAL:
* **Accelerometer** (Bosch, 100 Hz) ✅
* **Gyroscope** (Bosch, 200 Hz) + uncalibrated ✅
* **Ambient light** (TAOS) ✅
* **Proximity** (TAOS) + **rear proximity** ✅
* **Step detector** + **step counter** (Bosch) ✅
* **Gravity**, **Linear acceleration**, **Game rotation vector** (Motorola/AOSP fusion) ✅
* Moto special sensors: flat-up/flat-down, stowed, camera-activate, chop-chop, glance, motion-detect, stationary-detect
* **Magnetometer/compass: ABSENT** (9-axis fusion disabled — only game rotation vector, no geomagnetic heading)
* **Barometer/pressure: ABSENT**
* **Ambient temperature/humidity: ABSENT**
Feature flags also confirm: fingerprint, bluetooth_le, wifi.direct, usb.host, usb.accessory, telephony gsm+cdma, camera flash/autofocus/front.

### Phase 5 — Project selection
See Project Backlog. Top picks given unrooted + locked + no-NFC + good-connectivity profile: (1) Termux Linux box, (2) SSH pocket server, (3) Wi-Fi RSSI logger, (4) sensor logger. Root-only and NFC and bootloader-flashing projects are rejected/gated.

### Phase 6 — First safe setup — ✅ COMPLETE (approved & verified)
Installed and configured Termux + OpenSSH with dedicated-key auth; verified SSH from the Mac.

**What was installed/changed (all reversible):**
* **Termux v0.118.3** (`com.termux`, armeabi-v7a, minSdk 24) — sideloaded via `adb install` from the official GitHub release. SHA-256 **verified** = `89416397b70f9ff67a0044e8abe6ef82487cd48fcf543e2d23e02688cc541cf0`.
* Inside Termux: `pkg update` (Termux auto-selected working mirrors: grimler.se / termux.3san.dev / mirror.accum.se; most `.edu.cn` mirrors unreachable), then `pkg install openssh` (10.3p1-1) + deps.
* **Auth:** dedicated ed25519 keypair generated on Mac at `~/.ssh/id_moto_playground` (no passphrase, comment `moto-g4-playground`); public key injected into Termux `~/.ssh/authorized_keys` (verified byte-exact via `cat`). Termux user = **`u0_a122`**.
* **sshd** started (Termux default port **8022**); confirmed LISTEN on 0.0.0.0:8022 + :::8022.

**Verification result:** ✅ SSH login from Mac succeeded (key auth, no password) → returned `SSH_LOGIN_OK`, `u0_a122`, `armv7l`, `Moto G (4)`, uptime ~2 days.

**Networking caveat:** Direct Wi-Fi LAN SSH did **not** work — Mac is on `192.168.4.70`, phone on `192.168.5.197` (different /24), and the phone is on **guest Wi-Fi `Ambimat_Guest`** which almost certainly enforces client isolation. Verified path used **ADB USB port-forward** instead: `adb forward tcp:8022 tcp:8022` → `ssh -p 8022 u0_a122@127.0.0.1`. For Wi-Fi SSH, put both devices on the same non-guest network.

**How to reconnect (USB, works today):**
```
adb forward tcp:8022 tcp:8022
ssh -i ~/.ssh/id_moto_playground -p 8022 u0_a122@127.0.0.1
```
(sshd must be running on the phone: open Termux and run `sshd`. It does not auto-start on boot unless `termux-services` + `sv-enable sshd` is configured — not done yet.)

**Not yet done / optional next steps:** auto-start sshd on boot (termux-services), `termux-setup-storage`, `termux-api` for sensor/Wi-Fi scripting, device-info logging script.

### Phase 7 — Moto Playground telemetry logger

**Session date:** 2026-07-01. Goal: first real playground project — a safe, no-root device telemetry logger driven over the USB SSH bridge. Workspace at `~/moto_playground/`.

**Phase 0 — baseline connectivity:** ✅ `adb devices -l` shows `ZY22382BFL` (device). `~/moto-ssh.sh 'whoami'` → `LOGIN_OK`, `u0_a122`, `Moto G (4)` — sshd still running from prior session, USB key auth works.

**Phase 1 — workspace:** Created `~/moto_playground/{scripts,logs,docs}` + `README.md` (device identity, connection, start/stop, log locations, limitations).

**Phase 2 — Termux capability state:** Before this session only `openssh` was installed. `python`, `jq`, and all `termux-*` API tools were **missing**. Installed via Termux `pkg`: `python`, `jq`, `termux-api` (package = CLI shims only). ⚠️ The `termux-api` **companion app (APK)** is NOT installed — its commands will fail/hang until the Termux:API app is added from F-Droid (pending explicit approval).

**Key constraint discovered — what an unrooted Termux app uid (10122, `untrusted_app`) can/can't read:**
| Source | From Termux (app uid) | Notes |
| ------ | --------------------- | ----- |
| `getprop`, `df`, `/proc/meminfo`, `uname` | ✅ works | |
| `/system/bin/ip addr`, `ifconfig` | ✅ works | IP/network info; RSSI not included |
| `dumpsys battery/wifi/location/sensorservice` | ❌ not on PATH / DUMP perm denied | Works only via `adb shell` (shell uid 2000) |
| `/sys/class/power_supply/battery/*` | ❌ permission denied | SELinux blocks untrusted_app |
| battery / wifi-RSSI / sensors / location | ⚠️ only via Termux:API app | requires companion APK + runtime perms |

**Scripts created in `~/moto_playground/scripts/` (all syntax-checked):**
* `collect_baseline.sh` — one-shot Termux collector; robust (`set -u`, graceful degrade), logs to `~/moto_playground_logs/` on phone.
* `pull_logs.sh` — Mac-side `scp` puller over USB bridge → `~/moto_playground/logs/`.
* `check_termux_api.sh` — one-shot Termux:API probe with timeouts (no streaming, no continuous GPS).
* `telemetry_loop.py` — Python 3 JSONL+CSV loop; defaults 60s/10min; args `--interval/--duration/--output-dir/--no-location/--no-sensors`; clean Ctrl+C; no root/wakelocks/background.

**Phase 2 (cont.) — toolchain verified:** Python **3.13.13**, jq **1.8.2**, stdlib OK, all four `termux-*` shims present. (Install pulled in clang/llvm/lld as deps of `python-pip`; two cosmetic `py3compile` "cannot get content" exceptions during setup — known non-fatal Termux trigger issue, apt exit 0.)

**Phase 4 — baseline run:** ✅ `collect_baseline.sh` ran once on the phone; log pulled to `~/moto_playground/logs/baseline_20260701_155653.txt` (3.8 KB). Working sections returned good data (getprop, df → /data 20 GB free, meminfo, `ip addr` → 192.168.5.197, route). termux-api + dumpsys sections degraded gracefully (clear "unavailable" messages, no crash, no perm-denied flood). Confirms the app-uid constraint table above.

**Phase 5 — Termux:API probe:** `check_termux_api.sh` ran. All of `termux-battery-status`, `-wifi-connectioninfo`, `-sensor -l`, `-location -p network` **FAILED/timed out**. `adb shell pm list packages | grep com.termux` → only **`com.termux`** (companion **`com.termux.api` app is NOT installed**). No permission prompt appeared (nothing to prompt without the app). → Battery/Wi-Fi-RSSI/sensors/location remain blocked until the Termux:API app is installed from F-Droid (**pending explicit approval**).

**Phase 6 — telemetry loop smoke test:** `python telemetry_loop.py --interval 10 --duration 30 --no-location`. First run exposed 2 bugs, both fixed:
* `MemAvailable:` absent on this 3.10 kernel (added in 3.14) → added `MemFree` fallback.
* Missing companion app made each sample ~32 s (4× 8 s timeouts) → added a one-time `probe_termux_api()`; when absent, battery/wifi/sensor calls are skipped so samples stay sub-second.
Re-run: ✅ **3 samples at clean 10 s intervals**; JSONL (all lines valid JSON) + CSV (stable 18-col header) written and pulled to `~/moto_playground/logs/`. Sample data: `mem_avail ~100 MB`, `disk_avail ~20.4 GB`, `ip 192.168.5.197`; battery/rssi `null` (graceful).

**Phase 7 — root/bootloader discrepancy (read-only, no rooting attempted):**
| Property | Value |
| -------- | ----- |
| ro.secure | 1 |
| ro.debuggable | 0 |
| ro.boot.verifiedbootstate | green |
| ro.boot.flash.locked | (empty — not exposed on this build) |
| ro.boot.vbmeta.device_state | (empty) |
| ro.bootloader | 0xB107 |
| ro.build.type / tags | user / release-keys |
| SELinux | Enforcing |
| service.adb.root | (empty — adb root unavailable) |
| su binaries (/system/xbin, /system/bin, /sbin) | none |
| root managers (magisk/supersu/…) | none installed |

**Conclusion:** Internally consistent **stock, release-keys, user build with verified boot intact and SELinux enforcing** — the opposite of a rooted device. A persistent root (Magisk) would patch boot and break `verifiedbootstate=green`. Most likely root was never installed, or was fully removed / OTA'd back to stock. `green` also implies the bootloader is currently **locked** (an unlocked Moto bootloader typically reports `orange`). **Treat as unrooted.**

### Phase 9 — Local LLM feasibility (read-only study, 2026-07-01)

Goal: can this Moto G4 Plus run a local LLM on-device? Read-only only — no APK install, no sideload, no model downloads, no battery-heavy runtime tests.

**Device reconfirmation (read-only):**
| Property | Value | LLM implication |
| -------- | ----- | --------------- |
| Android / SDK | 7.0 / 24 | NNAPI needs API 27+ → **absent** |
| CPU ABI | `armeabi-v7a` (32-bit); `abilist64` **empty** | **cannot execute any arm64-v8a `.so`** |
| SoC / GPU | msm8952 (SD617) / Adreno 405 | no Vulkan feature flag → **no GPU delegate** |
| RAM | 2.95 GB total (~200 MB free at rest) | below modern app minimums |
| NNAPI service | none (`service list` has no neuralnetworks) | no NN acceleration |
| GPU/Vulkan feature | none in `pm list features` | CPU-only inference |

**Accelerator reality:** No 64-bit ABI, no NNAPI (API 24), no Vulkan. Any on-device LLM here would be **32-bit CPU-only** on a 2016 mid-range SoC with <3 GB RAM.

**Google AI Edge Gallery (`com.google.ai.edge.gallery`):** Uses the LiteRT / MediaPipe LLM Inference runtime (`.task`/`.litertlm` models, Gemma/Qwen) — the **same LiteRT-LM family** shipped as arm64-v8a-only native libs, and the app targets modern Android (minSdk ≥ 26 / Android 8.0). This device is API 24 + 32-bit-only → **cannot install (minSdk) and cannot run (arm64-only runtime)**. Verdict: **Not viable.** (Not installed/inspected — no APK per rules; based on the shared LiteRT-LM runtime evidence below + known project requirements.)

**dineshsoudagar/local-llms-on-android ("Pocket LLM") — source inspected (shallow clone at `~/moto_playground/external/local-llms-on-android`):**
* `app/build.gradle.kts`: `minSdk = 24`, `targetSdk = 35`, `compileSdk = 35`. Build toolchain **AGP 9.1.1 / Gradle 9.3.1 / Kotlin 2.2.21** (bleeding edge; local build needs latest Android Studio + JDK).
* Runtimes: **ONNX Runtime Android `1.23.2`** + **`com.google.ai.edge.litertlm:litertlm-android:0.10.2`** (LiteRT-LM, **arm64-v8a only**). No `abiFilters` set → ABIs come from the AAR native libs.
* Models (downloaded in-app, not bundled): Gemma 4 E2B/E4B LiteRT (flagship/mid), **Qwen3 0.6B LiteRT (labeled "low-end")**, Qwen3 0.6B Q4F16 ONNX, Qwen2.5 0.5B ONNX.
* **The project's own Requirements section states "4 GB or more RAM for smaller models."** This device has **2.95 GB** → below the author's stated minimum.

**Why Pocket LLM is not usable here despite `minSdk=24`:** The APK would *install* on Android 7.0, but (a) all **LiteRT** models (incl. the "low-end" Qwen3 0.6B) need arm64-v8a native code this device **cannot execute**; (b) the ONNX-only path still needs ≥4 GB RAM (author) and would be 32-bit, CPU-only, no NNAPI/GPU → OOM or unusably slow (seconds–minutes per token). Verdict: **Not viable / not usable on-device.**

**Does APK metadata inspection add anything?** The source already answers minSdk (24), ABI/runtime (ONNX + arm64-only LiteRT-LM), and RAM need (≥4 GB > 2.95 GB). A release-APK unzip would only confirm which ABI `.so` files are bundled — but the **RAM shortfall alone already disqualifies the device**, so inspection is **low value / not worth it** (would need approval to download a release APK regardless).

**Phase 9 verdict — True on-device LLM on Moto G4 Plus: NOT VIABLE.** Root cause: 32-bit-only ABI (no arm64 for LiteRT/MediaPipe), no NNAPI/Vulkan acceleration, and <4 GB RAM. This is a hardware/OS-generation limit, not a config issue.

### Phase 10 — Local LLM path decision and prototype plan

**Options classified (evidence-based):**
* **Option A — True on-device LLM:** ❌ **Not viable** (see Phase 9). Hardware/OS generation limit.
* **Option B — Build/inspect Pocket LLM APK:** ❌ **Not worth doing next.** Source already answers the unknowns; a modern-AGP local build is heavy with no payoff; a release-APK metadata unzip only confirms bundled ABIs while the RAM shortfall already disqualifies the device. (Could be done read-only if a release APK is provided — **needs approval to download** — but recommended **skip**.)
* **Option C — Hybrid: phone UI + Mac-hosted local LLM:** ✅ **Recommended practical path.** Phone = I/O terminal over the existing USB bridge; model runs on the Mac. Documented in `~/moto_playground/docs/local_llm_hybrid_plan.md`.
* **Option D — Newer Android device for true on-device LLM:** ℹ️ Recommendation only (no action). Desired profile: **Android 12+, arm64-v8a, ≥6 GB RAM (8 GB+ preferred), Vulkan/NNAPI, ample storage.** Then AI Edge Gallery / Pocket LLM (LiteRT) become viable.

**Mac-side LLM software presently installed:** none of Ollama / llama.cpp / LM Studio. Only `python3` (3.14.5) and `node`; Homebrew has an `onnx` formula. → Hybrid needs a server engine installed first (**pending approval**; no install/model-download done).

**Tunnel design (for hybrid):** phone→Mac uses **`adb reverse tcp:PORT tcp:PORT`** (listener on phone's `127.0.0.1` → Mac's `127.0.0.1`). Current tunnels: `adb forward tcp:8022→8022` (SSH); `adb reverse` empty. No servers were started this phase.

**Nothing installed, downloaded, sideloaded, or served in Phases 9–10.** External repo cloned as **source only** (no APK, no model) at `~/moto_playground/external/local-llms-on-android`.

### Phase 11 — Alternate-use roadmap after local LLM no-go

Since on-device LLM is ruled out (Phase 9), pivot to projects that fit an unrooted, 32-bit, Android-7, 2.95 GB, no-NFC/compass/baro device with good Wi-Fi/BT/GPS/camera/USB-OTG/sensors. Legend: **Needs API app?** = requires the Termux:API companion (com.termux.api); **Needs APK?** = requires a third-party Android app.

| Priority | Project | Uses Device Capabilities | Needs API app? | Needs APK? | USB-only OK? | Guest-WiFi OK? | Difficulty | Value | Risk | Status | Notes |
|---:|---|---|:--:|:--:|:--:|:--:|---|---|---|---|---|
| 1 | Termux SSH pocket server | CPU, Termux, net | No | No | ✅ | ✅ | Low | High | Low | ✅ DONE | Working over USB (8022); reversible |
| 2 | Telemetry logger (battery/mem/disk/net/sensors) | battery, mem, disk, Wi-Fi, sensors | **Yes** (battery/Wi-Fi/sensors) | No | ✅ | ✅ | Low | High | Low | ⚠️ Partial | mem/disk/net work now; rest blocked on API app |
| 3 | Wi-Fi RSSI / network logger | Wi-Fi | **Yes** (RSSI via termux-wifi-connectioninfo) | No | ✅ | ✅ | Low | Med | Low | ⚠️ Blocked-on-API | Without app: only IP via `ip addr`, no RSSI |
| 4 | BLE scanner / test node | Bluetooth LE | No (Termux:API has **no** BLE cmd) | **Yes** (e.g. nRF Connect) | ✅ (app runs standalone) | ✅ | Med | **High** (Ambimat/Furlink BLE) | Low | 🔎 Plan (Phase 15) | Termux/ADB cannot scan BLE unrooted; needs an app or root |
| 5 | GPS logger | GPS | **Yes** (termux-location) + loc permission | No (or GPSLogger app) | ✅ | ✅ | Med | Med | Low | 🔎 Plan | Needs sky/window view; one-shot fixes safe, continuous = battery |
| 6 | Sensor logger (accel/gyro/light/prox/step) | sensors | **Yes** (termux-sensor) | No | ✅ | ✅ | Low | Med | Low | ⚠️ Blocked-on-API | No mag/baro/temp on this device |
| 7 | MQTT / IoT node | net, Termux python | No | No | ✅ (adb reverse to broker) | ✅ | Med | Med | Low | 🗂 Backlog | `pkg install mosquitto`/paho; publish sensor data |
| 8 | USB-OTG serial terminal | USB-OTG host | No | **Yes** (serial terminal app; Termux can't do USB-serial unrooted) | ✅ | ✅ | Med-High | **High** (ESP32/A7672S) | Low-Med | 🔎 Plan (Phase 16) | Needs OTG + USB-UART dongle (CP2102/CH340/FTDI) |
| 9 | IP / lab camera | camera | one-shot via termux-camera-photo; streaming needs app | **Yes** for streaming (IP Webcam) | ✅ (adb forward) | ✅ | Med | Med | Med (privacy/net) | 🗂 Backlog | 2 cams + flash; keep loopback/LAN-only |
| 10 | QR / barcode scanner utility | camera | termux-camera-photo (capture) | Optional (Binary Eye) | ✅ | ✅ | Med | Med | Low | 🗂 Backlog | Capture via API app + decode with `zbar` in Termux |
| 11 | Home / lab dashboard screen | screen, browser | No | Optional (Fully Kiosk) | ✅ (adb reverse) | ✅ | Med | Med | Low | 🗂 Backlog | Display a Mac-hosted dashboard page; keep plugged in |
| 12 | Mac-hosted LLM client/controller | browser/Termux, net | No | No | ✅ (adb reverse) | ✅ | Low-Med | High | Low | 🗂 Backlog | The only sanctioned "LLM" path; see `docs/local_llm_hybrid_plan.md` |
| 13 | Offline field toolkit | Termux tools | Optional | No | ✅ | ✅ | Low | Med | Low | 🗂 Backlog | Curated Termux set: ssh, python, jq, nmap, tcpdump(*root), git |
| 14 | Android old-version compat test device | whole device | No | test APKs (with approval) | ✅ | ✅ | Low | Med | Low | 🗂 Backlog | Genuine API-24 / 32-bit target for app/web compat testing |

**Top 3 practical next projects (evidence-based):**
1. **Termux:API companion unlock → real telemetry + sensor + Wi-Fi-RSSI logger.** One small install (Phase 12/13) unblocks projects 2, 3, 5, 6, 10 at once — highest leverage, lowest friction, USB-only, reversible.
2. **BLE scanner / test node.** Highest *business* value (BLE work). Evidence caveat: **Termux:API provides no BLE command and unrooted Termux can't scan BLE**, so this needs one F-Droid app (e.g. nRF Connect) — a separate decision from #1. Planned in Phase 15.
3. **USB-OTG serial terminal / embedded lab companion.** High value for ESP32 / A7672S bring-up; needs OTG + USB-UART hardware and one serial-terminal app. Planned in Phase 16.

_(Wi-Fi RSSI and GPS logging are folded into #1 since they come "free" with the Termux:API companion; BLE is called out separately because it does not.)_

### Phase 12 — Termux:API companion app plan

**The blocker:** the `termux-api` **CLI package/shims** are installed in Termux, but the **Android companion app** `com.termux.api` is **not** — so battery/Wi-Fi/sensor/location/camera APIs fail (confirmed Phase 5).

**⚠️ Signature/source constraint (critical):** the installed Termux uses `sharedUserId=com.termux` and was installed from the **GitHub debug** build (v0.118.3). Add-on apps sharing that sharedUserId **must be signed with the identical key**, so the companion **must be the GitHub build too**. Installing the **F-Droid** Termux:API build alongside a GitHub Termux would fail (`INSTALL_FAILED_SHARED_USER_INCOMPATIBLE` / signature mismatch). → Use **github.com/termux/termux-api**, not F-Droid, for this device.

| Field | Value |
| ----- | ----- |
| Package name | `com.termux.api` |
| Official source | GitHub `termux/termux-api` releases (must match the GitHub Termux install) |
| Recommended asset | `termux-api-app_v0.53.0+github.debug.apk` (latest; published 2025-09-01) |
| APK size | ~8.4 MB (8,854,381 bytes) — small, not a "large file" |
| Checksums | `checksums-sha256.txt` published alongside the release (verify before install) |
| Min Android | SDK 24 / Android 7.0 (tracks the Termux app's minSdk) — **to be confirmed** from the APK manifest at install (Phase 13 `dumpsys`) |
| Version pairing | Works with the current `termux-api` CLI package already installed + Termux 0.118.3 |
| Notable permissions | Requested at runtime per API used: LOCATION (termux-location), CAMERA (termux-camera-photo), RECORD_AUDIO (mic), plus storage/contacts/SMS if those APIs are called. Battery/Wi-Fi-info need no runtime prompt. |
| Risks | Low: standalone add-on, no root, no system changes; grants only what you approve per API. Main risk is granting location/camera/mic — approve only what you use. |
| How to verify | `adb shell pm list packages \| grep com.termux.api`; then `termux-battery-status` returns JSON |
| How to uninstall | `adb uninstall com.termux.api` (fully reversible; does not affect Termux) |

**Status: NOT installed. Awaiting explicit approval (Phase 13).**

### Phase 13–14 — Repo migration + Termux:API companion install + real telemetry (2026-07-01)

**Phase 13A — repo migration:** Project migrated to canonical repo `/Users/neelshah/Documents/git_repo/rooted-phone/` (on-disk folder shows as `Rooted-Phone`; macOS case-insensitive FS → same directory). Non-destructive copies (originals kept in `~`): playbook, `README.md`, `scripts/*` (+ `moto-ssh.sh`), `docs/*`, `logs/*`. Path refs updated to repo-relative; `pull_logs.sh` now resolves DEST to repo `logs/`. `external/` (third-party clone) not migrated. No private keys copied (SSH key stays in `~/.ssh`).

**Phase 13B — Termux:API companion install (approved):** Source **github.com/termux/termux-api v0.53.0**, asset `termux-api-app_v0.53.0+github.debug.apk` (8,854,381 B). SHA-256 **verified** = `ecf916ff80ae751e65c092f51c055cce4de417ebeea8e449cd0f294afdbde39a` (matches published `checksums-sha256.txt`). `adb install` → **Success**. Package `com.termux.api` v0.53.0, `versionCode 1002`, **minSdk=24** (Android 7 ✅), targetSdk 28, `primaryCpuAbi=armeabi-v7a`, **`sharedUser=com.termux/10122`** (same uid/signature as the GitHub Termux — signature match confirmed; no conflict). Downloaded APK kept in `downloads/termux-api/` (gitignored).

**Phase 13C — API verification (no location):** Over the USB SSH bridge, **no permission prompt appeared**; all returned data:
* `termux-battery-status` → 87%, CHARGING/AC, GOOD, 39.2 °C, 4354 mV (full JSON).
* `termux-wifi-connectioninfo` → SSID `Ambimat_Guest`, RSSI −62, 2432 MHz, 72 Mbps, IP. (`mac_address` masked `02:00:...` — normal.)
* `termux-sensor -l` → all 21 sensors listed.
`termux-location` **not run** (awaiting explicit approval).

**Phase 14A — 2-minute telemetry session:** `telemetry_loop.py --interval 15 --duration 120 --no-location` (battery 87% & charging). **7 samples**, all fields populated: battery (pct/status/temp/current/plugged), Wi-Fi (ssid/rssi −53…−61/link/freq/ip), mem_avail, disk_avail, ip, plus one-shot `sensor_accel` (z≈9.7 = gravity) and `sensor_light` (~54 lux). JSONL all-valid, CSV stable header. Pulled into repo `logs/`. (`sensor_light` returns a multi-element array; first element ≈ lux — cosmetic, non-blocking.)

**Sensitive-data handling:** raw logs contain a Wi-Fi SSID + private IPs (and baseline `.txt` a MAC-derived IPv6); **no BSSID**. `.gitignore` excludes raw `logs/*.{jsonl,csv,txt}` and `downloads/`; a **redacted** `logs/SAMPLE_telemetry_redacted.jsonl` is kept as committable evidence.

**Not done (await approval):** 30-min telemetry, GPS/`termux-location`, BLE app, USB-serial app, boot auto-start, background services. No git add/commit/push.

### Phase 17 — Site Monitor project (daily website health / hack-indicator / SEO, 2026-07-01)

**Goal:** turn the phone into a daily 10 AM public-crawl monitor for the four Ambimat sites
(`ambimat.com`, `ambisecure.`, `ambiautomation.`, `esim.`) reporting broken pages/links,
defacement/injection/redirect indicators, Japanese/pharma/casino SEO-spam, SEO health, security
headers, TLS expiry, and title drift.

**`claude-seo` review:** the referenced repo is a **Claude Code AI skill** (Playwright/Chromium +
lxml/weasyprint/matplotlib + Google/DataForSEO/Moz APIs + API keys) — **not runnable** on Android 7
/ 32-bit Termux. Built a standalone lightweight crawler *inspired by* its `parse_html.py`,
`parasite_risk.py` (advisory-risk model), `drift_*` (baseline compare), and `url_safety` patterns
instead. Details: `docs/claude_seo_repo_review.md`.

**Implemented:** `site_monitor/` — `run_site_monitor.py` + `render_report.py` + config/keywords +
`run_once.sh`/`run_daily.sh`/`schedule_daily.sh`/`show_latest_report.sh`. Pure `requests` +
`beautifulsoup4` + `PyYAML`, installed on-device (PyYAML wheel built for `android_24_armeabi_v7a`).

**Hang + recovery:** an initial `--max-pages 20` run *appeared* stuck. Diagnosis: the crawl had
**completed** (reports written 17:22:16, 80 pages, 0 alerts) but `termux-notification`/`termux-toast`
spawned `libexec/termux-api` helpers that inherited the SSH stdout fd, so the session never returned.
Fixed: detached notifications (`/dev/null` fds + new session), `(connect,read)` timeouts, per-site +
global time budgets, capped/disableable external-link checks (social hosts skipped), flushed
progress, and always-write-partial-report in a `finally`. Smoke test (3 pages/site) and a bounded
manual crawl (10 pages/site, `--no-external-links`) then ran cleanly with **no hang** and **0
compromise alerts**. Full write-up: `docs/site_monitor_recovery_report.md`,
`docs/site_monitor_daily_plan.md`.

**Not done (await approval):** enabling the daily **10 AM cron** (`schedule_daily.sh install`);
Termux:Boot for reboot persistence; tuning external-link false positives. No git add/commit/push.

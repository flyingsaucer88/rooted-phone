# BLE Scanner Plan — Moto G4 Plus

## Goal
Use the Moto G4 Plus as a BLE scan/test node (e.g. for Ambimat/Furlink-style beacons/devices).

## Constraints
- Android 7.0 (SDK 24), unrooted, bootloader locked
- 32-bit `armeabi-v7a`, ~2.95 GB RAM
- Bluetooth + **BLE present** (`feature android.hardware.bluetooth_le` confirmed earlier)
- BLE scanning on Android 6+ requires **Location permission ON** (fine location) and Location services enabled — an OS rule, not a device limit
- Termux runs in an app sandbox with no Bluetooth-scan API

## Key evidence
- **Termux:API has NO BLE command.** It exposes battery/Wi-Fi/sensor/location/camera/etc., but there is no `termux-bluetooth-scan`. So the planned companion app (Phase 12) does **not** unlock BLE.
- **Unrooted Termux/ADB cannot do a BLE GATT scan.** `adb shell` can toggle the adapter and dump paired state, but there is no unprivileged CLI BLE-scan path on Android 7. (`hcitool`/`bluetoothctl` need BlueZ/root, which Android does not use.)
- Therefore BLE scanning needs a **dedicated Android app** (or root — out of scope).

## Options
| Option | Requires APK? | Requires Root? | Exportable Logs? | Difficulty | Notes |
|---|:--:|:--:|:--:|---|---|
| **nRF Connect for Mobile** (Nordic) | ✅ (F-Droid/official) | No | ✅ CSV/scan export + share | Low (manual) | Best general BLE scanner; works on Android 7; can log adv packets, connect, read GATT |
| **nRF Connect Device Firmware / Toolbox** | ✅ | No | Partial | Low | For specific profiles |
| **BLE Scanner / Beacon apps** (e.g. Beacon Scope, Radar) | ✅ | No | Varies | Low | Simpler; fewer export options |
| Custom minimal Android app (Kotlin, BluetoothLeScanner) | ✅ (self-built) | No | ✅ (you design it) | Med-High | Full control + logfile export to /sdcard; needs Android Studio + build; minSdk 24 fine |
| Termux + root + BlueZ | No APK | **Yes (root)** | ✅ | High | ❌ Not applicable — device is unrooted |
| ADB shell adapter/paired dump | No | No | text only | Low | `dumpsys bluetooth_manager` (via adb, shell uid) — state only, **not** a live adv scan |

## Can this phone be a BLE test node?
- **Scanning/observing beacons:** ✅ yes, via nRF Connect (manual) or a small custom app. Good enough to verify Ambimat/Furlink beacons advertise, read RSSI/adv payloads, and export scans.
- **Acting as a BLE peripheral/beacon (advertise):** ⚠️ possible via a custom app using `BluetoothLeAdvertiser` (chipset supports peripheral mode on many Moto G4 units, but not guaranteed) — needs a built app to confirm.
- **Automated/headless BLE logging:** needs the custom-app route (nRF Connect is interactive).

## Recommendation
- **Fastest useful path:** install **nRF Connect for Mobile** from **F-Droid** (official, Android-7 compatible), scan manually, export logs, pull via `adb pull`/SSH. This is a *standalone* app (no sharedUserId), so the Termux GitHub-signing constraint does **not** apply here.
- **If headless/automated BLE logging is required later:** build a tiny custom `BluetoothLeScanner` app (minSdk 24) that writes CSV to shared storage — more work but scriptable.
- **Prereq for any option:** grant the app Location permission and enable Location services (BLE-scan requirement on Android 7).
- **Do not install any BLE APK yet** — awaiting explicit approval. nRF Connect would be the recommended pick.

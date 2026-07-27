# USB-OTG Serial Terminal Plan — Moto G4 Plus

## Goal
Use the old Android phone as a field serial terminal / debug console for embedded work
(ESP32, A7672S modem, and similar UART debug boards) — a pocket alternative to a laptop.

## Feasibility summary
- `feature android.hardware.usb.host` **is present** on this device (confirmed earlier) → USB-OTG host mode is supported.
- **Termux (unrooted) cannot access USB-serial devices directly.** `/dev/ttyUSB*` is not created without a kernel driver + permissions; Android routes USB devices through the app-level USB Host API. So a **dedicated Android serial-terminal app** is required (it uses `UsbManager` + a userspace driver like usb-serial-for-android — no root needed).
- Note the phone's own USB port is currently used for **ADB over USB**. Plugging a USB-UART dongle via OTG uses the same physical port, so serial work and the ADB/SSH bridge are **mutually exclusive over that port** (you'd operate the phone standalone during serial sessions, then reconnect to the Mac afterward to pull logs).

## Hardware Needed
- **USB-OTG adapter** (USB-C? No — this Moto G4 Plus is **micro-USB OTG**; use a micro-USB-OTG adapter/cable).
- **USB-UART adapter**: CP2102, CH340/CH341, FTDI FT232, or PL2303 (all supported by usb-serial-for-android).
- **Test target**: ESP32 dev board / A7672S module / any 3.3 V UART debug header (mind voltage levels — use 3.3 V logic).

## App / Tool Options
| Tool | Source | Android 7 Support | Log Export | Root? | Risk | Notes |
|---|---|:--:|:--:|:--:|---|---|
| **Serial USB Terminal** (Kai Morich) | F-Droid / official | ✅ | ✅ save/share logs | No | Low | Recommended; supports CP2102/CH340/FTDI/PL2303; configurable baud/parity |
| **CoolTerm / Serial Bluetooth Terminal** family | F-Droid | ✅ | ✅ | No | Low | Same author; BT variant unrelated to USB |
| **DroidTerm / USB Serial Terminal** | Play/F-Droid | ✅ (varies) | Partial | No | Low | Alternatives if the above lacks a driver |
| Custom app (usb-serial-for-android lib) | self-built | ✅ (minSdk 24 fine) | ✅ (you design) | No | Med | Full control + auto-logging; needs Android Studio build |
| Termux `screen`/`picocom` on `/dev/ttyUSB0` | Termux pkg | ❌ unrooted | n/a | **Yes (root)** | — | Not usable here (no device node without root) |

## Baud / protocol support
- App-based drivers handle standard bauds (9600 … 115200 … up to 921600/1.5M depending on dongle + chip). ESP32 boot log is typically **115200**; A7672S AT is typically **115200** (sometimes autobaud).
- Standard 8N1; flow control optional. All handled in-app.

## Log export
- Serial USB Terminal can save session logs to shared storage; retrieve later with `adb pull /sdcard/...` or via the SSH bridge once reconnected to the Mac.

## Recommended First Test (documentation only — not executed)
1. Obtain a **micro-USB OTG adapter** + a **CP2102/CH340 USB-UART** dongle.
2. Install **Serial USB Terminal** (F-Droid) — *pending approval*; standalone app, so the Termux signing constraint does not apply.
3. Connect dongle → OTG → phone; Android should prompt "Open app for this USB device?" → approve (this is the permission prompt to expect).
4. Loopback sanity check: jumper the dongle's TX↔RX, type in the app, confirm echo.
5. Then connect to an ESP32 at 115200 and watch the boot log; save/export the log.

## Notes / caveats
- **Do not install any APK yet** — awaiting approval. Serial USB Terminal (F-Droid) is the recommended pick.
- Serial sessions occupy the micro-USB port → no simultaneous ADB/SSH; plan to pull logs after.
- Powering both the dongle and target from the phone's OTG port draws battery; keep sessions short or power the target externally.

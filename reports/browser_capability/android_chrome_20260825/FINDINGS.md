# Android Chrome capability investigation — 2026-08-25 IST

Device ZY22382BFL / Moto G (4) `athene_f`, Android 7.0 (NPJS25.93-14-18), armv7l.
Read-only investigation. No measurement prompt executed. No website/GA4/GSC/Bing/LinkedIn mutation.

## Root status — the stated premise does not hold

    ro.build.tags        = release-keys
    ro.debuggable        = 0
    ro.secure            = 1
    ro.boot.verifiedbootstate = green
    ro.boot.veritymode   = enforcing
    adb root             -> "adbd cannot run as root in production builds"

No `su` at /sbin, /su/bin, /system/xbin, /system/bin, /system/sbin, /magisk/.core/bin,
/debug_ramdisk or /data/adb. No Magisk/SuperSU/Superuser package installed.
`/system/xbin` contains one file (`dexlist`) — an untouched stock partition.
Termux ships a `su` wrapper on PATH; it reports "No su program found on this device."

**This device is stock and unrooted.** Every conclusion below follows from that.

## Chrome

    package     com.android.chrome
    version     119.0.6045.193  (versionCode 604519320, targetSdk 34)
    codePath    /data/app/com.android.chrome-1/base.apk
                (stock /system/app/Chrome 55.0.2883.91 is the shadowed base APK)
    updated     2026-06-04 08:33:34
    running     yes — pids 32218 (browser), 32316 (sandboxed_process0), 32346 (privileged_process0)

## DevTools socket

`/proc/net/unix` shows the abstract socket, visible from both shell and Termux:

    00000000: 00000002 00000000 00010000 0001 01 5422066 @chrome_devtools_remote

### From the workstation over adb — WORKS

    adb forward tcp:9222 localabstract:chrome_devtools_remote
    GET /json/version -> Chrome/119.0.6045.193, Protocol-Version 1.3, V8 11.9.169.7

WebSocket handshake is rejected with 403 unless the `Origin` header is suppressed
(Chrome 119 `--remote-allow-origins` check). Suppressing Origin is a client-side
change only — no Chrome flag, no command-line file, no root needed.

### From Termux locally — REJECTED

    connect("\0chrome_devtools_remote")  -> succeeds
    first read/write                     -> immediate EOF / ECONNRESET (3/3 attempts)

Chrome's Android DevTools server checks `SO_PEERCRED` and serves only uid 0 (root),
uid 2000 (shell) or its own uid. Termux is uid 10122, so the connection is accepted
at the kernel and dropped by Chrome. Not fixable without root.

### Local adbd loopback bridge — evaluated, not viable

adbd runs as uid 2000 and could have bridged Termux to the socket, but:

    getprop service.adb.tcp.port   -> (empty)
    getprop persist.adb.tcp.port   -> (empty)
    setprop service.adb.tcp.port 5555 (from Termux) -> "failed to set property"

adbd is USB-only. Enabling TCP needs `adb tcpip` from a workstation (lost on every
reboot) or root to set the persist property, plus a one-time on-screen authorisation
tap for the Termux adb key. `android-tools 35.0.2-7` is installable for arch `arm`,
but it has nothing to connect to. This path collapses back into Option C.

## Read-only control proof (over adb, existing benign tab, no navigation)

    tab enumeration   3 targets listed
    activate          PUT /json/activate/4 -> "Target activated"
    title             "Browse Chrome as a guest - Android - Google Chrome Help"
    url               https://support.google.com/chrome/answer/6130773?hl=en
    DOM.getDocument   #document nodeId 1
    element count     534
    innerText         read (first 200 chars)
    scroll            scrollY 400.67 -> 700.67, restored to 400.67
    screenshot        Page.captureScreenshot -> 234788 bytes PNG
                      sha256 73373a5e6a65405b... (cdp_proof_screenshot.png)

No form submitted, no click, no account state touched.

## Authenticated-session probe (one scratch tab, opened and closed)

Device Google account: exactly one, `ravikumar.c@ciright.com` (com.google) — a GMS
device account, not a browser sign-in, and not an Ambimat property owner.

Landing states after navigation, final URL + title only, no cookies read:

| Service | Final URL | Verdict |
| --- | --- | --- |
| GSC | `search.google.com/search-console/about` ("Start now") | SIGNED OUT |
| GA4 | `accounts.google.com/v3/signin/identifier?continue=analytics.google.com...` | SIGNED OUT |
| Bing WMT | `bing.com/webmasters/about?from=home` | SIGNED OUT |
| LinkedIn | `linkedin.com/login/?session_redirect=%2Ffeed%2F` | SIGNED OUT |

Corroborating, without any navigation: the pre-existing tabs were a Google search for
"outlook login", `accounts.google.com/v3/signin/identifier` titled "Google Play", and
the Chrome guest-browsing help page — and support.google.com rendered "Sign in" rather
than an account avatar. The browser was already signed out before this session.

The LinkedIn Android app is not installed.

Tab state restored: 3 tabs before, 3 tabs after, same ids (1, 3, 4).

## Native UI automation from Termux

    /system/bin/input keyevent 0     -> Killed, rc=137 (SELinux; no INJECT_EVENTS)
    /system/bin/uiautomator dump     -> produces no file
    /system/bin/screencap -p FILE    -> 0-byte file (no READ_FRAME_BUFFER)
    /system/bin/dumpsys window       -> "Can't find service: window"
    /system/bin/am start --user 0    -> WORKS (launched about:blank in Chrome)

Termux can launch Chrome and open a URL and nothing else. It cannot see the screen,
dump the view hierarchy, or inject a tap or swipe. Blind launching is not automation.
(The `am start` test opened one about:blank tab; it was closed and tab state restored.)

## Agent / LLM runtime on the phone

Absent: claude, claude-code, node, npm, deno, bun, ollama, llama-cli, aichat, sgpt, llm.
Python 3.13.13 present; `requests` and `bs4` present. Absent: anthropic, openai, httpx,
google.auth, googleapiclient, google_auth_oauthlib, requests_oauthlib, websocket,
websockets, selenium, playwright, lxml.
No `~/.anthropic`, `~/.config/anthropic`, `~/.claude`, `~/.ambimat_measure_creds`, `~/.netrc`.
Zero API-key-shaped environment variables. No key material was read or printed.

`nodejs 26.3.1` / `nodejs-lts 24.17.0` are installable for arch `arm`, so a CDP client
could be built — but there is no LLM runtime, no credential, and no owner authorisation
for a paid API integration. 2882 MB RAM, 19 GB free on /data.

## Existing automation — untouched

    crontab            4 lines, unchanged (10:00 site monitor, 11:00 SEO,
                       */30 watchdog, 12:00 cache monitor)
    crond              running
    markers            site_monitor=2026-08-25  seo=2026-08-25
                       front_page_cache=2026-08-25 (fired on its own at 12:00 today)
    boot script        ~/.termux/boot/start-ambimat-jobs intact
    ensure_scheduler   sha256 7c05ac978b5f025dffb2795f2fc7c9b245c0ced0f6d21ef3b829ad01ab54fcc7
                       (identical to the 2026-08-25 install record)
    queue.tsv          4 entries, all status=scheduled
    blackout           MQ_BLACKOUT_DATES defaults to 2026-08-28
    evidence dirs      none created (LATEST.json / LATEST.md only)
    prompt files       untouched; V2X / AmbiSecure / eSIM still awaiting owner Markdown

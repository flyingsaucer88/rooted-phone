# 12:00 IST front-page cache monitor — installation & verification, 2026-07-31

Adds a third daily job to the Moto G4 Plus scheduler: a **strictly read-only** inspection of
the cached front page of `https://ambimat.com/`. The job inspects and reports. It has no
capability to repair, purge, invalidate, rebuild, warm or modify anything, and none was added.

Runbook: [cache_monitor/README.md](../cache_monitor/README.md).

## Scheduler architecture found (unchanged, reused)

The scheduler lives on the phone at `~/seo_tracker/phone/` (not mirrored in this repo; see
[docs/scheduler_verification_20260727.md](scheduler_verification_20260727.md)):

- `lib_common.sh` — env-overridable helpers: per-job `<job>_last_success_date` markers,
  atomic dir locks with stale/dead-owner reclaim, network gate, wake-lock, `amb_run_if_due`.
  Exports `TZ=Asia/Kolkata`.
- `run_site_monitor_daily.sh` (10:00) and `run_daily.sh` (11:00) — offline-defer, own lock,
  mark success only on rc == 0.
- `ensure_scheduler.sh` — `*/30` watchdog + boot: single-flight, revives `crond`, reinstalls
  missing crontab lines, catches up due jobs.
- `schedule_daily.sh` — idempotent install of the three marker-tagged cron lines.
- `~/.termux/boot/start-ambimat-jobs` (Termux:Boot) — wake-lock, `sshd`, `crond`, crontab
  install, then the watchdog.

The noon job reuses all of it. Nothing was replaced.

## Changes made

**New, in this repo** — `cache_monitor/` (deployed to `~/cache_monitor` on the phone):

| File | Purpose |
|---|---|
| `front_page_cache_monitor.py` | Inspection engine. Stdlib only (no `requests`, no `tzdata`). |
| `run_cache_monitor_daily.sh` | Phone wrapper: marker, network gate, maintenance lock, own lock, evidence, notification. |
| `install_noon_job.sh` | Installs/removes **only** the `# ambimat-cache-monitor` cron line. |
| `ensure_scheduler_noon_block.sh` | Versioned copy of the watchdog edit below. |
| `config/expected_metadata.json` | Governed vs known-obsolete front-page metadata. |
| `config/server_inspection.example.json` | Optional read-only server access; ships **disabled**. |
| `tests/` | 58 offline fixture tests, 39 scheduling scenarios, static read-only audit. |
| `README.md` | Runbook. |

**On the phone, one additive edit** (backup kept as `ensure_scheduler.sh.bak-20260731`;
snapshot updated in `reports/scheduler_verification/phone_scripts_snapshot/`):
`ensure_scheduler.sh` gained a block after the existing 10:00/11:00 catch-up calls that
self-heals the noon crontab line and calls `amb_run_if_due front_page_cache 1200 …`.
The 10:00 and 11:00 catch-up calls above it are byte-identical to before.

**Crontab** — the noon line was appended; the three existing lines are unchanged:

```
0 10 * * *   .../run_site_monitor_daily.sh    # ambimat-site-monitor
0 11 * * *   .../run_daily.sh                 # ambimat-seo-tracker
*/30 * * * * .../ensure_scheduler.sh          # ambimat-scheduler-watchdog
0 12 * * *   .../run_cache_monitor_daily.sh   # ambimat-cache-monitor      <-- new
```

## Verification, 2026-07-31

| Check | Result |
|---|---|
| `bash -n` on all four shell files, `py_compile` on all Python | pass |
| Fixture tests (Mac) | 58/58 pass, sockets blocked for the whole suite |
| Fixture tests (phone, Python 3.13.13) | 58/58 pass |
| Scheduling scenarios (phone, against the **real** `lib_common.sh`) | 39/39 pass |
| Static read-only audit (Mac + phone) | pass |
| Audit negative control (four injected violations) | all four caught |
| Crontab after install | 4 lines, all markers present, `crond` running |
| Watchdog tick with all markers set | all three jobs "already succeeded today; skip" |
| Watchdog tick with the noon marker cleared, 17:38 IST, `--dry-run` | `front_page_cache: DRY-RUN — would run …` (10:00/11:00 still skip) |
| Termux notification | posted; confirmed via `dumpsys notification` (`pkg=com.termux.api tag=ambimat_cache_monitor`) |
| Live canary | **exactly one** public GET |

Reboot persistence: Termux:Boot already runs `ensure_scheduler.sh`, which now covers the
noon job, so no boot-script change was needed. Following the precedent of the 2026-07-27
session, **no unattended remote reboot was performed** — it would drop SSH and could strand
the phone. The catch-up decision was instead proven live via the dry-run above.

## Live canary result — a real finding

Evidence: [reports/cache_monitor_canary_20260731/](../reports/cache_monitor_canary_20260731/)
(manifest verifies, 10/10, self-excluding).

- One request, `2026-07-31T12:04:56Z`, UA `AmbimatRootedPhone-CacheMonitor/1.0`, HTTP 200,
  0 redirects, 192,835 bytes.
- Body SHA-256 `75a548b15ea8df3dd52bd4b95edc5d74ad6f6198833f02594af98582693a46ef` —
  **byte-identical** to the Gate C capture of 11:12:40Z.
- `Last-Modified: Fri, 31 Jul 2026 10:18:42 GMT`, `ETag "2f143-657e583550537"` — the same
  W3TC entry, now ≈ 1 h 46 min old against a 3600 s configured lifetime.
- `og:image` still resolves to `2022/05/image_2022.png` (attachment **9920**, the stale
  image, 1021×532). Schema image is the governed `…1200x630-1.png` (attachment 36105).
  `twitter:image` remains absent, as in the Gate C observation.
- Classification **`ALERT_STALE_OR_OBSOLETE_METADATA`**, `mutation_attempted: false`,
  `repair_attempted: false`, `public_request_count: 1`,
  `server_commands_read_only: unavailable`.

Server-side inspection reported `SERVER_INSPECTION_UNAVAILABLE`: the phone holds no
credential for the web host (`~/.ssh` contains only `authorized_keys`), so no server
inspection was configured, attempted or faked.

**Manual review required. No repair or mutation was attempted.**

## Manual follow-up

1. The phone-side `ensure_scheduler.sh` edit is versioned here as
   `cache_monitor/ensure_scheduler_noon_block.sh` and snapshotted under
   `reports/scheduler_verification/phone_scripts_snapshot/`. The canonical copy of that
   script also lives in the separate `ambisecure-seo-tracker` repo (`phone/`), which was
   **not** modified — mirror the block there when convenient.
2. Server-side inspection stays unavailable until a **read-only** credential is deliberately
   provisioned for the phone. Until then every run reports
   `PASS_PUBLIC_HEALTHY_SERVER_INSPECTION_UNAVAILABLE` (or an alert from public evidence
   alone, as today).
3. The stale front-page cache entry is a standing finding, not a task for this job.
   Any remediation belongs to a separate, explicitly authorized procedure.

# Measurement experiment — RETIRED, OWNER DECISION 2026-09-07

The authenticated-measurement framework was an experiment. The owner decided on
**2026-09-07** not to pursue it. It has been surgically retired from the phone and the
repository. The phone is back to being a plain operational monitor.

```
Measurement credential provisioning required: NO
Measurement queue active:                     NO
Measurement notifications active:             NO
```

## What was found

| Component | Where | Introduced by |
| --- | --- | --- |
| `measurement_queue/` (runner, lib, preflight, `api/` collectors, prompts, tests) | repo + `~/measurement_queue/` | `b552a73`, `6524798` (both 2026-08-25) |
| Watchdog invocation block | `~/seo_tracker/phone/ensure_scheduler.sh` lines 84–100 | `6524798` era |
| Queue state (4 runs) | `~/ambimat_job_logs/measurement_state/` | runtime |
| Credential directory | `~/.ambimat_measure_creds/` | created 2026-08-25 13:03, **always empty** |
| Credential-provisioning instructions | `docs/standalone_api_architecture_20260825.md` | `6524798` |
| Blocked evidence + notifications | `~/scheduled_measurements/`, Android tray | runtime |

## What scheduled it

**Only** the 30-minute `ambimat-scheduler-watchdog` cron line, via an additive block at
the very end of `ensure_scheduler.sh` — after the 10:00 / 11:00 / 12:00 blocks, so the
daily jobs always won the locks. There was **no dedicated cron line** for the measurement
queue and **no reference in the Termux:Boot hook** (verified: 0 matches in
`~/.termux/boot/start-ambimat-jobs`).

That is why it fired every 30 minutes, forever, re-emitting a BLOCKED notification.

## Provenance — why this was safe to remove surgically

The dependency arrow points one way only:

```
measurement_queue/*  ->  seo_tracker/phone/lib_common.sh   (measurement CONSUMES the shared lib)
site_monitor/, cache_monitor/, scripts/  ->  (nothing measurement)
```

A repo-wide search found **no** reference to `measurement_queue`, `lib_measure`,
`preflight_auth`, `MQ_*` or `ambimat_measure_creds` from any legitimate component —
only `.gitignore` safety patterns and the measurement-only design doc. No shared utility
and no credential path is used by site monitoring, SEO monitoring or the cache monitor.

So `fb2005a` was **not** blanket-reverted: its V2X/AI site additions, the site-inventory
guard, the notification-suppression fix and the scheduler test repairs are all retained.
Only the measurement feature was excised.

## What was removed or disabled

**On the phone**

| Action | Result |
| --- | --- |
| Stripped the measurement block from `ensure_scheduler.sh` | 4757 → 3832 bytes; `bash -n` clean; 0 measurement references |
| `rm -rf ~/measurement_queue` | gone |
| `rm -rf ~/ambimat_job_logs/measurement_state` | gone |
| `rmdir ~/.ambimat_measure_creds` | removed — **it was empty (0 entries)**, so no credential was ever present and none was deleted |
| `termux-notification-remove` ×5 | the eSIM / AmbiSecure / V2X BLOCKED banners cleared |

Backup of the pre-change watchdog:
`~/.recovery_backup_20260907/ensure_scheduler.sh.before-measurement-retirement`.

**In the repository**

* deleted `measurement_queue/` (27 files) and `docs/standalone_api_architecture_20260825.md`
* `RETIRED.md` markers added to the two historical evidence dirs under
  `reports/scheduler_verification/`
* `.gitignore` credential patterns kept, but re-commented as a pure safety net
* `README.md` states plainly that the phone needs no credentials
* `tests/test_site_inventory.py` gained `test_measurement_experiment_stays_retired`

## Credential directory disposition

`~/.ambimat_measure_creds/` contained **0 entries** at removal time (verified by
`ls -A | wc -l`). No unexpected secret was present, nothing was printed, nothing of value
was destroyed. It existed solely for the abandoned system.

## Why it cannot relaunch after reboot

Four independent reasons, each sufficient:

1. The Termux:Boot hook (`~/.termux/boot/start-ambimat-jobs`) never referenced the queue —
   it only starts `sshd`/`crond`, reinstalls the crontab and calls the watchdog.
2. The watchdog it calls no longer contains the invocation block.
3. The crontab has four lines, none of which is a measurement job; the watchdog's
   crontab self-heal reinstalls only those same four marker-tagged lines.
4. The runner binary is gone, so even a stale invocation would find nothing to execute.

Verified live: the watchdog tick at **2026-09-07 16:35:54 IST** logged only
`site_monitor`, `seo` and `front_page_cache`, and `measurement_queue.log` was not
written to (last modified 16:30, the final pre-retirement tick).

## Historical evidence preserved

* `phone_measurement_state_before.txt` — crontab, watchdog block, queue, state, file tree, cred dir
* `ensure_scheduler_before.txt` — the watchdog as it stood before the edit
* `measurement_artifacts.tar.gz` — 50 files: the full `~/measurement_queue/`,
  `~/scheduled_measurements/`, queue state and `measurement_queue.log`
* `notifications_before.json` — the Android tray, including the three BLOCKED banners
* The device keeps `~/scheduled_measurements/` and `~/ambimat_job_logs/measurement_queue.log`
  as inert historical logs; nothing reads or writes them any more.

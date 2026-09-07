# Scheduler inventory — every mechanism able to launch work on this phone

Enumerated on-device 2026-09-07. Timezone pinned to `Asia/Kolkata` by every job.

## Mechanisms that exist — OBSERVED

| Mechanism | Present? | Role |
| --- | --- | --- |
| Termux `cronie` / `crond` | YES (pid 8091, up 2h22m) | the only time-based trigger |
| Termux:Boot (`~/.termux/boot/start-ambimat-jobs`) | YES | wake-lock → sshd → crond → reinstall crontab → sleep 45 → watchdog catch-up |
| Termux:API (`com.termux.api`, pid 5094) | YES | `termux-notification`, `termux-battery-status`, `termux-wake-lock` |
| `ensure_scheduler.sh` watchdog | YES, every 30 min | catch-up engine for all four job families |
| `amb_acquire_lock` dir-locks w/ dead-owner reclaim | YES | `seo_run`, `site_run`, `cache_monitor_run`, `measure_queue` |
| Durable per-job success markers | YES | `~/ambimat_job_logs/<job>_last_success_date` |
| Android JobScheduler / AlarmManager | NO | not used |
| Tasker or equivalent | NO | not installed |
| Shell startup hooks (`.bashrc`/`.profile`) | NO | none exist — nothing launches work on login |
| Termux services (`sv`/runit) | NO | `usr/var/service` holds only crond/sshd/ssh-agent, unused by these jobs |
| `at`/`atd` | NO | not installed |
| SQLite state DB | NO | state is flat files (`.state`, marker files) |
| Scheduled GitHub interactions | NO | the phone never talks to GitHub |

## Installed crontab — OBSERVED (4 lines)

```
0 10 * * *   seo_tracker/phone/run_site_monitor_daily.sh    # ambimat-site-monitor
0 11 * * *   seo_tracker/phone/run_daily.sh                 # ambimat-seo-tracker
0 12 * * *   cache_monitor/run_cache_monitor_daily.sh       # ambimat-cache-monitor
*/30 * * * * seo_tracker/phone/ensure_scheduler.sh          # ambimat-scheduler-watchdog
```

## Activity table

| Activity | Scheduler | Intended cadence | Script / entrypoint | Last attempted | Last success | Current state |
| --- | --- | --- | --- | --- | --- | --- |
| Site availability / live-page monitor | cron 10:00 + watchdog + boot hook | daily 10:00 IST | `seo_tracker/phone/run_site_monitor_daily.sh` → `site_monitor/run_daily.sh` | 2026-09-07 15:05 (post-repair re-run) | **2026-09-07 12:56:06** | healthy; now 9 sites |
| SEO tracker | cron 11:00 + watchdog + boot hook | daily 11:00 IST | `seo_tracker/phone/run_daily.sh` | 2026-09-07 13:11 | **2026-09-07 13:11:07** | healthy; now 9 domains |
| Front-page cache monitor (read-only) | cron 12:00 + watchdog + boot hook | daily 12:00 IST | `cache_monitor/run_cache_monitor_daily.sh` | 2026-09-07 13:11 | **2026-09-07 13:11:12** | healthy; PASS |
| Scheduler watchdog | cron `*/30` | every 30 min | `seo_tracker/phone/ensure_scheduler.sh` | 2026-09-07 15:00 | n/a (control loop) | healthy |
| Boot hook | Termux:Boot | on power-on | `~/.termux/boot/start-ambimat-jobs` | 2026-09-07 12:34:29 | 2026-09-07 13:11:27 | healthy |
| Measurement queue — V2X | watchdog `*/30` | one-shot 2026-08-27 01:00 | `measurement_queue/run_measurement_queue.sh` | 2026-09-07 15:08:52 | never | **BLOCKED — SOURCE PROMPT NOT INSTALLED** |
| Measurement queue — AmbiSecure GSC 7-day | watchdog `*/30` | one-shot 2026-08-29 01:00 | same | 2026-09-07 15:08:55 | never | **BLOCKED — SOURCE PROMPT NOT INSTALLED** |
| Measurement queue — Ambimat GA4/GSC | watchdog `*/30` | one-shot 2026-08-29 01:00 | same | never (dependency-gated) | never | **STARVED** behind AmbiSecure |
| Measurement queue — eSIM phase 3b/4 | watchdog `*/30` | one-shot 2026-09-01 01:00 | same | 2026-09-07 15:08:59 | never | **BLOCKED — AUTHENTICATED DATA SOURCE UNAVAILABLE** (genuine) |

Success is taken from `<job>_last_success_date` markers **cross-checked against the
artefact each run actually produced** — a marker alone was never treated as proof.

## Process hygiene — OBSERVED

At audit time: `crond`, `sshd`, `com.termux`, `com.termux.api` only. **No** stale or hung
Python, crawler, Termux-API, notification or scheduler processes; **no** held locks; **no**
orphaned SSH sessions. 20 GB free, battery 62% and charging (AC).

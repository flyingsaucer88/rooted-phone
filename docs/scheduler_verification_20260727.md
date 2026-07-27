# Daily Scheduler Verification — 2026-07-27

Verification of the daily site-monitor (10:00) and SEO (11:00) jobs on the Moto G4 Plus
(Termux, Asia/Kolkata), including missed-run recovery, dedup, locking, and reboot survival.

## Scope note

The scheduler lives **on the phone** at `~/seo_tracker/phone/` (a project **not** mirrored in this
Mac repo — the repo contains only `site_monitor/`). This doc + `reports/scheduler_verification/`
capture the verification evidence and a snapshot of the (modified) phone scripts.

## Existing design (found already implemented; not replaced)

- **`lib_common.sh`** — shared, fully env-overridable (testable): per-job date success markers
  (`ambimat_job_logs/<job>_last_success_date`), atomic dir-based locking with stale/dead-owner
  reclaim, network gate, best-effort wake-lock, and `amb_run_if_due` (skip if done-today / before-due
  / offline; else run).
- **`run_site_monitor_daily.sh`** (10:00 cron + watchdog) — wraps `~/site_monitor/run_daily.sh`;
  offline-defers, takes `site_run` lock, marks success **only on rc==0**.
- **`run_daily.sh`** (11:00 cron + watchdog) — runs `phone_seo.py`; offline-defers, `seo_run` lock,
  marks success only on rc==0; notification redirects stdout/stderr to `/dev/null`.
- **`ensure_scheduler.sh`** (`*/30` watchdog + boot) — single-flight lock; revives `crond`;
  reinstalls crontab if lines missing; catches up site (10:00) then SEO (11:00), staggered.
- **`schedule_daily.sh`** — idempotent install/remove of the 3 cron lines (preserves other lines).
- **`install_boot_persistence.sh`** — generates `~/.termux/boot/start-ambimat-jobs` (Termux:Boot).

## On-phone state (verified 2026-07-27)

- Timezone: `Asia/Calcutta` (≡ Asia/Kolkata, IST +05:30). `date` is local, never UTC.
- crontab: 3 lines present (site 10:00, seo 11:00, watchdog `*/30`). `crond` running.
- Markers: both `site_monitor` and `seo` = `2026-07-27` (both succeeded today).
- Packages: cronie 1.7.2, python 3.13.13, termux-api 0.59.1, openssh. Termux:Boot installed.
- Boot log confirms Termux:Boot **fired at the last reboot** (11:38): wake-lock → crond → crontab → watchdog.
- Doze whitelist: `com.termux`, `com.termux.api`, `com.termux.boot` **added** (this session, via adb).

## Controlled scenario tests — 18/18 PASS

Harness: `reports/scheduler_verification/sched_tests.sh` (runs the real scripts against an isolated
temp `AMBIMAT_HOME` with injected time/network/runners; touches no real crontab/markers/reports).

| # | Scenario | Result |
|---|---|---|
| Running at 10:00/11:00 | cron fires each runner at its time | design + T2 |
| Off at 10:00, restarted 10:30 | watchdog catch-up runs missed site; SEO normal 11:00 | T2 |
| Off before 10:00 → 10:30 | same as above | T2 |
| Off 10:00–11:00 after site done | marker set → site not repeated; SEO at 11:00 | T3 |
| Off both, restart after 11:00 | both catch up once, site before SEO | T2 + code order |
| Restarted before 10:00 | neither runs early | T1 |
| Rebooted repeatedly after success | marker=today → skip | T3 |
| Job killed mid-run before completion | no marker (rc≠0) → retried next tick | C2 |
| Scheduler + boot fire together | lock → exactly one execution | D |
| offline when due | defer, no marker, retry later | T4, C3, E1 |
| dry-run | no execution | T5 |
| success only on rc==0 | marker set only on success | C1/C2 |
| SEO lock contention | second invocation skips, python not run | E2 |

Notification FD safety: an SSH-invoked `termux-notification` (stdout/stderr → `/dev/null`) returned
in ~1s with **no lingering `libexec/termux-api` helper** — the earlier hang class does not recur.

## Changes made this session (minimal, reliability-motivated; backups kept as `*.bak-20260727`)

1. `lib_common.sh`: added `: "${TZ:=Asia/Kolkata}"; export TZ` — explicit IST (req: never depend on
   an ambiguous default/UTC). Regression: 18/18 still pass.
2. `install_boot_persistence.sh`: the generated boot script now also starts **`sshd`** on boot, so
   the USB bridge survives reboots too (previously it started only crond). The live boot script
   already had this from a prior session; this makes it durable if the generator is re-run.
3. Doze battery whitelist added for the three Termux packages (adb).

## Coverage changes APPLIED (approved 2026-07-27) — full coverage

Per approval: added 3 domains to the site-monitor and raised caps for **full coverage** of both jobs.

- **Site-monitor now covers 7 domains** (added `ambipower`, `orders`, `roboracer` — all verified live,
  HTTP 200): ambimat.com, ambisecure., ambiautomation., esim., ambipower., orders., roboracer.
- **Caps raised** (`site_monitor/config/sites.yaml`): `max_pages_per_site 20→800`,
  `delay 1.0→0.5s`, `max_internal_link_checks 100→300`, `max_seconds_per_site 180→1200`,
  `global_max_seconds 600→3600` (time budgets raised so full coverage isn't truncated).
- **SEO cap raised** (`seo_tracker/phone/config.yaml`): `max_pages_per_domain 40→800` (backup kept).
- **Validation:** a single-site run of eSIM with the new config crawled **all 33 sitemap pages**
  (old cap was 20), `timed_out=False`, ~33 s — full coverage confirmed end-to-end.
- **Expected daily runtime** grows substantially (ambimat ~697 pages, ambisecure ~318). At 0.5 s/page
  the big site ≈ 6 min fetch + link checks, within the 1200 s/site budget; whole run bounded at
  60 min. The held wake-lock (watchdog/boot) matters more now — confirm the battery exemption.
- **SEO domain list reconciled (approved 2026-07-27):** `orders` and `roboracer` were added to the
  SEO config too, so **both jobs now cover the same 7 domains**. SEO entries include derived seed
  keywords (roboracer → autonomous-racing/robotics kit; orders → ordering/ecommerce portal).
- **Full 7-site coverage crawl COMPLETED on-device** (2026-07-27 14:03→14:22, `ORCH_DONE rc=0`,
  per-site processes, wake-lock held, external checks ON). Result: **917 pages, 7/7 reported, 0
  unreachable, 0 timed_out, partial=false** (nothing truncated). Real findings: 5 broken internal
  pages on ambimat.com (all 404) + 1 possibly-removed Play Store listing; the other 22 "broken
  external" links are bot-rejection false positives; 692 warnings are warning-level noise (no
  defacement ALERTs). Evidence: `reports/full_coverage_crawl_20260727/` (report + COVERAGE_SUMMARY.md).

## Original coverage findings (pre-change, for reference)

Sitemap page counts vs current crawl caps:

| Domain | sitemap pages | site-monitor (cap 20) | SEO (cap 40) | in site-monitor cfg? |
|---|---|---|---|---|
| ambimat.com | 697 | ~3% | ~6% | yes |
| ambisecure.ambimat.com | 318 | ~6% | ~13% | yes |
| esim.ambimat.com | 33 | ~60% | full | yes |
| ambiautomation.ambimat.com | 22 | ~90% | full | yes |
| ambipower.ambimat.com | 25 | — | full | **NO (missing)** |

- **Discrepancy:** SEO covers 5 domains; site-monitor covers 4 (missing `ambipower.ambimat.com`).
- **Caps truncate coverage** heavily for the two large sites. "All pages" is not currently achieved.
- Decision required (product + device-resource tradeoff): whether to add `ambipower` to the
  site-monitor and whether to raise caps for full coverage (longer daily runs on a 2016 phone).

## Remaining manual acceptance test (physical reboot)

A remote unattended reboot was **not** performed — it would drop SSH and, if boot recovery failed
for any reason, strand the phone until physically touched. Evidence already shows Termux:Boot fires
and the generated boot script now starts sshd. Definitive on-device proof:

1. Reboot the phone. Do **not** open Termux.
2. Wait ~2 min, then from the Mac: `adb forward tcp:8022 tcp:8022` and
   `ssh -p 8022 … 'tail ~/ambimat_job_logs/boot_startup.log; pgrep -x crond; pgrep -x sshd'`.
3. Expect: boot log shows the new run (wake-lock, sshd started, crond, watchdog); crond + sshd up.
4. Confirm the day's markers/reports appear per schedule (or immediately if a run was due).

## Verdict

Scheduling reliability (missed-run recovery, dedup, locking, failure-not-marked, boot survival):
**READY WITH MANUAL CHECK** (battery-exemption durability + one physical reboot test).
Website coverage: applied per approval — **both jobs now cover the same 7 domains** (SEO reconciled:
orders + roboracer added). Full-coverage caps validated end-to-end by a complete on-device 7-site
crawl (917 pages, ~19 min, no OOM/timeout/truncation via per-site processes). The prior single-process
full run OOM-killed at ~700 pages; per-site processing resolved it. No open coverage items remain.

Note: `Rooted-Phone` is **not** a git repository (no `.git` in the tree), so changes are delivered as
commit-ready files rather than committed here.

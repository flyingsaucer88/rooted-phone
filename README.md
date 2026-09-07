# Rooted Phone

Turning an old **Moto G4 Plus** into an always-on, self-recovering **daily website-monitoring
device**, plus a small safe telemetry/experiment toolkit — all driven from a Mac over a
USB (ADB + SSH) bridge. The phone is **unrooted**; everything here runs inside **Termux** with no
root, no browser automation, and no cloud API keys.

**The phone needs no credentials, API keys or authenticated accounts to do its job.** An
earlier experiment that added authenticated GA4 / Search Console measurement was
**RETIRED on 2026-09-07 by owner decision** and removed; see
[reports/measurement_retirement_20260907T110425Z/](reports/measurement_retirement_20260907T110425Z/).
If you find a note anywhere asking you to install `google_service_account.json` or an
`anthropic_api_key`, it is stale — nothing here needs them.

Three jobs run on the phone every day:

| Time (Asia/Kolkata) | Job | What it does |
|---|---|---|
| **10:00 AM** | **Site monitor** (this repo, `site_monitor/`) | Crawls every eligible internal page of each production site and flags non-live pages, broken links, redirects, HTTP/TLS/DNS failures, and public-page compromise indicators. |
| **11:00 AM** | **SEO tracker** (phone-resident, `~/seo_tracker/phone/` — see note) | Runs the SEO health workflow for the same sites. |
| **12:00 PM** | **Front-page cache monitor** (this repo, `cache_monitor/`) | **Inspect and report only.** Makes one ordinary public request to `https://ambimat.com/`, classifies whether the cached front page looks current, stale, inconsistent, unavailable or unverifiable, records evidence, and alerts. |

> ⚠️ **The 12:00 job never repairs the site.** It has no purge, flush, invalidate, warm,
> rebuild, cron-run, database-write or WordPress-write path — not even a disabled one. A
> stale finding produces an alert and evidence, and stops there. Full boundary, runbook and
> post-alert procedure: [cache_monitor/README.md](cache_monitor/README.md).

All three jobs have **missed-run recovery**: if the phone was off/asleep at the scheduled time, a
watchdog and a boot hook run the day's job late (exactly once), so a powered-off phone does not
silently skip a day.

> **Scope note — what is and isn't in this repo.** The **site monitor** (`site_monitor/`) is the
> runnable code in this repository. The **SEO tracker** and the full **scheduler / boot-persistence
> system** live *on the phone* under `~/seo_tracker/phone/` and are **not** part of this repo
> (device-resident, set up manually). What *is* committed here for them is: read-only **snapshots**
> of the phone scripts in [reports/scheduler_verification/phone_scripts_snapshot/](reports/scheduler_verification/phone_scripts_snapshot/)
> and the full verification writeup in [docs/scheduler_verification_20260727.md](docs/scheduler_verification_20260727.md).
> Commands below that reference `~/seo_tracker/phone/...` therefore describe the on-device setup and
> are marked **[phone-side, manual setup]**.

## Device & environment

| Field | Value |
| ----- | ----- |
| Model | Moto G4 Plus (`athene_f`) |
| Android | 7.0 (SDK 24) |
| CPU ABI | 32-bit `armeabi-v7a` (Qualcomm msm8952 / SD617) |
| RAM / Storage | ~2.95 GB (~130–150 MB typically free) / ~21 GB free |
| Root | **Not available** (no `su`); treated as unrooted |
| Termux user | `u0_a122` |
| Timezone | `Asia/Calcutta` ≡ `Asia/Kolkata` (IST, +05:30) — set explicitly by the jobs |

**Prerequisites**

- On the **phone** (Termux, GitHub build): `openssh`, `python` (3.13.x), `cronie`, and the
  `termux-api` CLI package; companion apps **Termux:API** (`com.termux.api`) and **Termux:Boot**
  (`com.termux.boot`) installed and, for reliability, the three Termux packages added to the
  battery/Doze whitelist. Python deps for the crawler: `requests`, `beautifulsoup4`, `PyYAML`.
- On the **Mac**: `adb` (Android platform-tools), `ssh`/`rsync`, and the dedicated SSH key
  `~/.ssh/id_moto_playground` (the key stays on the Mac; it is **not** in this repo).

## Repository structure

```
.
├── README.md                     # this file
├── .gitignore                    # excludes secrets, APKs, raw reports, caches
├── rooted_android_phone_playbook.md   # full narrative build log / device playbook
├── phone/seo_tracker_config.yaml # authoritative SEO-tracker domain list (deployed to the phone)
├── tests/test_site_inventory.py  # guard: the eight mandatory sites must stay in both inventories
├── site_monitor/                 # the daily site-monitor (runnable, Termux)
│   ├── config/sites.yaml         # site list + crawl policy + alert thresholds
│   ├── run_site_monitor.py       # crawler / analyzer / report writer
│   ├── merge_reports.py          # merges per-site reports into one combined report
│   ├── render_report.py          # JSON -> Markdown/HTML renderer + viewer
│   ├── run_once.sh               # run one crawl now (foreground)
│   ├── run_daily.sh              # per-site orchestrator (one process per site) + notify
│   ├── schedule_daily.sh         # install/show/remove the simple 10:00 cron line
│   ├── show_latest_report.sh     # open/print the latest report on the phone
│   ├── requirements.txt          # requests, beautifulsoup4, PyYAML
│   ├── keywords/*.txt            # editable spam / suspicious-pattern keyword lists
│   └── reports/.gitkeep          # placeholder; live reports go to ~/site_monitor_reports
├── cache_monitor/                # the 12:00 front-page cache monitor (READ-ONLY, runnable)
│   ├── README.md                 # runbook: boundary, states, catch-up, post-alert procedure
│   ├── front_page_cache_monitor.py       # the inspection engine (stdlib only)
│   ├── run_cache_monitor_daily.sh        # phone wrapper: locks, marker, notify, evidence
│   ├── install_noon_job.sh               # install/show/remove ONLY the 12:00 cron line
│   ├── ensure_scheduler_noon_block.sh    # versioned copy of the watchdog catch-up edit
│   ├── config/expected_metadata.json     # governed vs known-obsolete front-page metadata
│   ├── config/server_inspection.example.json  # optional read-only server access (off by default)
│   └── tests/                    # 58 offline fixture tests + 39 scheduling scenarios + static audit
├── scripts/                      # Mac/phone telemetry + connection helpers
│   ├── moto-ssh.sh               # USB forward + SSH login helper
│   ├── collect_baseline.sh       # one-shot device baseline
│   ├── check_termux_api.sh       # Termux:API probe
│   ├── telemetry_loop.py         # bounded telemetry sampler (JSONL/CSV)
│   └── pull_logs.sh              # pull phone logs into ./logs
├── docs/                         # design notes, plans, verification writeups
├── logs/                         # SAMPLE_telemetry_redacted.jsonl only (raw captures gitignored)
└── reports/
    ├── scheduler_verification/   # scheduler test harness + phone-script snapshots
    └── full_coverage_crawl_20260727/COVERAGE_SUMMARY.md   # evidence of a full 7-site crawl
```

## Installation & dependencies

**Site monitor (on the phone, in Termux):**

```bash
cd ~/site_monitor
python -m pip install --user -r requirements.txt   # requests, beautifulsoup4, PyYAML
```

`cronie` and the Termux companion apps are installed separately (see Prerequisites). The Python
deps are the only application dependencies of the crawler; it otherwise uses the standard library
(including `ssl` for TLS-expiry checks).

## Configuration

- **Sites & crawl policy:** [site_monitor/config/sites.yaml](site_monitor/config/sites.yaml).
  It lists the monitored sites and the crawl/alert policy. The monitored production domains are:
  `ambimat.com`, `ambisecure.ambimat.com`, `ambiautomation.ambimat.com`, `esim.ambimat.com`,
  `ambipower.ambimat.com`, `orders.ambimat.com`, `roboracer.ambimat.com`, `v2x.ambimat.com`,
  `ai.ambimat.com` (**9 sites — the authoritative active estate**). `v2x` and `ai` were
  added 2026-09-07; `esim` was ratified as mandatory the same day.
  `tests/test_site_inventory.py` fails if any of the nine goes missing from either
  inventory, if the two inventories drift apart, if retired `ambimechanicals` reappears,
  or if the retired measurement experiment returns.
  Notable keys: `max_pages_per_site`, `max_internal_link_checks_per_site`, `max_seconds_per_site`,
  `global_max_seconds`, `delay_between_requests_seconds`, `connect_timeout_seconds` /
  `read_timeout_seconds`, `check_external_links`, `external_check_skip_hosts` (social/CDN hosts that
  reject bots — kept out of "broken external" to avoid false positives), and the alert thresholds.
- **Keyword lists:** `site_monitor/keywords/*.txt` (Japanese-spam, pharma/casino/etc. spam,
  suspicious HTML patterns) — editable without code changes.
- **No secrets** are stored in this repo. The SSH key lives in `~/.ssh` on the Mac; raw telemetry
  captures (Wi-Fi SSID / private IPs) are gitignored; only a redacted sample is committed.

## Run the daily live-page / site-monitor check

**Manually, on the phone (foreground, whole run):**

```bash
cd ~/site_monitor
./run_daily.sh                 # per-site processes -> merged report + one phone notification
```

`run_daily.sh` crawls **one site per Python process** (memory-bounded — a single all-sites process
OOM-killed on this low-RAM phone at ~700 pages), writing `per_site/<slug>/report_latest.json`, then
`merge_reports.py` combines them into a single `report_latest.{json,md,html}`. Job success means "a
combined report was produced"; per-site alerts (broken pages, etc.) are **findings**, not job
failures.

**A single crawl / smoke test (bounded):**

```bash
cd ~/site_monitor
./run_once.sh --max-pages 3 --no-external-links --verbose        # quick smoke test
./run_once.sh                                                    # full config-driven single run
# lowest-level, fully bounded:
python run_site_monitor.py --config config/sites.yaml --output-dir ~/site_monitor_reports \
  --max-pages 3 --global-timeout 120 --site-timeout 60 --no-external-links --open-report false --verbose
# limit to one site (memory-bounded):
python run_site_monitor.py --config config/sites.yaml --only "Ambimat" \
  --output-dir ~/site_monitor_reports/per_site/ambimat_com --open-report false --no-notify
```

Useful flags: `--max-pages N`, `--global-timeout SEC`, `--site-timeout SEC`, `--no-external-links`,
`--only "<Site name>"`, `--verbose`, `--no-notify`, `--open-report true|false`.

## Run the SEO workflow  **[phone-side, manual setup]**

The SEO tracker is device-resident under `~/seo_tracker/phone/` (not in this repo). On the phone:

```bash
bash ~/seo_tracker/phone/run_daily.sh          # run the SEO workflow now (the 11:00 job entry point)
```

It covers the **same 9 domains** as the site monitor. Its domain list lives on the device at
`~/seo_tracker/phone/config.yaml`; the authoritative, version-controlled copy is
[phone/seo_tracker_config.yaml](phone/seo_tracker_config.yaml) (deploy instructions are in its header). A read-only snapshot of the SEO config used at verification time
is committed at
[reports/scheduler_verification/phone_scripts_snapshot/seo_config.yaml](reports/scheduler_verification/phone_scripts_snapshot/seo_config.yaml).

## Schedules (Asia/Kolkata)

Installed as four Termux `cron` lines — three via `~/seo_tracker/phone/schedule_daily.sh install`
**[phone-side]**, and the noon line via [cache_monitor/install_noon_job.sh](cache_monitor/install_noon_job.sh):

```
0 10 * * *   run_site_monitor_daily.sh     # 10:00 — site monitor          # ambimat-site-monitor
0 11 * * *   run_daily.sh                  # 11:00 — SEO tracker           # ambimat-seo-tracker
*/30 * * * * ensure_scheduler.sh           # every 30 min — watchdog       # ambimat-scheduler-watchdog
0 12 * * *   run_cache_monitor_daily.sh    # 12:00 — cache monitor (RO)    # ambimat-cache-monitor
```

Each installer strips and rewrites only its own marker-tagged lines, so the two are independent:
removing the noon job leaves the other three untouched, and vice versa.

The in-repo [site_monitor/schedule_daily.sh](site_monitor/schedule_daily.sh) is a **simpler,
single-job** installer (the 10:00 site-monitor line only) and does not set up boot persistence — it
predates the phone-side two-job scheduler. On the device, the phone-side installer is authoritative.

## Restart / catch-up behaviour (phone powered off during a scheduled run)

Implemented by the phone-side scheduler (`~/seo_tracker/phone/lib_common.sh` + `ensure_scheduler.sh`
+ the Termux:Boot hook). Design and evidence: [docs/scheduler_verification_20260727.md](docs/scheduler_verification_20260727.md).

- **Durable per-job success markers** — `~/ambimat_job_logs/<job>_last_success_date`. A marker is
  written **only** when the job exits successfully (rc == 0); a failed/interrupted run is **not**
  marked, so it is retried.
- **Catch-up** — the `*/30` watchdog (and the boot hook) runs a job late if its scheduled time has
  passed today and it has not completed. It never runs a job twice (marker check) and never runs it
  early.
- **Boot hook** — Termux:Boot runs `~/.termux/boot/start-ambimat-jobs` at power-on (no need to open
  Termux): it takes a wake-lock, starts `sshd` and `crond`, (re)installs the crontab, waits for the
  network, then runs the watchdog to catch up anything missed. Log: `~/ambimat_job_logs/boot_startup.log`.
- **Locking** — atomic dir-based locks with stale/dead-owner reclaim ensure that if the scheduler
  and the boot hook fire together, exactly one execution proceeds.
- **Timezone** — the jobs export `TZ=Asia/Kolkata` explicitly, so scheduling never depends on an
  ambiguous default.

18/18 controlled scenario tests for these behaviours pass — harness:
[reports/scheduler_verification/sched_tests.sh](reports/scheduler_verification/sched_tests.sh).
The 12:00 cache monitor adds 39 more scheduling scenarios (its own lock, respecting the 10:00/11:00
locks, same-day duplicate suppression, post-noon reboot catch-up, multiple missed days, IST
handling) — harness: [cache_monitor/tests/sched_tests_noon.sh](cache_monitor/tests/sched_tests_noon.sh).

## Manual run, validation & troubleshooting

- **Connect from the Mac:** `scripts/moto-ssh.sh 'uptime'` (sets up `adb forward tcp:8022` and logs
  in with `~/.ssh/id_moto_playground`). If SSH says *permission denied*, pass the key explicitly:
  `ssh -p 8022 -i ~/.ssh/id_moto_playground u0_a122@127.0.0.1`.
- **Check the scheduler on the phone:** `crontab -l`, `pgrep -x crond`, `pgrep -x sshd`,
  and inspect `~/ambimat_job_logs/*_last_success_date` and `~/ambimat_job_logs/boot_startup.log`.
- **Validate the crawler config parses:** `python -c "import yaml; yaml.safe_load(open('site_monitor/config/sites.yaml'))"`.
- **Byte-compile the Python:** `python -m compileall site_monitor cache_monitor scripts`.
- **Cache monitor (read-only, safe any time):**
  `python3 ~/cache_monitor/front_page_cache_monitor.py --evidence-dir ~/cache_monitor_reports/manual-$(date -u +%Y%m%dT%H%M%SZ) --run-kind manual`.
  Makes one ordinary public request and changes nothing; does not touch the daily marker.
  Its tests: `python3 cache_monitor/tests/test_cache_monitor.py`,
  `bash cache_monitor/tests/sched_tests_noon.sh`, `python3 cache_monitor/tests/audit_no_mutation.py`.
- **Reboot acceptance test:** reboot the phone, do **not** open Termux, wait ~2 min, then from the
  Mac check `boot_startup.log` shows a fresh run and `crond`/`sshd` are up.
- **Report "hang" gotcha (already fixed):** notifications are detached (`/dev/null` FDs +
  `start_new_session`) so a `termux-notification` invoked over SSH can never hold the session open.

## Logs & reports

- **Site-monitor reports (phone):** `~/site_monitor_reports/` — `report_latest.{json,md,html}`,
  timestamped `report_YYYYMMDD_HHMMSS.*`, per-site reports under `per_site/<slug>/`, and
  `daily_runner.log` / `cron.log`. `report_latest.json` also serves as the title-drift baseline.
- **Scheduler logs (phone):** `~/ambimat_job_logs/` (markers, `scheduler_watchdog.log`,
  `boot_startup.log`, `cache_monitor_daily.log`).
- **Cache-monitor evidence (phone):** `~/cache_monitor_reports/noon-cache-inspection-<UTC>/`
  (mode 700) — `result.json`, `SUMMARY.txt`, sanitized headers, parsed metadata, request procedure,
  retry history, scheduler evidence, server evidence, and a self-excluding `EVIDENCE.sha256`.
- **Committed evidence (repo):** `reports/scheduler_verification/`,
  `reports/full_coverage_crawl_20260727/COVERAGE_SUMMARY.md`, and
  `reports/cache_monitor_canary_20260731/` (the single live read-only canary of the noon job).
  Raw crawl dumps and raw telemetry are gitignored by design (keep large/regenerable/sensitive runs
  out of git).

## Safety notes & known limitations

- **Public-crawl indicator, not proof.** The site monitor only sees what is visible on public pages
  at crawl time. It **cannot** prove "a hack was attempted in the last 24h" (that needs
  server/WAF/CMS/Search-Console logs). "Suspicious" findings are advisory **warnings**; only
  high-confidence signals (broken pages, defacement calling-cards, cross-domain redirects,
  scripts/iframes from known-suspicious domains, unreachable site) are raised as **alerts**.
- **GET-only and polite.** No vulnerability scanning, no admin-path probing, no brute force, no
  login attempts; configurable delay + timeouts, bounded page count. It does not modify the sites.
- **Low RAM.** ~130–150 MB free drove the per-site-process design; keep new work memory-bounded.
- **Unrooted device.** `dumpsys`/`/sys` power data is permission-denied from the Termux uid; rich
  sensor/battery/Wi-Fi telemetry needs the Termux:API app (installed). No NFC/compass/barometer.
- **Connectivity.** The phone is on a guest/client-isolated Wi-Fi, so the Mac reaches it over the
  **USB** ADB→SSH bridge (port 8022), not LAN SSH.
- **Battery.** Keep the phone on the charger during the 10:00–11:00 window; heavy Doze on Android 7
  can otherwise delay wake-ups even with the battery whitelist and held wake-lock.
- **Manual setup still required** for the phone-side pieces (Termux:Boot app, `~/seo_tracker/phone/`
  SEO tracker + scheduler, battery whitelist) — these are not provisioned by this repo.
```

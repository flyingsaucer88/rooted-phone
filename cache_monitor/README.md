# ambimat.com front-page cache monitor — 12:00 IST

> **This job never repairs the site.** It looks at the front page, writes down what it
> saw, and tells you. Finding a problem produces an alert and evidence — never an action.
> There is no `--fix`, no purge, no cache warm-up, no "repair mode disabled by default".
> If you want the capability, it does not exist here and must not be added here.

## The three daily jobs (Asia/Kolkata)

| Time | Job | Script (on the phone) | Marker |
|---|---|---|---|
| 10:00 IST | Site monitor (crawl, availability, broken links) | `~/seo_tracker/phone/run_site_monitor_daily.sh` | `site_monitor_last_success_date` |
| 11:00 IST | SEO tracker | `~/seo_tracker/phone/run_daily.sh` | `seo_last_success_date` |
| **12:00 IST** | **Front-page cache inspection (read-only)** | `~/cache_monitor/run_cache_monitor_daily.sh` | `front_page_cache_last_success_date` |
| `*/30` | Self-healing watchdog + catch-up for all three | `~/seo_tracker/phone/ensure_scheduler.sh` | — |

The noon job was added on 2026-07-31. The 10:00 and 11:00 jobs are unchanged.

## What the noon job does

1. Skips if today's inspection already completed (Asia/Kolkata date).
2. Defers if the network is down, or if the 10:00 or 11:00 job still holds its lock.
3. Takes its own non-blocking lock (`cache_monitor_run`), so two noon runs cannot overlap.
4. Makes **one** ordinary public `GET https://ambimat.com/`.
5. Extracts the canonical/social/schema metadata and compares it with
   `config/expected_metadata.json`.
6. If — and only if — read-only server access has been deliberately configured, reads the
   on-disk W3TC cache entry.
7. Classifies, writes evidence, posts a Termux notification, records the day as done.

## The read-only boundary — exactly

Permitted, and nothing else:

* One plain public `GET` with the user agent `AmbimatRootedPhone-CacheMonitor/1.0`.
  No query string, no cookie, no logged-in session, no conditional header
  (`If-None-Match` / `If-Modified-Since`), no `Cache-Control`, no `Pragma`, no
  cache-busting parameter, no purge/refresh header, no origin-only host, no CDN bypass.
* Optionally, these remote commands and no others — the complete set is fixed in
  `SERVER_READ_ONLY_COMMANDS` in `front_page_cache_monitor.py`:
  `wp option get`, `wp cron event list`, `test`, `realpath`, `readlink`, `stat`,
  `sha256sum`. Paths and option names are validated against strict patterns before they
  are shell-quoted into a template. No other string is ever handed to `ssh`.
* Writing its own evidence files, under its own evidence directory.

Never, on any path — scheduled, catch-up, retry, canary or test:

delete / rename / move / truncate / touch / chmod a cache file · purge, flush, clear,
expire, invalidate, refresh, rebuild, regenerate, preload or warm any cache · any W3TC
cache-management command · invoking or deliberately triggering `w3_pgcache_cleanup` ·
`wp cron event run` (with or without `--due-now`) · a cache-bypass request · a second
request to see whether stale content changed · a retry because content is stale · any
WordPress content, option, transient, cron or database write · any SQL that is not a
`SELECT` · any Yoast index/reset/optimize/build/migrate/repair · any featured-image,
attachment, metadata or alt-text change · any W3TC configuration change · any theme,
plugin, MU-plugin, snippet or source change · applying or modifying a rollback ·
resuming Gate C or the five-object canary · touching the other 112 objects.

`tests/audit_no_mutation.py` proves this statically and fails the build if it stops being
true. `tests/test_cache_monitor.py::TestNoMutationPath` includes a negative control that
injects violations into a shadow copy and confirms the audit catches each one.

## Classifications

| Result | Meaning | Conclusive? |
|---|---|---|
| `PASS_HEALTHY_READ_ONLY` | Public request fine, expected metadata present, no known obsolete metadata, server evidence consistent | yes |
| `PASS_PUBLIC_HEALTHY_SERVER_INSPECTION_UNAVAILABLE` | Public evidence healthy; server inspection unavailable or safely skipped | yes |
| `WARN_CACHE_FILE_OVER_LIFETIME` | Cache file older than the configured lifetime, or cleanup overdue, or the resolved path is unexpected. **No repair attempted.** | yes |
| `ALERT_STALE_OR_OBSOLETE_METADATA` | Known obsolete image/metadata served, or required governed metadata absent. **No repair attempted.** | yes |
| `ALERT_PUBLIC_SERVER_MISMATCH` | Public body and the exact server cache file differ. **No repair attempted.** | yes |
| `FAIL_PUBLIC_REQUEST` | The request could not be completed after bounded transport retries | no |
| `BLOCKED_SERVER_INSPECTION` | Auth, permissions, path validation or read-only guarantees prevented server inspection | yes |
| `SKIPPED_ALREADY_COMPLETED` | Today's inspection already ran | — |
| `DEFERRED_MAINTENANCE_LOCK` | The 10:00 or 11:00 job is still running | no |
| `ERROR_MONITOR_INTERNAL` | The monitoring script itself failed | no |

Severity order, worst first: `ERROR_MONITOR_INTERNAL` → `FAIL_PUBLIC_REQUEST` →
`ALERT_STALE_OR_OBSOLETE_METADATA` → `ALERT_PUBLIC_SERVER_MISMATCH` →
`WARN_CACHE_FILE_OVER_LIFETIME` → `BLOCKED_SERVER_INSPECTION` →
`PASS_PUBLIC_HEALTHY_SERVER_INSPECTION_UNAVAILABLE` → `PASS_HEALTHY_READ_ONLY`.

There is deliberately **no** `PASS_NATURAL_RECOVERY`, `PASS_FRONT_PAGE_ONLY_RECOVERY` or
`FAIL_STALE_AFTER_BOUNDED_RECOVERY`. This job performs no recovery, so it cannot report on one.

### Healthy / stale / inconsistent / unverifiable

* **Healthy** — HTTP 200, canonical is `https://ambimat.com/`, `og:image` resolves to the
  governed image `2026/07/ambimat-home-ambimat.com-1200x630-1.png` (attachment 36105), no
  known obsolete image appears in `og:image`, `twitter:image` or the primary schema image,
  and any server evidence agrees.
* **Stale** — a known obsolete path segment appears (today: `2022/05/image_2022.png`,
  attachment 9920), or a required governed field is absent or is not the governed image,
  or the cache file is older than its configured lifetime.
* **Inconsistent** — the public response body's SHA-256 differs from the on-disk cache
  entry's, or the resolved cache path is a symlink / lies outside
  `wp-content/cache/page_enhanced/`.
* **Unverifiable** — the public request never completed (`FAIL_PUBLIC_REQUEST`), or server
  inspection could not be proven read-only (`SERVER_INSPECTION_UNAVAILABLE` /
  `BLOCKED_SERVER_INSPECTION`). A successful public inspection is always reported
  separately from unavailable server evidence.

## Evidence collected

Every execution writes `~/cache_monitor_reports/noon-cache-inspection-<UTC>/` (mode 700,
files 600):

`result.json` (machine-readable) · `SUMMARY.txt` · `notification.txt` ·
`response-headers.txt` (sanitized) · `parsed-metadata.txt` · `request-procedure.txt` ·
`retry-history.txt` · `scheduler.txt` · `server-inspection.txt` · `EVIDENCE.sha256`
(checksums every file **except itself**).

Public evidence: request timestamp, final URL, HTTP status, redirect chain, response time,
`Content-Type`, content length, body SHA-256, `Age` (when emitted), `Cache-Control`,
`Expires`, `ETag`, `Last-Modified`, `X-Cache` / W3TC / CDN cache headers when present,
canonical, `og:image` (+ width/height), `twitter:image`, primary schema image, and whether
any known obsolete front-page image or metadata appears.

Server evidence when available: `siteurl`, `home`, resolved cache-file path, existence,
regular-file / symlink, owner, group, mode, mtime, calculated age, size, SHA-256, whether
it matches the public body, configured lifetime, `w3_pgcache_cleanup` next run, and whether
cleanup appears overdue.

`result.json` always carries `mutation_attempted: false`, `repair_attempted: false`,
`public_request_count`, and `server_commands_read_only` (`true` / `false` / `unavailable`).

Credentials, keys, salts, cookies and tokens are never written. Cookie, authorization and
authenticate headers are dropped before anything is recorded.

## Catch-up, locking and retries

* **Catch-up** — `ensure_scheduler.sh` (cron `*/30` and Termux:Boot) calls
  `amb_run_if_due front_page_cache 1200 …`. After a reboot at any time past 12:00 with
  today's inspection unrun, it runs **once**. Before 12:00 it does not run. If the phone
  was off for days it runs once for the current day and never replays historical dates.
  The catch-up run carries exactly the same read-only restrictions as the scheduled run.
* **Locking** — its own `cache_monitor_run` lock (non-blocking, stale/dead-owner reclaim);
  it also refuses to start while `site_run` or `seo_run` is held by a live process.
* **Duplicate suppression** — `front_page_cache_last_success_date` in
  `~/ambimat_job_logs/`, an Asia/Kolkata date. Written for **any conclusive inspection**,
  including a stale ALERT — a stale result is a completed inspection, not a failed
  scheduling run, so the catch-up system does not re-inspect the same stale page all
  afternoon. Not written for `FAIL_PUBLIC_REQUEST` or `ERROR_MONITOR_INTERNAL`.
* **Retries** — only for transport failures that prevented an inspection: DNS, connection,
  TLS, timeout, HTTP 429 (honouring `Retry-After`, capped at 120 s) and temporary 5xx.
  Max 3 attempts, spaced 20 s then 45 s. Retries are never used to wait for stale content
  to change, to trigger WP-Cron, to cause cleanup, to warm the cache, or to check whether
  a repair occurred. **Once a valid response is captured, no further public request is
  made during that run.**

## Manual read-only inspection (safe to run any time)

```bash
ssh -i ~/.ssh/id_moto_playground -p 8022 u0_a122@127.0.0.1
python3 ~/cache_monitor/front_page_cache_monitor.py \
  --evidence-dir ~/cache_monitor_reports/manual-$(date -u +%Y%m%dT%H%M%SZ) \
  --run-kind manual
```

This makes the same single ordinary request and changes nothing. It does not touch the
daily marker, so it neither suppresses nor triggers the scheduled run.

## Disabling only the noon job

```bash
~/cache_monitor/install_noon_job.sh remove     # removes ONLY the 12:00 line
```

The 10:00, 11:00 and watchdog lines are untouched. To also stop the watchdog catch-up,
delete the `ambimat-cache-monitor` block at the end of
`~/seo_tracker/phone/ensure_scheduler.sh` (backup: `ensure_scheduler.sh.bak-20260731`).
Leaving the block in place while the runner is absent is harmless — it logs and skips.

## Scheduler rollback

```bash
cp ~/seo_tracker/phone/ensure_scheduler.sh.bak-20260731 ~/seo_tracker/phone/ensure_scheduler.sh
~/cache_monitor/install_noon_job.sh remove
rm -rf ~/cache_monitor                  # optional; evidence lives in ~/cache_monitor_reports
```

That restores the exact pre-2026-07-31 three-job scheduler. Nothing on the website is
involved in a rollback of this job, because this job never changed the website.

## After a stale-cache alert — what to do

The alert is information. **Do not treat it as authorization to change anything.**

1. Read the evidence directory named in the notification. `parsed-metadata.txt` says which
   field carried which obsolete image; `request-procedure.txt` proves what was requested.
2. Compare `Last-Modified` / `ETag` / body SHA-256 with the previous run's evidence to see
   whether the same cache entry is still being served, and for how long.
3. Decide, as a human, under a separate and explicitly authorized procedure, what (if
   anything) should be done. Then do it under that procedure.

> **Warning — never run a global W3TC flush** in response to this alert. A site-wide purge
> regenerates every page at once on shared hosting and has a far larger blast radius than
> the single front-page entry the alert concerns.
>
> **Warning — a stale alert does not authorize Gate C, any Yoast work, any cache clearing,
> or any featured-image change.** It authorizes reading. Nothing more.
>
> No ready-to-run cache-deletion or repair command is documented here, deliberately.
> Remediation belongs to a separate, explicitly authorized procedure — not to this runbook
> and not to this job.

## Optional read-only server inspection

Absent by default; the job reports `PASS_PUBLIC_HEALTHY_SERVER_INSPECTION_UNAVAILABLE` and
inspects the public page only. To enable it, copy
`config/server_inspection.example.json` to `config/server_inspection.json` on the phone,
set `enabled: true`, and point `identity_file` at a credential you deliberately provisioned
for this device — a **read-only** account is the right shape. `config/server_inspection.json`
is git-ignored and must never be committed.

Enabling it cannot widen what the job may do: the remote command set is fixed in code.

## Tests

```bash
python3 cache_monitor/tests/test_cache_monitor.py    # 58 offline fixture tests
bash    cache_monitor/tests/sched_tests_noon.sh      # 39 scheduling scenarios
python3 cache_monitor/tests/audit_no_mutation.py     # static read-only audit
```

The fixture suite blocks all socket creation before it runs, so it cannot reach the
internet. The scheduling suite runs the real `run_cache_monitor_daily.sh` and the real
`lib_common.sh` against an isolated temp `AMBIMAT_HOME` with a stub engine — no real
crontab, marker, lock, evidence directory or website is touched.

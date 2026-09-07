# Run history — reconstructed from phone-side job logs

All timestamps **Asia/Kolkata (IST, +05:30)**, as recorded on the device.
Source: `~/ambimat_job_logs/{site_monitor_daily,seo_daily,cache_monitor_daily,measurement_queue,boot_startup}.log`
(archived in `raw/phone_home_subset.tar.gz`).

## Boot history relevant to missed work — OBSERVED

| Boot (IST) | Note |
| --- | --- |
| 2026-07-27 11:49:47 | routine |
| 2026-09-01 15:22:41 | phone was off through 10:00/11:00/12:00 → all three caught up 15:23–15:59 |
| **2026-09-07 12:34:29** | **phone was off through 10:00/11:00/12:00 → all three caught up 12:35–13:11** |

Device uptime at audit time: 2h23m (booted 2026-09-07 ~12:33 IST). There is **no boot
record for 2026-09-06** — the phone was powered off for that entire calendar day.

## Daily jobs — last 7 logical days — OBSERVED

| Logical date | 10:00 site monitor | 11:00 SEO | 12:00 cache monitor |
| --- | --- | --- | --- |
| 2026-09-01 | SUCCESS 15:43:13 (late, post-boot catch-up) | SUCCESS 15:59:07 (catch-up) | SUCCESS 15:59:12 (catch-up) |
| 2026-09-02 | SUCCESS 10:20:31 | SUCCESS 11:13:44 | SUCCESS 12:00:13 |
| 2026-09-03 | SUCCESS 10:25:29 | SUCCESS 11:13:25 | SUCCESS 12:00:04 |
| 2026-09-04 | SUCCESS 10:20:08 | SUCCESS 11:13:46 | SUCCESS 12:00:03 |
| 2026-09-05 | SUCCESS 10:23:28 | SUCCESS 11:14:08 | SUCCESS 12:00:05 |
| **2026-09-06** | **MISSED — phone off all day** | **MISSED — phone off all day** | **MISSED — phone off all day** |
| **2026-09-07** | **SUCCESS 12:56:06 (catch-up)** | **SUCCESS 13:11:07 (catch-up)** | **SUCCESS 13:11:12 (catch-up)** |

`site_monitor_last_success_date`, `seo_last_success_date` and
`front_page_cache_last_success_date` all read `2026-09-07`.

2026-09-06 was **never** backfilled and never will be: catch-up is deliberately
same-logical-day only (see `docs/` scheduler verification). This is correct
behaviour, not a defect — a day-old availability crawl has no operational value.

## Completion verified, not merely claimed — VERIFIED

A success marker alone is not evidence. Each 2026-09-07 run was checked for real output:

| Job | Marker | Artefact produced | Real work? |
| --- | --- | --- | --- |
| Site monitor | 2026-09-07 | `report_latest.json` `generated_at=2026-09-07T12:56:05+05:30`, `sites_reported=7`, `pages_crawled=830`, `partial=false`, `missing_site_reports=[]` | YES — 7 distinct per-site crawls |
| SEO tracker | 2026-09-07 | `report_20260907_131107.json`, 7 domains, `total_pages=625`, `avg_ai_readiness=71.3` | YES |
| Cache monitor | 2026-09-07 | `noon-cache-inspection-20260907T074109Z`, `PASS_PUBLIC_HEALTHY_SERVER_INSPECTION_UNAVAILABLE`, `conclusive=True` | YES |

No log claims success for incomplete work. No job is stuck, hung or queued. No stale
locks were present (`~/ambimat_job_logs/.*.lock` — none). No orphaned Python, crawler,
Termux-API or SSH processes were found.

## One-shot measurement queue — OBSERVED

| run_id | Intended (IST) | Status before repair | True blocker |
| --- | --- | --- | --- |
| `v2x_seo_measurement_20260827` | 2026-08-27 01:00 | blocked, verdict *AUTHENTICATED DATA SOURCE UNAVAILABLE* | **prompt file never installed** (mislabelled) |
| `ambisecure_gsc_7day_20260829` | 2026-08-29 01:00 | blocked, verdict *AUTHENTICATED DATA SOURCE UNAVAILABLE* | **prompt file never installed** (mislabelled) |
| `ambimat_ga4_gsc_20260829` | 2026-08-29 01:00 | scheduled (never attempted) | starved: depends on `ambisecure_gsc_7day_20260829`, which can never complete |
| `esim_phase3b4_20260901` | 2026-09-01 01:00 | blocked, verdict *AUTHENTICATED DATA SOURCE UNAVAILABLE* | **genuine** — credential directory is empty |

First BLOCKED notification ever shown on the phone screen: **2026-08-27 01:00:06 IST** (V2X).
First *genuine* authentication block: **2026-09-01 01:00:15 IST** (eSIM).
Retry is bounded at 6 attempts/IST day per run, so these repeat but do not loop.

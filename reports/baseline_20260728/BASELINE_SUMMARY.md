# Baseline — 2026-07-28

First run with **full coverage on both jobs simultaneously**, and therefore the reference
baseline for future diffs. Supersedes `reports/full_coverage_crawl_20260727/` (site monitor only;
that day's SEO run was truncated to 160 pages).

Both jobs ran unattended from cron on the phone and succeeded:

| Job | Cron | Finished | Coverage |
|---|---|---|---|
| Site monitor | 10:00 IST | 10:24 | 7/7 sites, 921 pages |
| SEO tracker | 11:00 IST | 11:21 | 7/7 domains, 864 pages |

Success markers `~/ambimat_job_logs/{site_monitor,seo}_last_success_date` both read `2026-07-28`.
No missed runs, no watchdog catch-up.

## Files

| File | Contents |
|---|---|
| `site_monitor_20260728.json` / `.md` | merged 7-site crawl (phone `report_20260728_102418.*`) |
| `seo_tracker_20260728.json` / `.md` | 7-domain SEO run (phone `report_20260728_112148.*`) |

These are committed with `git add -f` — `.gitignore` excludes raw report dumps by default.
This directory is a deliberate, occasional exception so there is a versioned reference to diff
against; daily runs should stay out of git.

## Site monitor totals

```
sites_total 7   sites_reported 7   sites_unreachable 0   sites_timed_out 0
pages_crawled 921   broken_pages 22   broken_links 29   unverified_links 5
suspicious_warnings 695   partial false
```

## Per-site state

| Site | Pages | Alerts | Warnings | TLS days | Security headers |
|---|---|---|---|---|---|
| ambimat.com | 462 | 22 (all false positives, see below) | 492 | 38 | missing CSP, XFO, XCTO |
| ambisecure.ambimat.com | 318 | 0 | 72 | 46 | all present |
| ambiautomation.ambimat.com | 28 | 0 | 0 | 52 | all present |
| esim.ambimat.com | 33 | 0 | 67 | 70 | all present |
| ambipower.ambimat.com | 27 | 0 | 3 | 46 | missing XFO |
| orders.ambimat.com | 50 | 0 | 61 | 51 | missing XFO, XCTO, referrer-policy, **HSTS** |
| roboracer.ambimat.com | 3 | 0 | 0 | 72 | all present |

## Known distortions in this snapshot

**The 22 ambimat.com `broken-page` alerts are false positives** produced by the crawler bug fixed
in c8e0af2 (relative links resolved against the pre-redirect URL). All 22 paths return 200 on
`ambisecure.ambimat.com`. This baseline is stored **as generated**, un-doctored; the next run
after the fix should show ambimat.com alerts drop 22 → 0. Treat that drop as the fix landing,
not as 22 pages being repaired.

Genuinely fixed on this day vs. 2026-07-27: five real 404s now 301 correctly
(`/design/ambi-iot/ambiiot-medicals/`, `/design/ambi-iot/digital-receipt-printer/`,
`/design/design-services/java-card-applet/`, `/test-reports/`, and a malformed SELECT-FILE URL).

**SEO trend deltas in `seo_tracker_20260728.json` are misleading.** It reports
`avg_ai_readiness: -12.0` and `weak_pages_high: +68` against the previous run, but that run
covered 160 pages vs. 864 here (Ambimat and AmbiSecure capped at 40 each; Orders and RoboRacer
absent entirely). The decline is a coverage artifact, not a regression. Use this file — not the
delta — as the zero point.

**`broken_outbound` in the SEO report over-reports.** It flags internal links whose target is not
in the crawled HTML page set, so PDFs, `sitemap.xml`, ZIPs, `noindex` pages and trailing-slash
redirects appear as "broken" while returning 200. Verified live on this date: the AmbiSecure deck
PDF, the eSIM sitemap, AmbiPower `/resources/downloads/` and `/presentation/deck/`, the RoboRacer
board PDF/ZIP, and Orders `/shipping-policy` are all reachable. The only genuinely dead outbound
link is AmbiPower's Play Store listing for `com.ambimat.meterapp` (404). This bug is in the
phone-resident SEO tracker (`~/seo_tracker/phone/`), not in this repo.

**External 403/401s are bot blocks, not breakage** — sciencedirect, entrust, iso.org, cloudflare,
fbi.gov, gsma.com, business-standard, pib.gov.in, addtoany (×17 on Orders), slack signup.

## SEO metrics

```
total_pages 864   avg_ai_readiness 40.1   total_orphans 21
weak_pages_high 69   audit_high 4   audit_medium 41
```

| Domain | Pages | AI readiness | Quality | Schema cov | Orphans | Under-linked |
|---|---|---|---|---|---|---|
| Ambimat | 437 | 41.1 | 92.4 | 1.00 | 12 | 232 |
| AmbiSecure | 318 | 37.1 | 95.4 | 1.00 | 1 | 89 |
| eSIM | 33 | 59.9 | 100.0 | 1.00 | 0 | 1 |
| AmbiPower | 25 | 50.6 | 100.0 | 1.00 | 0 | 4 |
| AmbiAutomation | 22 | 52.1 | 100.0 | 1.00 | 0 | 0 |
| Orders | 26 | 12.5 | 63.3 | 0.50 | 8 | 2 |
| RoboRacer | 3 | 27.3 | 88.3 | 1.00 | 0 | 0 |

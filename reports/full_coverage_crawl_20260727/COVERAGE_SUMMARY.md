# Full-Coverage Site-Monitor Crawl — 2026-07-27 (on-device, per-site processes)

Definitive full-coverage run executed **on the phone only** (Moto G4 Plus, Termux, Asia/Kolkata)
via the rewritten `run_daily.sh` per-site orchestrator. Each site crawled in its own memory-bounded
Python process (`--only`), then merged into one combined report. Detached, wake-lock held.

- Start: `2026-07-27 14:03:02 +0530` — End: `ORCH_DONE rc=0 @ 14:22:21` (~19 min).
- Combined report: `report_full_coverage.{md,json}` (copied from phone `site_monitor_reports/report_latest.*`).

## Totals

| metric | value |
|---|---|
| sites_total / reported | 7 / 7 |
| sites_unreachable | 0 |
| sites_timed_out | 0 |
| missing_site_reports | none |
| partial | **false** (nothing truncated by cap or time budget) |
| pages_crawled | **917** |
| sites_with_alerts | 1 (Ambimat) |
| broken_pages | 5 |
| broken_links | 23 (all external) |
| unverified_links | 8 |
| warnings | 692 |
| external_links_checked | true |

## Per-site

| site | pages | timed_out | alerts | broken_pages | broken_ext | warnings |
|---|---|---|---|---|---|---|
| Ambimat (ambimat.com) | 458 | no | 5 | 5 | 3 | 489 |
| AmbiSecure | 318 | no | 0 | 0 | 0 | 72 |
| Ambimat eSIM | 33 | no | 0 | 0 | 3 | 67 |
| AmbiAutomation | 28 | no | 0 | 0 | 0 | 0 |
| AmbiPower | 27 | no | 0 | 0 | 1 | 3 |
| Orders | 50 | no | 0 | 0 | 15 | 61 |
| RoboRacer | 3 | no | 0 | 0 | 1 | 0 |

`timed_out=false` on every site with a per-site cap of 800 pages ⇒ this is the **full crawlable set**,
not a truncated sample. (Ambimat's sitemap lists ~697 URLs; 458 is the deduped set of live, crawlable
HTML pages after excluding non-HTML assets, redirects, and the 5 URLs that 404.)

## Real findings worth acting on

**5 broken internal pages on ambimat.com (all HTTP 404):**
- `/design/design-services/java-card-applet/`
- `/test-reports/`
- `/design/ambi-iot/digital-receipt-printer/`
- `/design/ambi-iot/ambiiot-medicals/`
- `/section-5-basic-organizations/6.11 SELECT FILE command` — malformed link (contains a space);
  looks like a bad anchor extracted from document text rather than a real page.

**1 possibly-real broken external link:**
- `https://play.google.com/store/apps/details?id=com.ambimat.meterapp` → 404 (linked from AmbiPower).
  The Play Store listing for the meter app may have been unpublished/removed — worth confirming.

## Noise (not real breakage — recommend suppressing)

- **22 of 23 "broken external links" are bot-hostile false positives:** `addtoany.com` social-share
  widgets (×15, all 403), `investopedia.com`/`forbes.com` (403), `cisa.gov`/`gsma.com` (403),
  `pib.gov.in` (401), `robo-racer.slack.com/signup` (403). These hosts reject bot HEAD/GET by policy.
  **Recommendation:** add `addtoany.com` (and optionally the gov/press hosts) to
  `alerts.external_check_skip_hosts` in `site_monitor/config/sites.yaml`, matching the existing
  twitter/facebook/linkedin handling. This removes the bulk of the external-link noise.
- **692 warnings are dominated by `suspicious-pattern` (573)** — keyword matches on words like
  hack/clone/attack/crack that appear legitimately in security-product marketing copy. These are
  **warnings, not alerts**, by design. The `defacement-marker-in-content` entries (11 total) are the
  corroboration-downgraded cases (marker present in body but NOT in title/H1) — working as intended;
  none escalated to a defacement ALERT.

## Verdict for coverage

Full coverage achieved on all 7 production domains in one memory-bounded on-device run, no OOM, no
timeouts, no truncation. The only true site defects are the 5 ambimat.com 404s and the possibly-removed
Play Store listing; everything else is expected warning-level noise or bot-rejection false positives.

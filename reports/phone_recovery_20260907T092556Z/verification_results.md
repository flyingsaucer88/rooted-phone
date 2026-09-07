# Post-repair verification — 2026-09-07

## Controlled full monitoring run — VERIFIED

Executed on the phone after the config repair, all nine configured sites,
one Python process per site.

* Site monitor: started **15:05:40 IST**, ended **15:24:46 IST**, merge `rc=0`
* SEO tracker: started ~15:39 IST, ended **15:56:02 IST**, `rc=0`

### Per-site results

| Site | Availability (10:00 job) | Pages crawled | SEO check (11:00 job) | SEO pages | Sitemap | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| ambimat.com | **PASS** (reachable) | 344 | **PASS** | 228 | index, 8 children | 1 broken page: `/products/` → 404 |
| ambisecure.ambimat.com | **PASS** | 342 | **PASS** | 308 | 308 URLs | none |
| ambipower.ambimat.com | **PASS** | 28 | **PASS** | 26 | 26 URLs | none |
| ambiautomation.ambimat.com | **PASS** | 28 | **PASS** | 22 | 22 URLs | none |
| **v2x.ambimat.com** | **PASS (first ever)** | 62 | **PASS (first ever)** | 62 | 62 URLs | none |
| **ai.ambimat.com** | **PASS (first ever)** | 8 | **PASS (first ever)** | 7 | 7 URLs | none (see note) |
| roboracer.ambimat.com | **PASS** | 8 | **PASS** | 8 | 8 URLs | none |
| orders.ambimat.com | **PASS** | 49 | **PARTIAL** | **0** | **404 — no sitemap** | 15 external `addtoany.com` 403s (bot-blocked, false positives) |
| esim.ambimat.com *(not one of the eight)* | **PASS** | 33 | **PASS** | 33 | 33 URLs | none |

Totals: `sites_total=9, sites_reported=9, sites_unreachable=0, pages_crawled=902,
broken_pages=1, partial=false, missing_site_reports=[]`.
SEO: `domain_count=9, total_pages=694, avg_ai_readiness=66.7, audit_high=0`.

**Notes on the two non-green cells** — both are pre-existing site-side issues, not phone faults:

* **orders SEO = 0 pages.** The SEO tracker is sitemap-driven and
  `orders.ambimat.com/sitemap.xml` returns 404. Verified pre-existing: the 2026-09-05
  report also shows `Orders: 0`. The *availability* monitor is link-discovery-driven and
  covers Orders fully (49 pages), so the site is not unmonitored — only its SEO analysis
  is empty. Fixing it needs a sitemap on the site, not a phone change.
* **ai.ambimat.com `<title>`** leaks an HTML comment from the prerender template. Reported,
  not fixed — production sites were not modified in this audit.

## Authenticated data retrieval — PARTIALLY VERIFIED

* **Transport verified**: `api/smoke.py reachability` at 15:06:58 IST — all six critical
  endpoints TLS 1.3 OK; only optional `api.linkedin.com` reset.
* **Retrieval NOT verified**: it cannot be, because no credential exists to authenticate
  with. `smoke.py full` requires the owner-supplied service account. This is stated as
  UNRESOLVED rather than papered over.
* **The warning was not hidden.** eSIM still reports
  `BLOCKED — AUTHENTICATED DATA SOURCE UNAVAILABLE`, because that is still true.

## Phone UI / notification tray — VERIFIED

Read back live with `termux-notification-list` after the repair:

```
eSIM — AUTHENTICATED DATA SOURCE UNAVAILABLE   <- genuine, correctly labelled
AmbiSecure — SOURCE PROMPT NOT INSTALLED       <- was mislabelled as auth
V2X — SOURCE PROMPT NOT INSTALLED              <- was mislabelled as auth
Ambimat Site Monitor | ALERT: 1 broken pages, …
SEO tracker ✓ | Daily crawl done
Ambimat front-page cache | PASS_… | No repair attempted.
```

A failed **site** is now visually distinct from an unavailable **data source**, and the
status is not misleadingly green while a data source is missing.

Unrelated, out of scope, left alone: an Android "Sign in required — ravikumar.c@ciright.com"
banner from Google Play Services. It is not produced by any Rooted Phone component.

## Test results

| Suite | Where | Result |
| --- | --- | --- |
| `tests/test_site_inventory.py` (**new**) | Mac | **4 passed, 0 failed** |
| `measurement_queue/tests/test_measurement_queue.sh` | phone | **49 passed, 0 failed** (was 47 + 2 new assertions groups) |
| `sched_tests.sh` (scheduler scenarios) | phone | **18 passed, 0 failed** |
| `cache_monitor/tests/sched_tests_noon.sh` | phone | **39 passed, 0 failed** |
| `cache_monitor/tests/test_cache_monitor.py` | Mac + phone | **58 tests, OK** (both) |
| `cache_monitor/tests/audit_no_mutation.{py,sh}` | Mac | **PASS** (no mutation path exists) |
| `site_monitor/tests/test_redirect_base.py` | phone | **4 passed** |

**Total: 172 automated assertions + 2 static audits, 0 failures.**

Negative-tested the new guard: deleting `V2X` from `sites.yaml` fails
`test_mandatory_sites_present` and `test_both_inventories_agree`, then passes again on
restore. The guard is not vacuous.

## Process hygiene after all runs — VERIFIED

`ps` on the phone shows no Python, crawler, merge, notification, Termux-API or orphaned
SSH processes. No lock directories remain in `~/ambimat_job_logs/`.

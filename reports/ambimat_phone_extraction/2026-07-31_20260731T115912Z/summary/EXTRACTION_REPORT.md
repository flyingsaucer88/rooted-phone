# Ambimat.com — Today's Phone Evidence Extraction

**Extraction run:** 2026-07-31 (Asia/Kolkata)
**Extraction directory:** `reports/ambimat_phone_extraction/2026-07-31_20260731T115912Z/`
**Mode:** inspection + extraction only. No repair, no rerun, no website request, no GSC archive processed.

> Everything in sections 3, 4, 9 and 10 is **what the phone's reports say about the state of the
> site at ~10:00–11:22 IST today**. It is not a statement about the site right now, and nothing here
> was re-verified against the live site — by design.

---

## 1. Phone connection result

Connected successfully using the project's established bridge (`scripts/moto-ssh.sh` pattern):
`adb forward tcp:8022 tcp:8022` → `ssh -p 8022 u0_a122@127.0.0.1` with `~/.ssh/id_moto_playground`.

| Item | Value |
| --- | --- |
| Device (adb) | `ZY22382BFL` — Moto G (4), `athene_f`, transport usb:20-1 |
| Android | 7.0 (SDK 24), kernel `3.10.84-ge03508d`, armv7l |
| Termux user | `u0_a122`, `PREFIX=/data/data/com.termux/files/usr`, 696 binaries |
| Device timezone | `persist.sys.timezone = Asia/Calcutta` |
| Phone clock | `2026-07-31 17:26:46 IST +0530` (epoch 1785499006) |
| Workstation clock | `2026-07-31 17:26:22 IST` / `2026-07-31 11:56:22 UTC` |
| Clock agreement | within ~1 s — no timestamp skew adjustment needed |
| Phone uptime | ~366 593 s ≈ 4.24 days → last boot ≈ 2026-07-27 ~11:56 IST. **No reboot today.** |
| Workstation | `Neels-MacBook-Pro.local`, user `neelshah`, darwin 25.5.0 |

No package was installed and no connectivity setting was changed. `sha256sum` was already present in
Termux, so **source-side hashes were computed on the phone** with no installation.

## 2. Date and timezone used

Today = **2026-07-31, Asia/Kolkata (+05:30)**. Every phone log line and every report timestamp used
below carries an explicit `+0530` offset or an IST-local `report_YYYYMMDD_HHMMSS` filename. Candidate
selection was driven by these **embedded** timestamps, not by filesystem mtime.

## 3. 10:00 live-page / site-monitor run — `COMPLETE`

| Field | Value |
| --- | --- |
| Scheduled | 10:00 IST |
| Actual start | 2026-07-31 **10:00:02** +0530 |
| Actual end | 2026-07-31 **10:25:04** +0530 (whole 7-site job) |
| ambimat.com segment | **10:00:03 → 10:15:56** +0530 |
| Task | `~/site_monitor/run_daily.sh` (per-site mode) |
| Exit status | ambimat crawler `rc=0`; merge `rc=0`; job `rc=0` |
| Trigger | watchdog catch-up path: `10:00:03 site_monitor: catching up (now=1000, due=1000)` — the **normal** daily trigger on this device, not a missed-run recovery |
| ambimat pages | **461** crawled (461 page records in JSON) |
| Errors | 0 broken pages · 0 broken internal links · 2 broken external links · 3 unverified external links · 0 alerts · 492 advisory warnings |

**Completion markers (all four present):**
`daily_runner.log` → `===== 2026-07-31 10:25:04 +0530 daily run end (merge rc=0) =====`;
`site_monitor_daily.log` → `site_monitor: success (2026-07-31)`;
`site_monitor_last_success_date` → `2026-07-31`;
report JSON parses cleanly with `totals.partial = false`, `timed_out = false`.

**Lock-contention note (not a failure):** `site_monitor_daily.log` logs `10:00:03 … lock held; skipping`.
That is a *second* trigger declining the lock while the first run held it. The holding run ran to
`end rc=0` at 10:25:04. This is the same pattern seen on 07-28/29/30, all of which also succeeded.
No notification or SSH-helper behaviour is visible in any log as having affected the crawl.

**Caveats recorded, not resolved:**
- 461 pages is below the 800-page cap and below the "~697 sitemap pages" figure in `sites.yaml`,
  yet the run reports neither timeout nor partial output. Scope/robots/link-discovery difference is
  the likely reason; **not investigated** (would require a crawl, which is out of scope).
- `totals.sites_ok = 0` while `sites_with_alerts = 0` — the tool only counts a site "ok" with zero
  warnings, and 492 advisory warnings were present.

## 4. 11:00 SEO run — `COMPLETE`

| Field | Value |
| --- | --- |
| Scheduled | 11:00 IST |
| Actual start | 2026-07-31 **11:00:02–11:00:04** +0530 (watchdog catch-up launch) |
| Actual end | 2026-07-31 **11:22:13** +0530 |
| Task | `seo_tracker/phone_seo.py`, mode `phone-crawl-only` |
| Exit status | catch-up runner `rc=0`; SEO run `rc=0` |
| ambimat pages | **437** crawled, 845 keywords tracked |
| Errors | audit 1 high / 17 medium / 464 low · 30 high-severity weak pages · 12 orphans · 492 "broken outbound" internal-link records (see §11) |

**Completion markers (all four present):**
`daily_runner.log` → `Phone SEO run complete (crawl-only).` then `===== 2026-07-31 11:22:13 +0530 SEO run end (rc=0) =====`;
`seo_daily.log` → `seo: success (2026-07-31)`; `seo_last_success_date` → `2026-07-31`;
report JSON parses cleanly with `generated_date = 2026-07-31`.

Same benign lock pattern as the 10:00 job (`11:00:03 seo: lock held; skipped`, then success at 11:22:13).

## 5. Files discovered

Read-only discovery covered `~/site_monitor_reports/` (587 entries), `~/site_monitor_reports/per_site/`
(7 host directories), `~/seo_tracker_reports/`, `~/seo_tracker_reports/history/`, and `~/ambimat_job_logs/`.

Today-dated outputs found: the ambimat per-site report pair, the merged 7-site report pair + HTML, the
SEO report pair + HTML + `summary_history.json`, and five scheduler/runner logs. Six sibling per-site
report sets (AmbiSecure, AmbiAutomation, eSIM, AmbiPower, Orders, RoboRacer) were found and
**deliberately excluded** — their primary target is another host. All prior-day reports were excluded
as not-today. Every excluded candidate is listed in the inventory with its reason.

## 6. Files copied

**29 files**, all via `scp -p` (copy, never move), preserving filenames, contents and mtimes, laid out
mirroring the phone's relative paths:

| Category | Count | Contents |
| --- | ---: | --- |
| `raw/site_monitor/` | 10 | ambimat per-site report (`.json`/`.md`, timestamped + `_latest` + `.html`), merged 7-site report (`.json`/`.md`), merged `report_latest.html`, `daily_runner.log`, `cron.log` |
| `raw/seo/` | 8 | SEO report (`.json`/`.md` timestamped + `_latest`), `report_latest.html`, `daily_runner.log`, `cron.log`, `history/summary_history.json` |
| `raw/scheduler/` | 11 | `scheduler_watchdog.log`, `site_monitor_daily.log`, `seo_daily.log`, both `*_last_success_date`, `missed_run.log`, `missed_cron.log`, `cron_5min_probe.log`, `boot_startup.log`, plus the two run configs (`sites.yaml`, `phone/config.yaml`) as run context |

The merged 7-site report is multi-host by construction; it is retained because it is the 10:00 job's
own deliverable, and only its ambimat rows were carried into the summaries.

**Secret handling:** all 29 copied files were scanned for private keys, `ssh-rsa` blobs, bearer tokens,
AWS keys, `password=`/`api_key=`/`client_secret`/`refresh_token` patterns. **0 hits — no redaction was
required, and no credential, key, cookie, token or unrelated personal data was copied.**

## 7. Transfer-integrity results

SHA-256 computed **on the phone before copying** and again on each workstation copy:

- **29 / 29 hashes match**, **29 / 29 sizes match**. Zero mismatches.
- Post-parse re-hash of `raw/` confirms the copied evidence was not edited during parsing.
- Post-extraction re-hash **on the phone**: **28 / 29 byte-identical**. The single difference is
  `ambimat_job_logs/scheduler_watchdog.log`, which grew 227 901 → 228 103 bytes because the phone's
  **own** half-hourly watchdog appended its 17:30 tick during this session. Verified as append-only:
  `head -c 227901` of the live file hashes to exactly the value captured before copying, and the 202
  appended bytes are three lines reading `wake-lock acquired` / `site_monitor: already succeeded today
  (2026-07-31); skip` / `seo: already succeeded today (2026-07-31); skip`. **That append was made by the
  device's own timer, not by this extraction, and it explicitly records that no job was launched.**

Full manifest: `checksums/SHA256SUMS`. Per-file source/copy hashes: `inventory/phone_evidence_inventory.csv`.

## 8. Counts extracted

| Artifact | Rows |
| --- | ---: |
| `inventory/phone_evidence_inventory.csv` | 38 (29 included + 9 excluded candidates) |
| `summary/site_monitor_results.csv` | 466 (461 internal URLs + 5 external link checks) |
| `summary/seo_results.csv` | 1 221 |
| `summary/execution_status.json` | 2 runs, independently classified |

## 9. Findings reported by the phone for `ambimat.com`

### 9a. From the 10:00 site-monitor run (state at ~10:00–10:15 IST)

- **Reachability:** `https://ambimat.com` → 200, no redirect, final URL `https://ambimat.com/`.
- **All 461 crawled internal URLs returned HTTP 200.** Zero broken pages, zero broken internal links,
  zero title drift, zero alerts.
- **TLS:** certificate for `ambimat.com` valid to `Sep 5 04:12:51 2026 GMT` — **35 days** at crawl time.
- **Security headers:** present `referrer-policy`, `strict-transport-security`; missing
  `content-security-policy`, `x-frame-options`, `x-content-type-options`.
- **robots meta:** 450 pages `index, follow, …`; **10 pages `noindex, follow`** — all of them
  `/category/general/` and its `page/2/`…`page/10/` pagination. The same 10 URLs are the only ones
  reported missing a canonical.
- **Metadata:** 0 pages missing a title, 0 missing an H1, **136 missing a meta description** (mostly
  `/tag/*` and `/category/*` archives), 17 duplicate-title groups, 13 duplicate-description groups.
- **Canonicals:** 7 pages carry a canonical pointing elsewhere — including `/about/` → `/about/company-overview/`,
  `/design/design-by-technology/sound/` → `/design/ambi-iot/sound/`, `http://ambimat.com/contact/` →
  `https://ambimat.com/contact/`, and `/design/design-services/java-card-applet/` →
  `https://ambisecure.ambimat.com/services/javacard-development/` (also logged as an `offsite-redirect`).
- **492 advisory warnings**, which the report's own `limitation` field states are *"advisory WARNINGS to
  investigate, not confirmed compromise"*:

  | Warning type | Count | What the phone actually recorded |
  | --- | ---: | --- |
  | `suspicious-pattern` | 460 | matches on `display:none` / `visibility:hidden` / `opacity:0` — ubiquitous in ordinary theme CSS |
  | `external-iframe` | 23 | Google reCAPTCHA fallback, Google Maps embed, and WordPress `/embed/` iframes of cited third-party articles |
  | `defacement-marker-in-content` | 2 | phrase "hacked by" on `/cyber-attacks-in-india/` and `/is-there-a-secure-way-to-distribute-passwords-in-an-organisation/`; the tool itself annotates both *"likely editorial (title looks normal, 1225/753 words); verify manually"* |
  | `suspicious-external-link` | 2 | substring `pharma` in `pharmaceuticalcommerce.com`, and a `cryptomathic.com` PDF matching `crypto` |
  | `japanese-spam` | 2 | substring `betting` on the two Application-Identifier (AID) list pages |
  | `seo-spam` | 1 | substring `xxx` on `/section-5-basic-organizations/` |
  | `security-headers` | 1 | the three missing headers above |
  | `offsite-redirect` | 1 | `/design/design-services/java-card-applet/` resolving to the AmbiSecure host |

  Every one of these keyword hits is a substring match on legitimate-looking security/payments editorial
  content. **None is reported as confirmed compromise, and none was verified here.**

### 9b. From the 11:00 SEO run (ambimat.com slice)

- 437 pages crawled, 845 keywords tracked; average response 700 ms; 1 slow page; **0 redirect chains**.
- **AI readiness average 41.1** (0 pages above 70, 209 below 40) — the weakest are all `/tag/*` archives at 28.
- **Audit:** 1 high (`/category/general/` is noindex), 17 medium, 464 low. Medium findings are
  "canonical points elsewhere" (×2, both the smart-city street-light article) and eight duplicate-title groups.
- **Metadata:** 127 pages with incomplete Open Graph, 0 missing Twitter tags, 327 heading issues,
  **alt-text coverage 1.0 across 3 889 images**.
- **Schema:** coverage **1.0** (437/437) — BreadcrumbList/WebSite/Organization on every page,
  Article on 186, FAQPage on 6.
- **Content quality:** average 92.4, none below 55.
- **Weak pages:** 30 high / 656 medium / 408 low. Every high-severity one is a *duplicate-intent* pair,
  e.g. `/about/` vs `/about/company-overview/`, `/ambi-con/` vs `/categories/ambi-con/`, the four PCB
  surface-finish articles, `/emv-application-selection/` vs `/emvtm-application-selection/`, and many
  `/tag/*` vs article pairs.
- **Internal links:** 12 orphans (`/ambi-space/`, `/ambi-sense/`, `/ambi-pay/`, `/ambi-secure/`,
  `/ambi-power/`, `/ambi-con/`, `/by-industry/`, `/by-technologies/`, `/f1tenth/`, `/terms-conditions/`,
  `/refund-cancellation-policy/`, `/event/ambimat-history/`), 232 under-linked, 55 over-linked,
  98 internal-link recommendations.
- **157 recommendations** for ambimat (18 HIGH / 60 MEDIUM / 79 LOW). These are generator suggestions
  only; **no site change is proposed or implemented by this run.**
- Ecosystem context: 826 total pages across 7 domains, ecosystem AI-readiness 64.5.

## 10. External-link findings — kept separate from `ambimat.com` findings

These are third-party hosts linked *from* ambimat pages. **None indicates an ambimat.com defect**, and
each response class is kept distinct:

| External URL | Method | Recorded | Class | Linked from |
| --- | --- | --- | --- | --- |
| `toshiba.semicon-storage.com/us/product.html` | HEAD | 403 | forbidden / bot-block, **HEAD-only** | `/clients-vendors/` |
| `developer.apple.com/services-account/download?path=…WalletCompanionFiles.zip` | HEAD | 403 | forbidden / bot-block, **HEAD-only** | `/applevas-about-pass-files/` |
| `www.businesswire.com/` | HEAD→GET, 1 retry | no status | **read timeout** (10 s) | `/worldnet-launches-gochipnow-…/` |
| `indianarmy.nic.in/index.aspx` | HEAD→GET, 1 retry | no status | **TLS verify failed** (no local issuer) | `/clients-vendors/` |
| `scl.gov.in/` | HEAD→GET, 1 retry | no status | **TLS verify failed** (no local issuer) | `/clients-vendors/` |

The crawler issues HEAD and only falls back to GET on 405 or 5xx — so a 403 is **never** re-tested with
GET. The two 403s are therefore **HEAD-only observations and are not established as broken links**.
The three no-status entries are `UNVERIFIED`, which the tool defines as distinct from a failing status.
A further **738 external links were skipped by policy** (bot-hostile social/CDN hosts).

## 11. Missing, partial, stale, conflicting or ambiguous evidence

Nothing was missing: both expected runs produced today-dated, structurally complete output. Four
genuine conflicts are **preserved rather than reconciled**:

1. **Page count: 461 (10:00) vs 437 (11:00) for the same host.** Two different crawlers with different
   discovery rules. Neither is treated as authoritative here.
2. **noindex count: 10 (10:00) vs `technical.noindex = 1` (11:00).** The 10:00 run lists
   `/category/general/` *plus its nine pagination pages*; the 11:00 run's smaller page set caught only
   the parent. Consistent with the different crawl scopes, but not verified.
3. **Broken internal links: 0 (10:00) vs 492 `broken_outbound` records (11:00).** The 11:00 figure is
   dominated by **437 records whose target is the bare `https://ambimat.com`** (no trailing slash) —
   i.e. essentially every crawled page's link to the homepage, flagged against an inventory keyed on
   `https://ambimat.com/`. The remaining ~55 cluster on `/categories/ambi-logistics/` (17),
   `/categories/powered-card/` (17), and a handful of no-trailing-slash variants. The 10:00 run, which
   actually issued HTTP requests for internal links, found **zero** broken. The two results are
   recorded side by side in `seo_results.csv` and flagged `low (conflicting evidence)`.
4. **`trend.deltas.avg_ai_readiness = +17.3`** ecosystem-wide day-over-day (with `total_pages −30`), a
   large single-day swing the report does not explain. Recorded as-is.

Additionally: the 10:00 job's 461-page crawl vs the ~697-page sitemap figure in `sites.yaml` is
unexplained but is **not** flagged as truncation by the tool (`partial=false`, `timed_out=false`).

## 12. Notification / SSH-helper issues visible in existing logs

None affecting either crawl. The only related signal is the benign lock contention in both job logs
(`lock held; skipping` at 10:00:03 and 11:00:03) where a duplicate trigger declined the lock while the
real run held it; both holding runs then completed `rc=0`. `missed_cron.log` is empty; `missed_run.log`
contains only 2026-07-01 catch-up history; `boot_startup.log` last changed 2026-07-27 (matching the
~4.2-day uptime, so no boot recovery ran today). `seo_tracker_reports/cron.log` is 0 bytes and unchanged
since 2026-07-07 — the watchdog, not cron, is the effective trigger on this device.

## 13. Exact extraction directory

```
/Users/neelshah/Documents/git_repo/Rooted-Phone/reports/ambimat_phone_extraction/2026-07-31_20260731T115912Z/
├── raw/{site_monitor,seo,scheduler}/     29 copied files, phone layout mirrored
├── inventory/phone_evidence_inventory.csv
├── summary/{site_monitor_results.csv,seo_results.csv,execution_status.json,EXTRACTION_REPORT.md}
└── checksums/{SHA256SUMS,COMMAND_LOG_REDACTED.txt,INTEGRITY_STATEMENT.txt}
```

No pre-existing extraction was overwritten; this directory was newly created.

## 14. Confirmation that no run or repair was triggered

No scheduler, cron, watchdog, catch-up, boot-recovery, retry, site-monitor or SEO script was invoked.
Phone-side commands were limited to `date`, `id`, `uname`, `getprop`, `ls`, `cat`, `head`, `tail`,
`grep`, `wc`, `sed -n`, `stat` and `sha256sum`, plus `scp` reads. The watchdog's own 17:30 tick — which
this extraction did not cause — logged `already succeeded today … skip` for both jobs, independently
confirming nothing was re-run.

## 15. Confirmation that the phone source files were not modified

All 29 source files were re-hashed on the phone after extraction. 28 are byte-identical to their
pre-copy hashes. The 29th (`scheduler_watchdog.log`) was appended to by the phone's own scheduled
watchdog and was proven append-only: its first 227 901 bytes still hash to the pre-copy value. **No file
was created, edited, renamed, moved, truncated, compressed or deleted on the phone by this extraction.**

## 16. Confirmation that zero public-site requests were made

No HTTP, HTTPS, DNS, TLS, browser, curl, wget, WordPress, WP-CLI, Search Console or any other request
to `ambimat.com` or any other public host was made. Every HTTP status, redirect, certificate detail and
SEO metric in this report was **read out of files the phone had already written** at 10:15 and 11:22 IST.
No GSC ZIP archive was opened or processed. No live server was accessed.

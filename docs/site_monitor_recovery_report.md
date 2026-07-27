# Site Monitor Recovery Report

**Date:** 2026-07-01 · **Device:** Moto G4 Plus (athene_f, unrooted, Android 7 / 32-bit)

## What happened

A manual site-monitor crawl was launched on the phone over USB SSH (background task `b48ziuh4w`,
`run_site_monitor.py --max-pages 20`, all four sites, external link checking ON). From the Mac it
appeared **stuck/hung** — the SSH task never returned and stdout showed only the startup lines
(stdout was block-buffered; only a `utcnow()` DeprecationWarning on stderr had appeared).

On inspection, the crawl had **actually completed successfully** on the phone: full reports were
written at **17:22:16** (`report_20260701_172216.{json,md}` + `report_latest.*`, ~75 KB JSON,
all 4 sites, 80 pages). No Python process was running. The "hang" was the **SSH session not
returning**, not a crawl that never finished.

## Evidence preserved (before stopping anything)

- Completed reports pulled to `reports/site_monitor_recovery/`
  (`report_20260701_172216.json/md`, `report_latest.json/md/html`).
- Phone-side `ps -A` output captured (no python; 5 leftover `libexec/termux-api` helper
  processes + the `com.termux.api` app service).
- Background task output log retained by the harness.

## Root cause / likely cause

**Primary (the hang):** `notify()` called `termux-notification` and `termux-toast` at the end of the
run. Those wrappers spawn `/data/data/com.termux/files/usr/libexec/termux-api` helper processes that
**inherited the SSH command's stdout file descriptor**. Even after the Python process exited and the
reports were written, the helpers kept the channel open, so `ssh` never received EOF and the session
(and thus the background task) hung indefinitely. Five idle `libexec/termux-api` helpers were found
still alive, confirming this.

**Secondary (slow + noisy):** external-link checking. The 20-page/site run with external checks took
~11 minutes and reported 26 "broken links", but most were **false positives** — bot-hostile hosts
(twitter.com, facebook.com) return `None`/403 to HEAD requests. A few genuine internal 404s on
`ambimat.com` were real. **No compromise indicators (0 alerts)** were found on any site.

**Minor:** a `datetime.utcnow()` DeprecationWarning (cosmetic).

## Fixes made

Code (`site_monitor/run_site_monitor.py`) and config (`site_monitor/config/sites.yaml`):

- **Notification hang fixed** — `termux-notification`/`termux-toast` now run with
  `stdin/stdout/stderr = /dev/null`, `start_new_session=True`, and a 20 s timeout, so a helper can
  never hold the SSH channel open. Verified: **no leftover helpers** after the fixed runs.
- **`(connect, read)` timeout tuple** on every request (`connect_timeout_seconds`,
  `read_timeout_seconds`).
- **Per-site time budget** (`max_seconds_per_site`, default 180 s) and **global budget**
  (`global_max_seconds`, default 600 s). Crawl, sitemap parsing, and link-checking all check the
  deadline and stop early; remaining sites are skipped rather than hanging.
- **External link checking capped** (`max_external_links_per_site`, default 20) and disableable
  (`--no-external-links`); bot-hostile social/CDN hosts skipped via `external_check_skip_hosts` so
  they no longer masquerade as broken links.
- **Progress flushed** (`flush=True`) after every page; new `--verbose` streams each page live.
- **Reports always written in a `finally` block** — partial results are saved on timeout /
  Ctrl-C / exception. `SIGINT`/`SIGTERM` handled; report marked `"partial": true`.
- A slow/failed page becomes a **`fetch-error` warning**, not a process hang (verified: a
  `RemoteDisconnected` mid-crawl was logged and the crawl continued).
- New CLI: `--max-pages`, `--global-timeout`, `--site-timeout`, `--no-external-links`, `--verbose`.
- `utcnow()` replaced with timezone-aware UTC (warning gone).

Conservative config defaults are now: `max_pages_per_site: 20`, `connect/read: 5/10 s`,
`max_external_links_per_site: 20`, `max_seconds_per_site: 180`, `global_max_seconds: 600`.

## Smoke test result (3 pages/site, `--no-external-links`)

- Command: `--max-pages 3 --global-timeout 120 --site-timeout 60 --no-external-links --verbose`.
- **Returned cleanly, rc=0**, 17:31:49 → 17:33:53 (~124 s; the internal-link-check phase — it
  self-terminated, no hang). SSH session closed promptly (notify fix confirmed).
- All 4 sites reachable (HTTP 200), 12 pages, **0 alerts**, 11 warnings, 2 broken (internal) links.
- Progress streamed live; reports written; notification/toast fired; **no leftover helper processes**.

## Bounded manual crawl result (10 pages/site, `--no-external-links`)

- Command: `--max-pages 10 --global-timeout 600 --site-timeout 180 --no-external-links --verbose`.
- **Completed cleanly, rc=0**, 17:35:06 → 17:39:52 (**~4m46s**, well under the 600 s global cap; no
  hang, no leftover helper processes).
- **39 pages** crawled: Ambimat 9 (1 page returned `RemoteDisconnected` → logged as a `fetch-error`
  warning, crawl continued), AmbiSecure 10, AmbiAutomation 10, eSIM 10.
- **0 compromise alerts on any site.** All 4 reachable, HTTP 200.
- **6 broken internal links** — all genuine `404`s under `ambimat.com/design/ambi-iot/…` and
  `/categories/…` (real site issues worth fixing; external links not checked this run).
- **34 warnings**, all advisory: Ambimat 12 (`suspicious-pattern` ×9, missing security headers,
  1 external iframe, the fetch-error), AmbiSecure 0, AmbiAutomation 0, eSIM 22
  (`external-iframe` ×10, `suspicious-pattern` ×10, + 2 spam-term hits — see next).
- TLS certificates valid: Ambimat 65 d, AmbiSecure 73 d, AmbiAutomation 79 d, eSIM 36 d.
- Ambimat's internal-link check honestly reported `stopped early (79/100 checked)` when the 180 s
  site budget was reached — bounded, not hung, and disclosed in the report.

### False-positive found and fixed (spam keyword matching)

The eSIM run flagged `japanese-spam: cialis` and `seo-spam: cialis` on `case-studies/keyra.html`.
Investigation showed the substring came from **"commercialisation" / "commercialise"** — a naive
substring match, not spam. Fixed: ASCII spam terms now require **word boundaries**
(`term_in_text()`), so `cialis` no longer matches inside `commercialise` and `loan` no longer
matches inside `download`; CJK/Japanese terms keep substring matching. Verified against the live
page — it now yields **zero** spam hits. (The 17:39:52 report predates the fix and still shows those
2 warnings; the next run will not.)

## Remaining limitations

- Public-crawl only — cannot prove a hack occurred in the last 24 h (needs server/WAF/GSC/CMS logs).
- External-link checking is disabled for recovery runs; social/CDN false positives still need tuning
  before external checks are trusted in the daily job.
- `suspicious-pattern` / `external-iframe` warnings are advisory and expected on normal
  WordPress/marketing sites (analytics, embeds, lazy-load CSS) — not evidence of compromise.
- Cron does not survive reboot without Termux:Boot (not installed).

## Next approval needed

Explicit approval to **enable the daily 10:00 AM cron job** (`site_monitor/schedule_daily.sh install`).
Not enabled in this recovery run.

# Ambimat Site Monitor

A lightweight, **public-crawl-based** website health + hack-indicator + SEO monitor that runs
in **Termux on the Moto G4 Plus** (Android 7 / 32-bit / unrooted). Pure Python +
`requests` + `beautifulsoup4` + `PyYAML`. No root, no browser automation, no cloud APIs, no keys.

It is *inspired by* the `claude-seo` project (see `../docs/claude_seo_repo_review.md`) but shares
none of its heavy runtime — `claude-seo` is a Claude Code AI skill needing Playwright/Chromium and
paid data APIs, which cannot run on this phone.

## ⚠️ Accuracy limitation (read this first)

This tool is a **public-crawl-based compromise *indicator* + SEO health report**. It can only
detect evidence of compromise that is **visible on public pages at crawl time**. It **cannot**
prove whether "a hack was attempted in the last 24 hours." That requires server logs, hosting/WAF
logs, Google Search Console alerts, or CMS security logs — none of which this tool has access to.

Every "suspicious" finding is an **advisory WARNING to investigate**, not confirmed compromise.
Wording used in reports:

- `Broken pages detected`
- `Suspicious indicators detected`
- `Potential SEO spam indicators`
- `Potential injected external links/scripts`
- `No public-page compromise indicators detected`

Only high-confidence signals (broken pages, defacement calling-cards, redirects to a different
domain, scripts/iframes from a known-suspicious domain, unreachable site) are raised as **ALERTS**.

## What it checks

- **Reachability & broken pages/links** — HTTP status of crawled pages; bounded HEAD/GET checks of
  internal links not crawled and (optionally) external links.
- **Defacement** — defacement calling-cards ("hacked by", "pwned by", …) in title/H1/visible text.
- **Malicious redirect** — homepage redirecting to a *different registrable domain*.
- **Japanese-keyword SEO hack spam** — terms from `keywords/japanese_spam.txt`.
- **Pharma/casino/adult/loan/crypto/replica spam** — terms from `keywords/suspicious_spam.txt`.
- **Injected/hidden content** — off-host `<script>`/`<iframe>` (suspicious domain → alert),
  hidden/off-screen links, and raw-HTML patterns from `keywords/suspicious_patterns.txt`
  (`eval(`, `base64_decode`, `document.write(unescape`, hidden CSS, meta-refresh, `<?php`, …).
- **SEO health** — title, meta description, H1, canonical, robots-meta (noindex/nofollow),
  word count, duplicate titles/descriptions.
- **Security headers** (homepage) — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy,
  Strict-Transport-Security.
- **TLS certificate expiry** — days remaining (stdlib `ssl`, no heavy deps).
- **Title drift** — titles that changed since the previous successful run (baseline =
  `report_latest.json`).

## What it does NOT do

No vulnerability scanning, no admin-path / `wp-login` probing, no brute force, no fuzzing, no
exploit payloads, no login attempts. GET-only, same-domain, polite (configurable delay + timeouts),
bounded page count. It does not modify the sites in any way.

## Files

```
site_monitor/
  config/sites.yaml          # site list + crawl policy + alert thresholds
  run_site_monitor.py        # the crawler / analyzer / report writer
  render_report.py           # JSON -> Markdown/HTML; also a standalone viewer
  link_notes.py              # external-link classification registry (interpretation only)
  config/external_link_notes.yaml  # the classifications themselves
  prune_reports.py           # bounded report retention (dry-run by default)
  run_once.sh                # run one crawl now (foreground)
  run_daily.sh               # cron wrapper (sets PATH, logs, notifies)
  schedule_daily.sh          # install/show/remove the 10 AM cron entry
  show_latest_report.sh      # open latest HTML / print latest MD on the phone
  requirements.txt           # requests, beautifulsoup4, PyYAML
  keywords/*.txt             # spam / pattern keyword lists (editable)
  reports/                   # (repo placeholder; live reports go to ~/site_monitor_reports)
```

## Install (in Termux, on the phone)

```bash
cd ~/site_monitor
python -m pip install --user -r requirements.txt
```

## Run manually

```bash
cd ~/site_monitor
./run_once.sh                       # config default (max_pages_per_site: 20)
./run_once.sh --max-pages 10 --no-external-links --verbose
# fast smoke test (bounded, streams progress):
python run_site_monitor.py --config config/sites.yaml --output-dir ~/site_monitor_reports \
  --max-pages 3 --global-timeout 120 --site-timeout 60 --no-external-links --open-report false --verbose
```

### CLI flags

| Flag | Effect |
|---|---|
| `--max-pages N` | override `max_pages_per_site` |
| `--global-timeout SEC` | override `global_max_seconds` (whole run) |
| `--site-timeout SEC` | override `max_seconds_per_site` |
| `--no-external-links` | skip external-link checks (recommended until social/CDN false positives are tuned) |
| `--verbose` | print each page as it is crawled (flushed live) |
| `--no-notify` | skip termux notification/toast |
| `--open-report true` | open `report_latest.html` on the phone at the end |

### Fail-fast / bounded guardrails (added after a hang — see `../docs/site_monitor_recovery_report.md`)

- Every request uses a `(connect, read)` timeout; a slow/dead page becomes a warning, never a hang.
- Per-site **and** global time budgets; the run self-terminates and writes a **partial** report.
- External-link checks are capped and skip bot-hostile hosts (Twitter/Facebook/… return `None` to
  HEAD and would otherwise look "broken").
- Progress is flushed after every page; reports are always written in a `finally` block.
- Notifications are detached (`/dev/null` fds + new session) so they cannot hold the SSH session
  open — that was the original hang.

## Reports (stored on the phone)

Output dir: `~/site_monitor_reports/`

```
report_YYYYMMDD_HHMMSS.json   # full machine-readable report
report_YYYYMMDD_HHMMSS.md     # human-readable snapshot
report_latest.json            # newest run (also the drift baseline for next run)
report_latest.md
report_latest.html            # phone-friendly HTML
daily_runner.log / cron.log   # scheduler logs
```

## Report retention

Report storage was never bounded; by 2026-09-10 it had reached 162 MB on a phone with limited
space. `prune_reports.py` thins **dated** reports on a tiered schedule with a finite horizon:

| age | kept |
|---|---|
| 0–30 days | every report |
| 31–90 days | one per ISO week |
| 91 days – 24 months | one per calendar month |
| older than 24 months | **expired** |

The last row is what makes this a bound rather than a slow leak. "One per month, forever" still
adds 24 files a year until the disk fills; `MAX_AGE_DAYS = 730` closes it.

The weekly and monthly tiers are applied **independently to successful and to abnormal runs**, so
a failure is never thinned away by the healthy runs that surround it. Abnormal means: alert/warning
raised, broken links, a crawl error, or a report that will not parse (a truncated file is itself
the evidence that a run died).

Two things outlive the horizon, both finite and both deliberate:

- **the newest abnormal report**, whatever its age — never lose the last evidence of a failure
- **the onset of an unresolved incident.** If the most recent report is still abnormal, the run of
  consecutive abnormal reports ending at it is an incident that is still open, and its first report
  is the evidence of when it started. That report is kept past the horizon until a healthy report
  lands and closes the incident. It is exactly one extra report per store.

Never touched, at any age:

- `report_latest.{json,md,html}` — `report_latest.json` is the title-drift baseline, so deleting it
  would silently reset drift detection
- `per_site/<slug>/unverified_ledger.json` — the staleness ledger
- `seo_tracker_reports/history/` and `state/` — where SEO trends actually live
- today's reports, and anything written in the last hour (a run may still be writing it)

Dated reports have no consumers: nothing in this repo or the SEO tracker reads
`report_YYYYMMDD_HHMMSS.*`. Thinning them costs no trend or audit function. A logical report is
its whole `.json` + `.md` (+ `.html`) set, or a whole cache-inspection directory — deleted together
or not at all, so no half-report is ever left behind.

### Why the retained set is finite

With `d`=30, `w`=90, `m`=730, `r` runs per day and 2 kinds (ok / abnormal), the retained count per
store is at most

```
d*r  +  2*ceil((w-d)/7)  +  2*ceil((m-w)/30.44)  +  2
```

— the full-detail window, the weekly representatives, the monthly representatives, and the two
evidence exemptions. At the current settings and `r ≤ 8` that is about **304 logical reports per
store**, approached asymptotically and never exceeded. It does not depend on how long the estate
keeps running, which is the property "one per month beyond 90" did not have.

### Log rotation

The logs were the only other store still growing without a limit: ~44 kB/day across 12 files,
16 MB a year, forever. Every line is small, which is exactly why it went unnoticed. Once a `.log`
in `ambimat_job_logs/`, `site_monitor_reports/`, `seo_tracker_reports/` or `cache_monitor_reports/`
passes `LOG_MAX_BYTES` (1 MB) it is rotated, keeping `LOG_GENERATIONS` (2) historical copies — so
each log costs at most 3 MB permanently.

Rotation is **copy-and-truncate, not rename**. `run_daily.sh`, the wrapper above it and cron all
hold their log open in append mode for the whole run — including the run that calls the pruner.
Renaming would leave those writers appending to a file nobody reads. Copying the content to `.1`
and truncating in place keeps every open descriptor valid: `O_APPEND` writes go to the new end of
file, so nothing is lost and nothing is written to a ghost. The active log is never deleted, only
emptied after its content is safely in `.1`. No `logrotate` dependency — it is not installed in
Termux and is not needed.

```bash
python prune_reports.py            # DRY RUN — default; prints exactly what would go
python prune_reports.py --apply    # actually delete / rotate
```

Runs **weekly** from `run_daily.sh` (stamp file `~/site_monitor_reports/.last_prune`, `-mtime +6`),
only after a successful merge, and only ever as an extra step of the existing 08:00 job — no new
cron entry. A prune failure is logged and non-fatal: monitoring never depends on housekeeping.
Exit status is non-zero on a genuine error. Re-running is a no-op.

### Stores deliberately left alone

| store | why no retention rule |
|---|---|
| `history/summary_history.json` | already hard-capped by the SEO tracker itself (`history[-60:]`); 60 records ≈ 14 kB, and `_trend_deltas()` reads only `history[-1]` |
| `seo_tracker_reports/state/` | current-state only, 11 bytes |
| `per_site/*/unverified_ledger.json` | garbage-collected every run against live crawl membership — a URL that stops being unverified, or stops existing, is deleted from the ledger the same run. Bounded by the number of currently governed URLs, not by time |
| `config/external_link_notes.yaml` | curated metadata, added by hand. Never age-pruned |

## External-link classification registry

`config/external_link_notes.yaml` records what was learned when a link could not be verified —
per URL, one of `antibot`, `transient` or `upstream-failure`, with the date it was confirmed by
hand and why.

**It is not an allowlist and it does not suppress anything.** A note is attached *after* the
crawler has already decided, on live evidence in that run, that a link is unverified. It cannot:

- move a link out of `unverified_external`, or stop one entering `broken_external`
- keep a link out of the staleness ledger
- prevent the check from being made — every noted URL is fetched on every run, exactly as before

If a noted URL answers 200 next run it is simply never recorded as unverified and the note never
applies. If it starts answering 404/410/5xx, changes its redirect, fails DNS or fails certificate
validation, it becomes a broken link exactly as it would with no note at all. Annotation is wired
into the two `unverified_external` appends and the one `unverified_internal` append only;
`broken_external` and `broken_internal` are deliberately never annotated.

The only thing a note changes is what the report says:

```
- https://www.nytimes.com/... (403) [known: antibot, confirmed 2026-09-10]
- https://brand-new.example/x (403) [NEW / unclassified]
```

...which is the difference between a finding somebody has already judged and one nobody has. The
report also counts how many unverified links are NEW, so a genuinely new blocker stands out
instead of hiding in a long familiar list. Adding an entry requires an actual manual check on the
date recorded. `site_monitor/tests/test_link_notes.py` asserts the no-suppression properties.

## View on the phone

```bash
./show_latest_report.sh                       # opens HTML (termux-open) + prints MD
python render_report.py --latest --open       # re-render latest JSON and open HTML
cat ~/site_monitor_reports/report_latest.md    # plain terminal view
```

**Screen-lock note:** Android may not bring the HTML viewer to the foreground if the screen is
locked. The **notification** (and toast) is the reliable delivery path; opening the HTML report is
best-effort. The daily job does not force the screen on.

## Daily 10:00 AM schedule (Termux cron)

```bash
cd ~/site_monitor
./schedule_daily.sh install     # adds "0 8 * * *" + starts crond for this session
./schedule_daily.sh show        # show crontab + crond status
./schedule_daily.sh remove      # disable the daily job
```

**Limitation:** cron runs only while Termux + `crond` stay alive. It does **not** survive a reboot
unless **Termux:Boot** is installed later (intentionally NOT installed now). After a phone reboot,
re-run `./schedule_daily.sh install` (or just `crond`) to restart the scheduler.

## Privacy / sensitive data

Reports contain only public website data (URLs, titles, HTTP statuses, header names). They do not
contain phone identifiers, Wi-Fi SSIDs, or private IPs. They are safe to keep, but raw reports are
gitignored by default; a redacted sample is committed as evidence.

## Battery / charger notes

One daily foreground run of a bounded crawl is light. Expect a few minutes of network + CPU once a
day. No wakelock is taken and no background service runs; if the phone is asleep at 10 AM, cron
still fires as long as `crond` is alive, but heavy sleep/doze on Android 7 can delay it — keeping
the phone on the charger during the daily window is the most reliable setup.

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

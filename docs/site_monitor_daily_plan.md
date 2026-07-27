# Site Monitor — Daily 10:00 AM Plan

Operational plan for running the Ambimat site monitor (`site_monitor/`) as a daily
health / hack-indicator / SEO check on the Moto G4 Plus. **Cron is NOT enabled yet** — it is
gated on approval after a stable bounded manual crawl (see the recovery report).

## What the monitor checks

- Reachability + broken pages (HTTP status of crawled pages).
- Broken internal links, and (optionally) external links — external checking is **off** for
  recovery runs because bot-hostile social/CDN hosts (Twitter/Facebook/…) return `None`/403 to
  HEAD and produce false "broken" results.
- Defacement calling-cards, malicious cross-domain redirects, injected off-host scripts/iframes,
  hidden/off-screen links → **ALERTS** (high confidence) or **warnings** (advisory).
- Japanese-keyword SEO-hack spam and pharma/casino/adult/loan/crypto/replica spam → **warnings**.
- SEO health: title/description/H1/canonical/robots-meta, word count, duplicate titles/descriptions.
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS).
- TLS certificate expiry (days remaining).
- Title drift vs the previous successful run.

## What it does NOT check / prove

Public-crawl only. It **cannot** prove "a hack was attempted in the last 24 h" — that needs server
/ hosting / WAF logs, Search Console alerts, or CMS security logs. No vulnerability scanning, no
admin-path probing, no brute force, no fuzzing, no logins. All "suspicious" findings are advisory.

## Bounded / fail-fast guarantees (post-recovery)

- Every request has a `(connect, read)` timeout.
- Per-site time budget (`max_seconds_per_site`, default 180 s) and global budget
  (`global_max_seconds`, default 600 s). The run self-terminates and writes a **partial** report
  rather than hanging.
- External link checking capped (`max_external_links_per_site`) and disableable (`--no-external-links`).
- Progress printed with `flush=True` after every page (`--verbose`).
- Reports always written in a `finally` block (even on timeout / Ctrl-C / exception).
- Phone notifications are detached (`/dev/null` fds + new session) so they can never hold the SSH
  session open — this was the original hang.

## How to run manually (in Termux)

```bash
cd ~/site_monitor
# fast smoke test (bounded, no external links):
python run_site_monitor.py --config config/sites.yaml --output-dir ~/site_monitor_reports \
  --max-pages 3 --global-timeout 120 --site-timeout 60 --no-external-links --open-report false --verbose
# bounded manual crawl:
python run_site_monitor.py --config config/sites.yaml --output-dir ~/site_monitor_reports \
  --max-pages 10 --global-timeout 600 --site-timeout 180 --no-external-links --open-report false --verbose
```

## Daily 10:00 AM schedule (Termux cron) — NOT ENABLED YET

Once approved:

```bash
cd ~/site_monitor
./schedule_daily.sh install     # adds "0 10 * * *" running run_daily.sh + starts crond
./schedule_daily.sh show
./schedule_daily.sh remove      # disable
```

The cron line:

```
0 10 * * * /data/data/com.termux/files/home/site_monitor/run_daily.sh >> ~/site_monitor_reports/cron.log 2>&1
```

`run_daily.sh` sets a Termux PATH, runs the monitor, appends to `daily_runner.log`, and fires a
notification/toast. It uses the config defaults (currently `--no-external-links` NOT applied — the
daily job will use whatever `check_external_links` is set to in `sites.yaml`; keep it disabled or
capped until external-link false positives are tuned).

### Scheduling limitations

- Cron runs **only while Termux + `crond` are alive**. It does **not** survive a reboot unless
  **Termux:Boot** is installed later (intentionally not installed now). After a reboot, re-run
  `./schedule_daily.sh install` (or `crond`).
- Android 7 Doze/sleep can delay a 10 AM firing if the phone is in deep sleep. Keeping the phone on
  the charger during the daily window is the most reliable setup.
- Screen-lock: the HTML report may not foreground if the screen is locked; the **notification** is
  the reliable delivery path.

## Reports

Stored on the phone in `~/site_monitor_reports/`:
`report_YYYYMMDD_HHMMSS.{json,md}`, `report_latest.{json,md,html}`, `daily_runner.log`, `cron.log`.
Pull to the Mac with `scp -P 8022 -i ~/.ssh/id_moto_playground 'localhost:~/site_monitor_reports/*' reports/site_monitor/`.

## Remaining before enabling cron

1. ✅ Bounded, non-hanging manual crawl proven.
2. ⏳ Your explicit approval to enable the daily 10 AM job.
3. (Optional, later) Tune external-link checking / decide whether the daily job checks external
   links, and whether to install Termux:Boot for reboot persistence.

# Scheduler durability — audit against the eight required conditions

Verified by reading the live device code plus the three scenario suites
(18 + 39 + 49 = 106 scheduling assertions, all passing on the phone). Nothing
destructive was simulated: no reboot, no forced network loss, no killed run.

| # | Condition | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Normal uptime | **OK** | `*/30` watchdog plus three cron lines; 2026-09-02→09-05 ran on time every day |
| 2 | Phone reboot | **OK** | Termux:Boot hook re-acquires wake-lock, starts `sshd`+`crond`, reinstalls the crontab, waits 45 s, runs the watchdog. Exercised for real on 2026-09-01 and again on 2026-09-07 12:34 |
| 3 | Off at 10:00 | **OK** | 2026-09-07: site monitor caught up 12:35→12:56 |
| 4 | Off at 11:00 | **OK** | 2026-09-07: SEO caught up →13:11:07 |
| 5 | Back after both times passed | **OK** | all three same-day jobs caught up within 37 min of boot |
| 6 | Temporary network loss | **OK** | `amb_network_ready` gate defers *without* marking success — observed live 2026-08-04 11:00 ("network unavailable at start; deferred (no success mark)") then succeeded 11:53 |
| 7 | Authenticated source unavailable | **OK, and now honest** | measurement queue records BLOCKED + evidence, never `completed`; stays retryable, bounded at 6 attempts/IST day. The verdict now names the *actual* blocker |
| 8 | Previous run crashed halfway | **OK** | marker written only on `rc == 0`; dir-locks reclaim a dead owner's lock; partial reports are written but never mark success |

## "Launched" vs "completed successfully" — VERIFIED

`amb_run_if_due` gates on `amb_marker_is_today`, and the marker file is written **only**
by the runner after `rc == 0`. Process start is never recorded as completion. Suite E of
`sched_tests.sh` asserts both failure paths explicitly:

```
PASS: SEO offline -> marker NOT set
PASS: SEO lock held -> exits without setting marker (python not run)
```

## Duplicate suppression — VERIFIED

```
PASS: two concurrent wrappers -> sibling executed EXACTLY once (lock dedup)
PASS: concurrent run -> marker set once (today)
PASS: completed run never re-executes (already completed)
PASS: retry bounded at 6/day
```

## Deliberate limitation (not a defect)

Catch-up is **same-logical-day only**. 2026-09-06 was missed entirely and will never be
backfilled. This is correct: a day-old availability crawl has no operational value, and
replaying history would corrupt the SEO trend series. Idempotent, bounded, no replay storm.

## SSH-hang regression (Termux notification helpers) — VERIFIED NOT REGRESSED

Historically `termux-notification` / `termux-toast` could inherit stdout and hold an SSH
session open after the Python job exited. All three call sites still redirect every
descriptor:

* `site_monitor/run_daily.sh` — `termux-notification … >/dev/null 2>&1 </dev/null || true`
* `measurement_queue/lib_measure.sh` `mq_notify()` — same, plus a new
  `MQ_NOTIFY_DISABLE` guard so the test harness cannot post to the live tray
* `cache_monitor/run_cache_monitor_daily.sh` — same pattern

No SSH session hung during this audit despite ~30 remote invocations, and no orphaned
helper processes were left behind.

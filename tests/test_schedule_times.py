#!/usr/bin/env python3
"""Guard: the daily schedule is 08:00 / 09:00 / 10:00 IST, everywhere.

Moved from 10:00/11:00/12:00 by owner decision on 2026-09-07. The times live in
five separate files across two machines, so the failure mode is one of them being
missed and the phone drifting back to the old schedule on the next crontab
self-heal. This asserts every source of truth agrees, and that the boot-window
catch-up maths follows from those same numbers.

Stdlib only, no device required: it reads the repo's own copies.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SITE_HM, SEO_HM, CACHE_HM = "0800", "0900", "1000"

# file -> list of (regex that must match, human description)
EXPECTED = [
    ("cache_monitor/run_cache_monitor_daily.sh",
     [(r'^DUE_HM="1000"', "cache monitor due time is 1000")]),
    ("cache_monitor/install_noon_job.sh",
     [(r'^CRON_LINE="0 10 \* \* \*', "cache monitor cron line is 0 10")]),
    ("cache_monitor/ensure_scheduler_noon_block.sh",
     [(r"amb_run_if_due front_page_cache 1000", "watchdog catch-up block uses 1000")]),
    ("site_monitor/schedule_daily.sh",
     [(r'^CRON_LINE="0 8 \* \* \*', "site monitor cron line is 0 8")]),
    ("reports/scheduler_verification/phone_scripts_snapshot/ensure_scheduler.sh",
     [(r"amb_run_if_due site_monitor 0800", "watchdog: site monitor at 0800"),
      (r"amb_run_if_due seo\s+0900", "watchdog: SEO at 0900"),
      (r"amb_run_if_due front_page_cache 1000", "watchdog: cache monitor at 1000")]),
]

# Nothing operational may still carry the retired 10:00/11:00/12:00 schedule.
STALE = [
    (r"amb_run_if_due site_monitor 1000", "site monitor still at 1000"),
    (r"amb_run_if_due seo\s+1100", "SEO still at 1100"),
    (r"amb_run_if_due front_page_cache 1200", "cache monitor still at 1200"),
    (r'DUE_HM="1200"', "cache monitor DUE_HM still 1200"),
    (r'CRON_LINE="0 12 \* \* \*', "cache cron line still 0 12"),
    (r'CRON_LINE="0 10 \* \* \* \$WRAPPER', "site monitor cron line still 0 10"),
]
OPERATIONAL_DIRS = ["site_monitor", "cache_monitor", "scripts", "tests",
                    "reports/scheduler_verification/phone_scripts_snapshot"]


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_every_source_of_truth_has_the_new_times():
    for rel, checks in EXPECTED:
        body = _read(rel)
        for pattern, desc in checks:
            assert re.search(pattern, body, re.M), "%s: %s" % (rel, desc)


def test_no_operational_file_keeps_the_old_times():
    offenders = []
    for sub in OPERATIONAL_DIRS:
        base = os.path.join(ROOT, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, _, names in os.walk(base):
            if "__pycache__" in dirpath or "/fixtures" in dirpath:
                continue
            for name in names:
                fp = os.path.join(dirpath, name)
                if os.path.abspath(fp) == os.path.abspath(__file__):
                    continue      # this guard names the old values in order to ban them
                try:
                    body = open(fp, encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                for pattern, desc in STALE:
                    if re.search(pattern, body, re.M):
                        offenders.append("%s: %s" % (os.path.relpath(fp, ROOT), desc))
    assert not offenders, "stale schedule values still present:\n  " + "\n  ".join(offenders)


def _due(now_hm, due_hm):
    """Mirror of lib_common.sh amb_run_if_due()'s time gate: run when now >= due."""
    return int(now_hm) >= int(due_hm)


def test_boot_window_catch_up():
    """The five boot windows the owner asked about, straight off the due times."""
    cases = [
        ("0730", (False, False, False), "boots before 08:00 - nothing is due yet"),
        ("0830", (True,  False, False), "boots 08:00-09:00 - only the site monitor"),
        ("0930", (True,  True,  False), "boots 09:00-10:00 - site + SEO"),
        ("1100", (True,  True,  True),  "boots after 10:00 - all three"),
        ("2359", (True,  True,  True),  "late boot same day - all three still due"),
    ]
    for now, expected, why in cases:
        got = (_due(now, SITE_HM), _due(now, SEO_HM), _due(now, CACHE_HM))
        assert got == expected, "%s: expected %s, got %s" % (why, expected, got)


def test_a_completed_job_is_never_re_run_and_yesterday_is_never_replayed():
    """Catch-up keys on a same-logical-day success marker, not on the clock.

    amb_run_if_due returns early when amb_marker_is_today() holds, so a job that
    already succeeded today never re-runs however late the watchdog ticks, and a
    marker from a previous date never causes yesterday's run to be replayed - it
    only makes TODAY due.
    """
    lib = _read("reports/scheduler_verification/phone_scripts_snapshot/lib_common.sh")
    assert "amb_marker_is_today" in lib, "lib_common.sh no longer defines amb_marker_is_today"
    assert re.search(r"if amb_marker_is_today[^\n]*\n\s*amb_log[^\n]*already succeeded today",
                     lib, re.M), "amb_run_if_due no longer short-circuits on today's marker"

    # The marker is written by the RUNNER and is always guarded by that runner's own
    # success condition, so a launched-but-failed job stays due. For the cache monitor
    # the condition is a CONCLUSIVE observation, not merely a zero exit: a failed public
    # request must leave the day unmarked so the watchdog retries it.
    runner = _read("cache_monitor/run_cache_monitor_daily.sh")
    calls = [m for m in re.finditer(r'^\s*amb_set_marker\s+"\$JOB"', runner, re.M)]
    assert len(calls) == 1, "expected exactly one amb_set_marker call, found %d" % len(calls)
    guard = runner[:calls[0].start()].rstrip().splitlines()[-1]
    assert re.search(r'if \[ "\$CONCLUSIVE" = "True" \]', guard), \
        "amb_set_marker is no longer guarded by a conclusive observation: %r" % guard
    assert "NOT set for FAIL_PUBLIC_REQUEST" in runner, \
        "the runner no longer documents that a failed request leaves the day unmarked"


def main():
    failures = []
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print("  PASS  %s" % name)
        except AssertionError as exc:
            failures.append(name)
            print("  FAIL  %s\n     -> %s" % (name, exc))
    total = sum(1 for n in globals() if n.startswith("test_"))
    print("\n%d passed, %d failed" % (total - len(failures), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

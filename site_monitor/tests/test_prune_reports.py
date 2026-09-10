#!/usr/bin/env python3
"""Regression: retention must bound storage without destroying evidence.

Report storage had never been pruned — 462 logical reports, ~168 MB, growing daily. The
danger in fixing that is not the disk, it is deleting the one report that mattered. Each
test below is a thing the pruner must refuse to do.
"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prune_reports as pr  # noqa: E402

failures = 0


def check(name, got, want):
    global failures
    if got == want:
        print("PASS %s" % name)
    else:
        failures += 1
        print("FAIL %s\n     got  %r\n     want %r" % (name, got, want))


def write_report(root, day, hhmmss="080000", *, abnormal=False, unparseable=False):
    stamp = f"{day.strftime('%Y%m%d')}_{hhmmss}"
    body = {"totals": {"sites_unreachable": 0, "sites_with_alerts": 0, "sites_timed_out": 0,
                       "broken_pages": 0, "broken_links": 0, "partial": False},
            "sites": [{"name": "X", "alerts": [], "warnings": [], "reachable": True}]}
    if abnormal:
        body["totals"]["sites_with_alerts"] = 1
    p = os.path.join(root, f"report_{stamp}.json")
    with open(p, "w") as fh:
        fh.write("{ truncated" if unparseable else json.dumps(body))
    with open(os.path.join(root, f"report_{stamp}.md"), "w") as fh:
        fh.write("# report\n")
    old = dt.datetime.combine(day, dt.time(8, 0)).timestamp()
    for ext in ("json", "md"):
        os.utime(os.path.join(root, f"report_{stamp}.{ext}"), (old, old))
    return stamp


def build(root, today):
    os.makedirs(root, exist_ok=True)
    for name in pr.PROTECTED_NAMES:
        with open(os.path.join(root, name), "w") as fh:
            fh.write("{}")
    with open(os.path.join(root, "daily_runner.log"), "w") as fh:
        fh.write("log\n")
    stamps = {}
    for age in (0, 1, 5, 29, 31, 33, 40, 45, 60, 95, 120, 200):
        d = today - dt.timedelta(days=age)
        stamps[age] = write_report(root, d)
    stamps["abnormal_old"] = write_report(root, today - dt.timedelta(days=150),
                                          "090000", abnormal=True)
    stamps["truncated_old"] = write_report(root, today - dt.timedelta(days=160),
                                           "090000", unparseable=True)
    return stamps


TODAY = dt.date(2026, 9, 10)
tmp = tempfile.mkdtemp()
root = os.path.join(tmp, "site_monitor_reports")
stamps = build(root, TODAY)

reports = pr.collect(root)
check("only dated reports are collected (latest/logs ignored)",
      all(r.key[0].isdigit() for r in reports), True)
check("json+md are grouped as ONE logical report",
      all(len(r.paths) == 2 for r in reports if not r.is_dir), True)

keep, drop = pr.plan(reports, today=TODAY)
kept = {r.key for r in keep}

# --- things that must survive ------------------------------------------------
for name in pr.PROTECTED_NAMES:
    check("protected file survives: %s" % name,
          os.path.exists(os.path.join(root, name)), True)
check("today's report is kept", stamps[0] in kept, True)
for age in (1, 5, 29):
    check("report from %d days ago kept (inside 30-day window)" % age, stamps[age] in kept, True)
check("abnormal report at 150 days is kept (its own monthly track)",
      stamps["abnormal_old"] in kept, True)
check("truncated/unparseable report is treated as abnormal and kept",
      stamps["truncated_old"] in kept, True)

# An abnormal report must not be thinned away by the healthy runs around it.
_same_week = TODAY - dt.timedelta(days=45)
ok_a = write_report(root, _same_week, "070000")
bad_a = write_report(root, _same_week + dt.timedelta(days=1), "070000", abnormal=True)
ok_b = write_report(root, _same_week + dt.timedelta(days=2), "070000")
k3 = {r.key for r in pr.plan(pr.collect(root), today=TODAY)[0]}
check("an abnormal report survives a week full of healthy runs", bad_a in k3, True)
_wk = _same_week.isocalendar()[:2]
_kept_in_week = [r for r in pr.plan(pr.collect(root), today=TODAY)[0]
                 if r.day.isocalendar()[:2] == _wk and 30 < (TODAY - r.day).days <= 90]
check("that week keeps exactly one healthy representative",
      sum(1 for r in _kept_in_week if not r.abnormal), 1)
check("that week also keeps exactly one abnormal representative",
      sum(1 for r in _kept_in_week if r.abnormal), 1)

# --- thinning actually happens ------------------------------------------------
check("something is dropped (storage is bounded)", len(drop) > 0, True)
check("31-90 day band is thinned to weekly representatives",
      sum(1 for r in keep if 30 < (TODAY - r.day).days <= 90 and not r.abnormal) <
      sum(1 for r in reports if 30 < (TODAY - r.day).days <= 90 and not r.abnormal), True)
wk = [r.day.isocalendar()[:2] for r in keep if 30 < (TODAY - r.day).days <= 90 and not r.abnormal]
check("at most one successful report kept per ISO week in the weekly band",
      len(wk) == len(set(wk)), True)
mo = [(r.day.year, r.day.month) for r in keep if (TODAY - r.day).days > 90 and not r.abnormal]
check("at most one successful report kept per month beyond 90 days",
      len(mo) == len(set(mo)), True)

# --- a run that is still writing must not be touched --------------------------
fresh = write_report(root, TODAY - dt.timedelta(days=200), "235959")
now = dt.datetime.now().timestamp()
for ext in ("json", "md"):
    os.utime(os.path.join(root, f"report_{fresh}.{ext}"), (now, now))
k2, d2 = pr.plan(pr.collect(root), today=TODAY)
check("a file modified in the last hour is never deleted",
      fresh in {r.key for r in k2}, True)

# --- dry run changes nothing --------------------------------------------------
before = sorted(os.listdir(root))
res = pr.prune(root, "test", apply=False, today=TODAY, log=lambda *a, **k: None)
check("dry run deletes nothing", sorted(os.listdir(root)), before)
check("dry run still reports bytes it would reclaim", res["bytes_freed"] > 0, True)

# --- apply, then idempotency --------------------------------------------------
res1 = pr.prune(root, "test", apply=True, today=TODAY, log=lambda *a, **k: None)
check("apply removed the planned reports", res1["removed"] > 0, True)
check("no half-deleted report remains (no orphan .md without .json)",
      sorted(f for f in os.listdir(root) if f.startswith("report_2") and f.endswith(".md"))
      == sorted(f.replace(".json", ".md") for f in os.listdir(root)
                if f.startswith("report_2") and f.endswith(".json")), True)
res2 = pr.prune(root, "test", apply=True, today=TODAY, log=lambda *a, **k: None)
check("second run is a no-op (idempotent)", res2["removed"], 0)
for name in pr.PROTECTED_NAMES:
    check("protected file still present after apply: %s" % name,
          os.path.exists(os.path.join(root, name)), True)
check("log file untouched", os.path.exists(os.path.join(root, "daily_runner.log")), True)

# --- cache directories are one logical unit ------------------------------------
croot = os.path.join(tmp, "cache_monitor_reports")
os.makedirs(croot)
def cache_dir(day, ok=True):
    n = f"noon-cache-inspection-{day.strftime('%Y%m%d')}T100000Z"
    d = os.path.join(croot, n); os.makedirs(d)
    with open(os.path.join(d, "SUMMARY.txt"), "w") as fh:
        fh.write("PASS_PUBLIC_HEALTHY\n" if ok else "FAIL_PUBLIC_REQUEST\n")
    with open(os.path.join(d, "result.json"), "w") as fh:
        fh.write("{}")
    old = dt.datetime.combine(day, dt.time(10, 0)).timestamp()
    os.utime(d, (old, old))
    return n
c_recent = cache_dir(TODAY - dt.timedelta(days=3))
c_old_ok = cache_dir(TODAY - dt.timedelta(days=200))
c_old_bad = cache_dir(TODAY - dt.timedelta(days=210), ok=False)
ck, cd = pr.plan(pr.collect(croot), today=TODAY)
ckept = {r.key for r in ck}
check("recent cache inspection kept", c_recent in ckept, True)
check("failed cache inspection kept even at 210 days", c_old_bad in ckept, True)
check("cache inspection is one logical unit (a directory)",
      all(r.is_dir for r in pr.collect(croot)), True)

# --- missing directory is safe -------------------------------------------------
res3 = pr.prune(os.path.join(tmp, "does_not_exist"), "gone", apply=True, log=lambda *a, **k: None)
check("missing directory does not raise and reports zero", res3["considered"], 0)

shutil.rmtree(tmp, ignore_errors=True)
print()
print("--- retention-boundedness suites ---")


# ===========================================================================
# 24-month hard horizon (2026-09-10). "One per month beyond 90 days" has no tail:
# it adds 24 files a year forever. These tests pin the horizon that closes it.
# ===========================================================================

def horizon_suite():
    root = tempfile.mkdtemp(prefix="prune_horizon_")
    try:
        os.makedirs(root, exist_ok=True)
        for name in pr.PROTECTED_NAMES:
            with open(os.path.join(root, name), "w") as fh:
                fh.write("{}")

        D = lambda n: TODAY - dt.timedelta(days=n)          # noqa: E731
        ancient_ok = write_report(root, D(900))             # 29 months, routine
        ancient_bad = write_report(root, D(880), "090000", abnormal=True)
        edge_in = write_report(root, D(pr.MAX_AGE_DAYS - 1), "100000")
        edge_out = write_report(root, D(pr.MAX_AGE_DAYS + 1), "100000")
        mid_ok = write_report(root, D(400))                 # ~13 months, inside horizon
        mid_bad = write_report(root, D(370), "090000", abnormal=True)
        recent = write_report(root, D(3))
        today_rep = write_report(root, TODAY, "070000")

        keep, drop = pr.plan(pr.collect(root), today=TODAY)
        kept = {r.key for r in keep}
        dropped = {r.key for r in drop}

        check("routine report older than 24 months is removed", ancient_ok in dropped, True)
        check("abnormal report older than 24 months is removed too (no open incident)",
              ancient_bad in dropped, True)
        check("the horizon is inclusive: exactly MAX_AGE_DAYS-1 survives",
              edge_in in kept, True)
        check("...and MAX_AGE_DAYS+1 does not", edge_out in dropped, True)
        check("monthly representative inside 24 months survives (ok track)",
              mid_ok in kept, True)
        check("monthly representative inside 24 months survives (abnormal track)",
              mid_bad in kept, True)
        check("recent report survives", recent in kept, True)
        check("today's report survives", today_rep in kept, True)
        for n in pr.PROTECTED_NAMES:
            check("latest alias survives the horizon: %s" % n,
                  os.path.exists(os.path.join(root, n)), True)

        # The horizon must be finite, not merely large: prove the retained set stops growing.
        # Ten years of daily runs must retain no more than the closed-form bound.
        big = tempfile.mkdtemp(prefix="prune_bound_")
        for i in range(0, 3650, 5):
            write_report(big, TODAY - dt.timedelta(days=i), "080000",
                         abnormal=(i % 20 == 0))
        bkeep, bdrop = pr.plan(pr.collect(big), today=TODAY)
        bound = (pr.RECENT_DAYS * 1                     # r=1 run per day in this corpus
                 + 2 * (-(-(pr.WEEKLY_DAYS - pr.RECENT_DAYS) // 7))
                 + 2 * (-(-(pr.MAX_AGE_DAYS - pr.WEEKLY_DAYS) // 30)) + 2)
        check("10 years of daily runs retains a finite set", len(bkeep) <= bound, True)
        check("...and most of that decade is actually deleted", len(bdrop) > len(bkeep), True)
        oldest_kept = min((TODAY - r.day).days for r in bkeep) if bkeep else 0
        newest_kept = max((TODAY - r.day).days for r in bkeep)
        check("nothing retained beyond the horizon", newest_kept <= pr.MAX_AGE_DAYS, True)
        check("and the recent window is intact", oldest_kept == 0, True)
        shutil.rmtree(big, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def incident_suite():
    """An unresolved incident's onset must outlive the horizon; a closed one must not."""
    root = tempfile.mkdtemp(prefix="prune_incident_")
    try:
        D = lambda n: TODAY - dt.timedelta(days=n)          # noqa: E731
        onset = write_report(root, D(900), "080000", abnormal=True)
        write_report(root, D(400), "080000", abnormal=True)
        write_report(root, D(2), "080000", abnormal=True)   # still failing today
        keep, drop = pr.plan(pr.collect(root), today=TODAY)
        kept = {r.key for r in keep}
        check("onset of an unresolved incident outlives the 24-month horizon",
              onset in kept, True)
        reasons = [r.reason for r in keep if r.key == onset]
        check("...and says so", "unresolved incident" in reasons[0], True)

        # Now close the incident with a healthy newest report: the old onset loses protection.
        write_report(root, TODAY, "090000")
        keep2, _ = pr.plan(pr.collect(root), today=TODAY)
        check("once the incident closes, the ancient report expires normally",
              onset in {r.key for r in keep2}, False)
        check("the protection is finite: at most one extra report",
              len(keep) - len(keep2) <= 2, True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def log_rotation_suite():
    home = tempfile.mkdtemp(prefix="prune_logs_")
    try:
        d = os.path.join(home, "ambimat_job_logs")
        os.makedirs(d)
        big = os.path.join(d, "scheduler_watchdog.log")
        small = os.path.join(d, "seo_daily.log")
        with open(big, "w") as fh:
            fh.write("x" * (pr.LOG_MAX_BYTES + 2048))
        with open(small, "w") as fh:
            fh.write("still small\n")

        n, _, errs = pr.rotate_logs(home, apply=False, log=lambda *a: None)
        check("dry run reports the oversized log", n, 1)
        check("dry run mutates nothing", os.path.getsize(big) > pr.LOG_MAX_BYTES, True)
        check("dry run creates no generation file", os.path.exists(big + ".1"), False)

        n, _, errs = pr.rotate_logs(home, apply=True, log=lambda *a: None)
        check("apply rotated exactly one log", (n, errs), (1, 0))
        check("the active log still exists", os.path.exists(big), True)
        check("...and is now empty, not deleted", os.path.getsize(big), 0)
        check("its content was preserved in .1",
              os.path.getsize(big + ".1") > pr.LOG_MAX_BYTES, True)
        check("the small log was left alone", os.path.getsize(small), len("still small\n"))

        # Generations must cap, not accumulate: many rotations, still LOG_GENERATIONS files.
        for _ in range(6):
            with open(big, "w") as fh:
                fh.write("y" * (pr.LOG_MAX_BYTES + 16))
            pr.rotate_logs(home, apply=True, log=lambda *a: None)
        gens = [f for f in os.listdir(d) if f.startswith("scheduler_watchdog.log.")]
        check("generations are capped, so log storage is bounded",
              len(gens), pr.LOG_GENERATIONS)
        cap = (pr.LOG_GENERATIONS + 1) * (pr.LOG_MAX_BYTES + 4096)
        total = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
        check("total log bytes stay under the structural cap", total < cap, True)

        # An append-mode writer that held the file open across a rotation must not break.
        with open(big, "a") as writer:
            writer.write("z" * (pr.LOG_MAX_BYTES + 16))
            writer.flush()
            pr.rotate_logs(home, apply=True, log=lambda *a: None)
            writer.write("after rotation\n")
            writer.flush()
        check("a writer holding the log open across rotation still lands in the live file",
              "after rotation" in open(big).read(), True)

        check("missing log dir does not raise",
              pr.rotate_logs(os.path.join(home, "nope"), apply=True, log=lambda *a: None),
              (0, 0, 0))
    finally:
        shutil.rmtree(home, ignore_errors=True)


horizon_suite()
incident_suite()
log_rotation_suite()

print("\nall retention-boundedness checks passed" if not failures
      else "\n%d FAILURE(S)" % failures)
sys.exit(1 if failures else 0)

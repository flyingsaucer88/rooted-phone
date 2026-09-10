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
if failures:
    print("%d FAILURE(S)" % failures)
    sys.exit(1)
print("all prune_reports regression checks passed")

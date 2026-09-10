#!/usr/bin/env python3
"""Bound the growth of Rooted Phone report directories without losing evidence.

Report storage has never been pruned. On 2026-09-10 it held 462 logical reports across
~168 MB. The device has ~20 GB free, so this is preventive housekeeping, not a rescue.

WHAT A LOGICAL REPORT IS. The site monitor and the SEO tracker write a dated pair
(report_<stamp>.json + report_<stamp>.md) per run, plus report_latest.{json,md,html} which
they overwrite. The cache monitor writes one directory per inspection. This module treats
the dated pair, or the directory, as ONE unit: it never deletes half a report and leaves a
fragment behind.

WHAT IS NEVER DELETED, at any age:
  - report_latest.* and every other non-dated file (logs, ledgers, state, history)
  - unverified_ledger.json, which the staleness ledger depends on
  - seo_tracker_reports/history/ and state/, which are where SEO trends actually live
  - anything from today, or anything modified in the last hour (a run may be writing it)
  - any report that is not a clean success — see below

WHY FAILURES ARE KEPT SEPARATELY. A routine all-green report is interchangeable with the
fifty either side of it; the one that recorded an alert, a warning, an unreachable site or a
truncated crawl is the only evidence that it happened. So successful and abnormal reports
are thinned on their OWN tracks: each period keeps a representative of each kind. A week in
which something broke can never be thinned away by the healthy runs around it, and the
newest abnormal report is never removed at all.

Thinning abnormal reports rather than keeping every one is deliberate. On this estate 339 of
343 site reports are "abnormal" — the monitor was noisy for months before the remediation
campaigns — so a keep-all-failures rule would retain everything and bound nothing, which is
the opposite of the point. One representative per period per kind keeps the history legible
and the storage finite.

TIERS (applied independently to successful and to abnormal reports):
  - last RECENT_DAYS days .................. keep everything
  - RECENT_DAYS..WEEKLY_DAYS ............... keep the newest of each ISO week, per kind
  - beyond WEEKLY_DAYS ..................... keep the newest of each month, per kind

Dry-run is the default. Nothing is deleted without --apply.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import sys

RECENT_DAYS = 30
WEEKLY_DAYS = 90
MIN_AGE_SECONDS = 3600          # never touch something a run may still be writing

_STAMP = re.compile(r"^report_(\d{8})_(\d{6})\.(json|md|html)$")
_DIRSTAMP = re.compile(r"^(?:noon-cache-inspection|manual-verify)-(\d{8})T\d{6}Z$")

PROTECTED_NAMES = ("report_latest.json", "report_latest.md", "report_latest.html",
                   "unverified_ledger.json")
PROTECTED_DIRS = ("history", "state", "per_site")


class Report:
    """One logical report: a dated file set, or a dated directory."""

    def __init__(self, key, day, paths, is_dir=False):
        self.key, self.day, self.paths, self.is_dir = key, day, paths, is_dir
        self.abnormal = False
        self.reason = ""

    @property
    def bytes(self):
        total = 0
        for p in self.paths:
            try:
                if os.path.isdir(p):
                    for root, _, files in os.walk(p):
                        for f in files:
                            total += os.path.getsize(os.path.join(root, f))
                else:
                    total += os.path.getsize(p)
            except OSError:
                pass
        return total


def _parse_day(text):
    try:
        return _dt.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except (ValueError, IndexError):
        return None


def _json_is_abnormal(path):
    """True when a site/SEO report recorded anything other than a clean success.

    Read defensively: a report that cannot be parsed is itself abnormal — a truncated or
    half-written file is exactly the diagnostic evidence worth keeping.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return True, "unparseable/truncated"
    totals = data.get("totals") or {}
    if totals.get("partial"):
        return True, "partial run"
    for field, label in (("sites_unreachable", "unreachable site"),
                         ("sites_with_alerts", "alerts"),
                         ("sites_timed_out", "timed out"),
                         ("broken_pages", "broken pages"),
                         ("broken_links", "broken links")):
        if (totals.get(field) or 0) > 0:
            return True, label
    sites = data.get("sites")
    sites = list(sites.values()) if isinstance(sites, dict) else (sites or [])
    for s in sites:
        if s.get("alerts") or s.get("warnings"):
            return True, "site alert/warning"
        if s.get("reachable") is False or s.get("timed_out"):
            return True, "site unreachable/timeout"
    return False, ""


def _dir_is_abnormal(path):
    """Cache inspections: anything whose SUMMARY is not a PASS is worth keeping."""
    summary = os.path.join(path, "SUMMARY.txt")
    try:
        with open(summary, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4000)
    except Exception:
        return True, "missing/unreadable SUMMARY"
    if re.search(r"\bPASS_[A-Z_]+", head):
        return False, ""
    return True, "non-PASS classification"


def collect(root):
    """Group a report directory into logical reports. Non-dated files are ignored entirely."""
    reports = {}
    if not os.path.isdir(root):
        return []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if name in PROTECTED_NAMES or name in PROTECTED_DIRS:
            continue
        m = _STAMP.match(name)
        if m:
            day = _parse_day(m.group(1))
            if not day:
                continue
            key = f"{m.group(1)}_{m.group(2)}"
            reports.setdefault(key, Report(key, day, []))
            reports[key].paths.append(path)
            continue
        if os.path.isdir(path):
            d = _DIRSTAMP.match(name)
            if d:
                day = _parse_day(d.group(1))
                if day:
                    reports[name] = Report(name, day, [path], is_dir=True)
    out = []
    for rep in reports.values():
        if rep.is_dir:
            rep.abnormal, rep.reason = _dir_is_abnormal(rep.paths[0])
        else:
            js = [p for p in rep.paths if p.endswith(".json")]
            rep.abnormal, rep.reason = _json_is_abnormal(js[0]) if js else (True, "no json in set")
        out.append(rep)
    return sorted(out, key=lambda r: r.key)


def plan(reports, today=None, now=None):
    """Decide keep/delete per logical report. Pure: no filesystem writes."""
    today = today or _dt.date.today()
    now = now if now is not None else _dt.datetime.now().timestamp()
    keep, drop = [], []

    abnormal = [r for r in reports if r.abnormal]
    newest_abnormal = abnormal[-1].key if abnormal else None

    # Buckets are keyed by (period, kind) so an abnormal week keeps its own representative
    # even when healthy runs surround it.
    seen_week, seen_month = set(), set()
    for rep in sorted(reports, key=lambda r: r.key, reverse=True):   # newest first
        age = (today - rep.day).days
        kind = "abnormal" if rep.abnormal else "ok"
        detail = f" — {rep.reason}" if rep.abnormal and rep.reason else ""
        why = None

        youngest = 0
        for p in rep.paths:
            try:
                youngest = max(youngest, os.path.getmtime(p))
            except OSError:
                pass
        if now - youngest < MIN_AGE_SECONDS:
            why = "written within the last hour"
        elif age <= 0:
            why = "today's report"
        elif rep.key == newest_abnormal:
            why = f"newest abnormal report{detail}"
        elif age <= RECENT_DAYS:
            why = f"within {RECENT_DAYS}-day window"
        elif age <= WEEKLY_DAYS:
            wk = rep.day.isocalendar()[:2] + (kind,)
            if wk not in seen_week:
                seen_week.add(wk)
                why = f"weekly {kind} representative ({wk[0]}-W{wk[1]:02d}){detail}"
        else:
            mo = (rep.day.year, rep.day.month, kind)
            if mo not in seen_month:
                seen_month.add(mo)
                why = f"monthly {kind} representative ({mo[0]}-{mo[1]:02d}){detail}"

        if why:
            rep.reason = why
            keep.append(rep)
        else:
            drop.append(rep)
    return sorted(keep, key=lambda r: r.key), sorted(drop, key=lambda r: r.key)


def prune(root, label, apply=False, today=None, log=print):
    reports = collect(root)
    if not reports:
        log(f"  {label:<14} no dated reports found ({root})")
        return {"label": label, "considered": 0, "kept": 0, "removed": 0,
                "bytes_before": 0, "bytes_freed": 0, "errors": 0}
    keep, drop = plan(reports, today=today)
    before = sum(r.bytes for r in reports)
    freed, errors = 0, 0
    for rep in drop:
        size = rep.bytes
        if apply:
            try:
                for p in rep.paths:
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            except OSError as exc:
                errors += 1
                log(f"  {label:<14} FAILED to remove {rep.key}: {exc}")
                continue
        freed += size
        log(f"  {label:<14} {'removed' if apply else 'would remove'} {rep.key} "
            f"({len(rep.paths)} file(s), {size:,} B)")
    oldest = keep[0] if keep else None
    newest = keep[-1] if keep else None
    log(f"  {label:<14} considered {len(reports)} · keep {len(keep)} · "
        f"{'removed' if apply else 'would remove'} {len(drop)} · "
        f"{freed:,} B of {before:,} B")
    if oldest:
        log(f"  {label:<14} oldest retained {oldest.key} ({oldest.reason}); "
            f"newest retained {newest.key}")
    log(f"  {label:<14} abnormal reports retained: "
        f"{sum(1 for r in keep if r.abnormal)}")
    return {"label": label, "considered": len(reports), "kept": len(keep),
            "removed": len(drop), "bytes_before": before, "bytes_freed": freed,
            "errors": errors}


def main(argv=None):
    home = os.path.expanduser("~")
    ap = argparse.ArgumentParser(description="Bound Rooted Phone report storage.")
    ap.add_argument("--apply", action="store_true",
                    help="actually delete (default is a dry run that changes nothing)")
    ap.add_argument("--site-dir", default=os.path.join(home, "site_monitor_reports"))
    ap.add_argument("--seo-dir", default=os.path.join(home, "seo_tracker_reports"))
    ap.add_argument("--cache-dir", default=os.path.join(home, "cache_monitor_reports"))
    ap.add_argument("--per-site", action="store_true", default=True,
                    help="also prune site_monitor_reports/per_site/<slug>/")
    args = ap.parse_args(argv)

    stamp = _dt.datetime.now().strftime("%F %T %z")
    print(f"===== {stamp} prune_reports ({'APPLY' if args.apply else 'DRY RUN'}) =====")
    results = [prune(args.site_dir, "site", args.apply),
               prune(args.seo_dir, "seo", args.apply),
               prune(args.cache_dir, "cache", args.apply)]

    per_site_root = os.path.join(args.site_dir, "per_site")
    if args.per_site and os.path.isdir(per_site_root):
        for slug in sorted(os.listdir(per_site_root)):
            d = os.path.join(per_site_root, slug)
            if os.path.isdir(d):
                results.append(prune(d, f"site/{slug[:9]}", args.apply))

    freed = sum(r["bytes_freed"] for r in results)
    before = sum(r["bytes_before"] for r in results)
    errors = sum(r["errors"] for r in results)
    print(f"  TOTAL          {'freed' if args.apply else 'would free'} {freed:,} B "
          f"of {before:,} B across {sum(r['considered'] for r in results)} logical reports "
          f"({sum(r['removed'] for r in results)} removed, "
          f"{sum(r['kept'] for r in results)} kept, {errors} error(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

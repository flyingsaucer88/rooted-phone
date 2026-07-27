#!/data/data/com.termux/files/usr/bin/env python3
"""merge_reports.py — combine per-site monitor reports into one combined report.

Used by run_daily.sh's per-site (one-process-per-site) mode: each site is crawled in its own
Python process writing `<per-site-dir>/<slug>/report_latest.json`; this merges them into a single
`report_latest.{json,md,html}` (+ timestamped) in the main output dir. Keeps memory bounded (each
crawl process holds only one site) while presenting one unified report.

Usage:
  python merge_reports.py --per-site-dir DIR --output-dir DIR [--order name1,name2,...]
"""
import argparse
import datetime as _dt
import json
import os
import sys

import render_report


def main():
    ap = argparse.ArgumentParser(description="Merge per-site site_monitor reports.")
    ap.add_argument("--per-site-dir", required=True, help="dir containing <slug>/report_latest.json")
    ap.add_argument("--output-dir", required=True, help="where to write the combined report")
    ap.add_argument("--order", default="", help="comma-separated site names for output ordering")
    args = ap.parse_args()

    order = [s.strip() for s in args.order.split(",") if s.strip()]
    sites, missing = [], []
    if os.path.isdir(args.per_site_dir):
        for slug in sorted(os.listdir(args.per_site_dir)):
            p = os.path.join(args.per_site_dir, slug, "report_latest.json")
            if not os.path.isfile(p):
                missing.append(slug)
                continue
            try:
                d = json.load(open(p))
                sites.extend(d.get("sites", []))
            except Exception as e:
                missing.append(f"{slug} (unreadable: {e})")

    # order sites as requested (config order), unknowns appended
    if order:
        rank = {n: i for i, n in enumerate(order)}
        sites.sort(key=lambda s: rank.get(s.get("name"), len(order)))

    ext_checked = any(s.get("broken_external_links") is not None
                      and not any("external link checking disabled" in x
                                  for x in s.get("skipped", [])) for s in sites)
    totals = {
        "sites_total": len(sites),
        "sites_reported": len(sites),
        "sites_unreachable": sum(1 for s in sites if not s.get("reachable")),
        "sites_with_alerts": sum(1 for s in sites if s.get("alerts")),
        "sites_ok": sum(1 for s in sites
                        if s.get("reachable") and not s.get("alerts") and not s.get("warnings")),
        "sites_timed_out": sum(1 for s in sites if s.get("timed_out")),
        "pages_crawled": sum(s.get("pages_crawled", 0) for s in sites),
        "broken_pages": sum(len(s.get("broken_pages", [])) for s in sites),
        "broken_links": sum(len(s.get("broken_internal_links", []))
                            + len(s.get("broken_external_links", [])) for s in sites),
        "unverified_links": sum(len(s.get("unverified_internal_links", []))
                                + len(s.get("unverified_external_links", [])) for s in sites),
        "suspicious_warnings": sum(len(s.get("warnings", [])) for s in sites),
        "external_links_checked": ext_checked,
        "partial": bool(missing) or any(s.get("timed_out") for s in sites),
        "merged_per_site": True,
        "missing_site_reports": missing,
    }
    report = {
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generator": "RootedPhoneSiteMonitor/0.1 (per-site merged)",
        "limitation": render_report.LIMITATION,
        "run_args": {"mode": "per-site-processes"},
        "sites": sites,
        "totals": totals,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    md = render_report.render_markdown(report)
    html = render_report.render_html(report)
    with open(os.path.join(args.output_dir, f"report_{stamp}.json"), "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.output_dir, f"report_{stamp}.md"), "w") as f:
        f.write(md)
    for name, content in (("report_latest.json", json.dumps(report, indent=2, ensure_ascii=False)),
                          ("report_latest.md", md),
                          ("report_latest.html", html)):
        with open(os.path.join(args.output_dir, name), "w") as f:
            f.write(content)

    print(render_report.compact_summary(report))
    if missing:
        print(f"[merge] WARNING: missing/failed per-site reports: {', '.join(missing)}")
    print(f"[merge] combined {len(sites)} sites -> {os.path.join(args.output_dir, 'report_latest.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

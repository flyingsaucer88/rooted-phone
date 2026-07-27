#!/data/data/com.termux/files/usr/bin/env python3
"""render_report.py — turn a site_monitor JSON report into Markdown / HTML.

Two uses:
  1. Imported by run_site_monitor.py (render_markdown / render_html).
  2. Standalone viewer:
        python render_report.py --latest [--open]
        python render_report.py --json report_YYYYMMDD_HHMMSS.json [--open]

The renderer never asserts "hacked". It uses the wording:
  Suspicious indicators detected / Potential SEO spam indicators /
  Potential injected external links/scripts / Broken pages detected /
  No public-page compromise indicators detected.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys

LIMITATION = (
    "This is a PUBLIC-CRAWL-BASED compromise indicator + SEO health report. It can only detect "
    "evidence of compromise that is visible on public pages at crawl time. It CANNOT prove whether "
    "a hack was attempted in the last 24 hours — that needs server/hosting/WAF logs, Search Console "
    "alerts, or CMS security logs, which this tool does not have. All 'suspicious' findings are "
    "advisory WARNINGS to investigate, not confirmed compromise."
)


def _status_word(site):
    if not site.get("reachable", False):
        return "UNREACHABLE"
    if site.get("alerts"):
        return "ALERT"
    if site.get("warnings"):
        return "WARN"
    return "OK"


def overall_status(report):
    sites = report.get("sites", [])
    if any(not s.get("reachable", False) for s in sites):
        return "ALERT"
    if any(s.get("alerts") for s in sites):
        return "ALERT"
    if any(s.get("warnings") for s in sites):
        return "WARN"
    return "OK"


def compact_summary(report):
    """One-line-ish terminal/notification summary."""
    t = report.get("totals", {})
    status = overall_status(report)
    if status == "OK":
        return f"OK: all {t.get('sites_total', 0)} sites healthy — no public-page compromise indicators detected."
    parts = []
    if t.get("sites_unreachable"):
        parts.append(f"{t['sites_unreachable']} unreachable")
    if t.get("broken_pages"):
        parts.append(f"{t['broken_pages']} broken pages")
    if t.get("broken_links"):
        parts.append(f"{t['broken_links']} broken links")
    if t.get("unverified_links"):
        parts.append(f"{t['unverified_links']} unverified links")
    if t.get("suspicious_warnings"):
        parts.append(f"{t['suspicious_warnings']} suspicious warnings")
    head = "ALERT" if status == "ALERT" else "WARN"
    return f"{head}: " + ", ".join(parts) if parts else f"{head}: see report"


def render_markdown(report):
    lines = []
    a = lines.append
    a("# Ambimat Site Monitor Report")
    a("")
    a(f"- **Generated:** {report.get('generated_at', '?')}")
    a(f"- **Generator:** {report.get('generator', '?')}")
    a(f"- **Overall status:** {overall_status(report)}")
    a(f"- **Summary:** {compact_summary(report)}")
    a("")
    a("> **Accuracy limitation.** " + LIMITATION)
    a("")
    for s in report.get("sites", []):
        a(f"## {s.get('name')} — {_status_word(s)}")
        a(f"- URL: {s.get('base_url')}")
        if s.get("final_url") and s.get("final_url") != s.get("base_url"):
            a(f"- Resolved to: {s.get('final_url')}")
        if not s.get("reachable", False):
            a(f"- **UNREACHABLE:** {s.get('error')}")
            a("")
            continue
        http = s.get("http", {})
        a(f"- Homepage HTTP status: {http.get('status')}")
        a(f"- Pages crawled: {s.get('pages_crawled', 0)}")
        cert = s.get("cert", {})
        if cert:
            if cert.get("error"):
                a(f"- TLS certificate: could not check ({cert.get('error')})")
            else:
                a(f"- TLS certificate expires: {cert.get('not_after')} "
                  f"({cert.get('days_to_expiry')} days)")
        sec = s.get("security_headers", {})
        if sec:
            a(f"- Security headers present: {', '.join(sec.get('present', [])) or 'none'}")
            if sec.get("missing"):
                a(f"- Security headers MISSING: {', '.join(sec.get('missing'))}")

        alerts = s.get("alerts", [])
        a("")
        a(f"### Alerts ({len(alerts)})")
        if not alerts:
            a("- No public-page compromise indicators detected.")
        for al in alerts:
            a(f"- **[{al.get('type')}]** {al.get('detail')}"
              + (f"  \n  ↳ {al.get('url')}" if al.get('url') else ""))

        warnings = s.get("warnings", [])
        a("")
        a(f"### Warnings ({len(warnings)})")
        if not warnings:
            a("- None.")
        for w in warnings[:200]:
            a(f"- [{w.get('type')}] {w.get('detail')}"
              + (f"  \n  ↳ {w.get('url')}" if w.get('url') else ""))
        if len(warnings) > 200:
            a(f"- … {len(warnings) - 200} more warnings (see JSON report).")

        seo = s.get("seo", {})
        a("")
        a("### SEO checks")
        a(f"- Missing title: {len(seo.get('pages_missing_title', []))}")
        a(f"- Missing meta description: {len(seo.get('pages_missing_description', []))}")
        a(f"- Missing H1: {len(seo.get('pages_missing_h1', []))}")
        a(f"- Missing canonical: {len(seo.get('pages_missing_canonical', []))}")
        a(f"- noindex pages: {len(seo.get('noindex_pages', []))}")
        a(f"- Duplicate titles: {len(seo.get('duplicate_titles', {}))}")
        a(f"- Duplicate descriptions: {len(seo.get('duplicate_descriptions', {}))}")

        bp = s.get("broken_pages", [])
        bil = s.get("broken_internal_links", [])
        bel = s.get("broken_external_links", [])
        a("")
        a("### Broken pages / links")
        a(f"- Broken pages: {len(bp)}")
        for b in bp[:30]:
            a(f"  - {b.get('status')} {b.get('url')}")
        a(f"- Broken internal links: {len(bil)}")
        for b in bil[:30]:
            a(f"  - {b.get('status')} {b.get('url')} (on {b.get('found_on')})")
        a(f"- Broken external links: {len(bel)}")
        for b in bel[:30]:
            a(f"  - {b.get('status')} {b.get('url')} (on {b.get('found_on')})")
        uil = s.get("unverified_internal_links", [])
        uel = s.get("unverified_external_links", [])
        if uil or uel:
            a(f"- Unverified links (no definitive status — connection error/timeout, NOT confirmed "
              f"broken): {len(uil)} internal, {len(uel)} external")
            for b in (uil + uel)[:20]:
                a(f"  - (unverified) {b.get('url')} (on {b.get('found_on')})")

        drift = s.get("title_drift", [])
        if drift:
            a("")
            a(f"### Title changes since last run ({len(drift)})")
            for d in drift[:30]:
                a(f"- {d.get('url')}")
                a(f"  - was: {d.get('old')!r}")
                a(f"  - now: {d.get('new')!r}")
        a("")
    return "\n".join(lines) + "\n"


def render_html(report):
    status = overall_status(report)
    color = {"OK": "#2d6a4f", "WARN": "#d4740e", "ALERT": "#c53030"}.get(status, "#555")
    esc = html.escape
    out = []
    a = out.append
    a("<meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>")
    a("<style>"
      "body{font-family:-apple-system,Roboto,Segoe UI,sans-serif;margin:0;padding:12px;"
      "background:#faf9f7;color:#1a1a1a;font-size:15px;line-height:1.45}"
      ".hdr{padding:14px;border-radius:10px;color:#fff;margin-bottom:14px}"
      ".site{background:#fff;border:1px solid #e5e2dc;border-radius:10px;padding:12px;margin-bottom:12px}"
      ".badge{display:inline-block;padding:2px 8px;border-radius:6px;color:#fff;font-size:12px;font-weight:600}"
      ".alert{color:#c53030;font-weight:600}.warn{color:#d4740e}.ok{color:#2d6a4f}"
      "code{background:#f0eee9;padding:1px 4px;border-radius:4px;font-size:13px;word-break:break-all}"
      "ul{padding-left:18px;margin:6px 0}.small{color:#666;font-size:13px}"
      "h1{font-size:20px}h2{font-size:17px;margin-bottom:4px}h3{font-size:14px;margin:10px 0 2px}"
      "</style>")
    a(f"<div class='hdr' style='background:{color}'>")
    a(f"<h1 style='margin:0'>Ambimat Site Monitor</h1>")
    a(f"<div style='font-size:18px;font-weight:700'>{esc(status)}</div>")
    a(f"<div class='small' style='color:#fff'>{esc(report.get('generated_at',''))}</div>")
    a(f"<div style='margin-top:6px'>{esc(compact_summary(report))}</div>")
    a("</div>")
    a(f"<p class='small'><b>Accuracy limitation.</b> {esc(LIMITATION)}</p>")

    badge_color = {"OK": "#2d6a4f", "WARN": "#d4740e", "ALERT": "#c53030", "UNREACHABLE": "#c53030"}
    for s in report.get("sites", []):
        sw = _status_word(s)
        a("<div class='site'>")
        a(f"<h2>{esc(s.get('name',''))} "
          f"<span class='badge' style='background:{badge_color.get(sw,'#555')}'>{sw}</span></h2>")
        a(f"<div class='small'><code>{esc(s.get('base_url',''))}</code></div>")
        if not s.get("reachable", False):
            a(f"<p class='alert'>UNREACHABLE: {esc(str(s.get('error')))}</p></div>")
            continue
        http = s.get("http", {})
        a(f"<div class='small'>Homepage HTTP {esc(str(http.get('status')))} · "
          f"{s.get('pages_crawled',0)} pages crawled</div>")
        cert = s.get("cert", {})
        if cert and not cert.get("error"):
            a(f"<div class='small'>TLS cert expires {esc(str(cert.get('not_after')))} "
              f"({cert.get('days_to_expiry')} days)</div>")
        sec = s.get("security_headers", {})
        if sec.get("missing"):
            a(f"<div class='small warn'>Missing security headers: {esc(', '.join(sec['missing']))}</div>")

        alerts = s.get("alerts", [])
        a(f"<h3 class='alert'>Alerts ({len(alerts)})</h3>")
        if not alerts:
            a("<div class='ok'>No public-page compromise indicators detected.</div>")
        else:
            a("<ul>")
            for al in alerts:
                u = f" <code>{esc(al['url'])}</code>" if al.get("url") else ""
                a(f"<li class='alert'>[{esc(al.get('type',''))}] {esc(al.get('detail',''))}{u}</li>")
            a("</ul>")

        warnings = s.get("warnings", [])
        a(f"<h3 class='warn'>Warnings ({len(warnings)})</h3>")
        if warnings:
            a("<ul>")
            for w in warnings[:150]:
                u = f" <code>{esc(w['url'])}</code>" if w.get("url") else ""
                a(f"<li>[{esc(w.get('type',''))}] {esc(w.get('detail',''))}{u}</li>")
            a("</ul>")
            if len(warnings) > 150:
                a(f"<div class='small'>… {len(warnings)-150} more (see JSON).</div>")
        else:
            a("<div class='ok'>None.</div>")

        seo = s.get("seo", {})
        a("<h3>SEO checks</h3><ul class='small'>")
        a(f"<li>Missing title: {len(seo.get('pages_missing_title',[]))}</li>")
        a(f"<li>Missing description: {len(seo.get('pages_missing_description',[]))}</li>")
        a(f"<li>Missing H1: {len(seo.get('pages_missing_h1',[]))}</li>")
        a(f"<li>Missing canonical: {len(seo.get('pages_missing_canonical',[]))}</li>")
        a(f"<li>noindex pages: {len(seo.get('noindex_pages',[]))}</li>")
        a(f"<li>Duplicate titles: {len(seo.get('duplicate_titles',{}))}</li>")
        a(f"<li>Duplicate descriptions: {len(seo.get('duplicate_descriptions',{}))}</li>")
        a("</ul>")

        bp, bil, bel = s.get("broken_pages", []), s.get("broken_internal_links", []), s.get("broken_external_links", [])
        uil = s.get("unverified_internal_links", [])
        uel = s.get("unverified_external_links", [])
        a(f"<h3>Broken pages/links</h3><div class='small'>"
          f"pages: {len(bp)} · broken internal: {len(bil)} · broken external: {len(bel)}"
          f" · unverified (not confirmed broken): {len(uil) + len(uel)}</div>")
        drift = s.get("title_drift", [])
        if drift:
            a(f"<h3 class='warn'>Title changes since last run ({len(drift)})</h3><ul class='small'>")
            for d in drift[:20]:
                a(f"<li><code>{esc(d.get('url',''))}</code>: "
                  f"{esc(str(d.get('old')))} → {esc(str(d.get('new')))}</li>")
            a("</ul>")
        a("</div>")
    return "\n".join(out) + "\n"


def _open_on_phone(path):
    if shutil.which("termux-open"):
        try:
            subprocess.run(["termux-open", path], timeout=15)
            return True
        except Exception as e:
            print(f"[render] termux-open failed: {e}", file=sys.stderr)
    else:
        print("[render] termux-open not available; view the file manually.", file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser(description="Render/view a site_monitor report.")
    ap.add_argument("--output-dir", default=os.path.expanduser("~/site_monitor_reports"))
    ap.add_argument("--latest", action="store_true", help="use report_latest.json in output-dir")
    ap.add_argument("--json", help="path to a specific report JSON")
    ap.add_argument("--open", action="store_true", help="open the HTML report on the phone")
    args = ap.parse_args()

    if args.json:
        json_path = args.json
    elif args.latest:
        json_path = os.path.join(args.output_dir, "report_latest.json")
    else:
        print("Specify --latest or --json PATH", file=sys.stderr)
        return 2
    if not os.path.isfile(json_path):
        print(f"No report found at {json_path}", file=sys.stderr)
        return 1

    with open(json_path) as f:
        report = json.load(f)

    md = render_markdown(report)
    html_doc = render_html(report)
    md_path = os.path.join(args.output_dir, "report_latest.md")
    html_path = os.path.join(args.output_dir, "report_latest.html")
    with open(md_path, "w") as f:
        f.write(md)
    with open(html_path, "w") as f:
        f.write(html_doc)
    print(compact_summary(report))
    print(f"[render] markdown: {md_path}")
    print(f"[render] html:     {html_path}")
    if args.open:
        _open_on_phone(html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

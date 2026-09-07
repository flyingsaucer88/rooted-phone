#!/usr/bin/env python3
"""Guard: the eight mandatory production sites must be monitored by BOTH trackers.

On 2026-09-07 the site monitor and the SEO tracker each carried their own,
independently-edited site list. v2x.ambimat.com and ai.ambimat.com were live and
in neither one, so two production sites went unmonitored without anything failing.
This test is the thing that would have caught it.

Stdlib only (regex over the `base_url:` / `domain:` lines) so it runs on the Mac,
in CI and on the phone without PyYAML.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The authoritative set. Changing this list is a deliberate, reviewable act.
MANDATORY = {
    "ambimat.com",
    "ambisecure.ambimat.com",
    "ambipower.ambimat.com",
    "ambiautomation.ambimat.com",
    "v2x.ambimat.com",
    "ai.ambimat.com",
    "roboracer.ambimat.com",
    "orders.ambimat.com",
}

# Retired — must never be reintroduced by a copy-paste from an old report.
RETIRED = {"ambimechanicals.com", "ambimechanicals.ambimat.com"}

INVENTORIES = {
    "site monitor": ("site_monitor/config/sites.yaml", r"^\s*base_url:\s*https?://([^/\s]+)"),
    "SEO tracker": ("phone/seo_tracker_config.yaml", r"^\s*domain:\s*([^\s#]+)"),
}


def hosts(rel, pattern):
    path = os.path.join(ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return {m.group(1).lower().rstrip("/") for m in re.finditer(pattern, text, re.M)}


def test_mandatory_sites_present():
    for label, (rel, pattern) in INVENTORIES.items():
        found = hosts(rel, pattern)
        missing = MANDATORY - found
        assert not missing, "%s (%s) is missing mandatory sites: %s" % (
            label, rel, ", ".join(sorted(missing)))


def test_retired_sites_absent():
    for label, (rel, pattern) in INVENTORIES.items():
        found = hosts(rel, pattern)
        resurrected = RETIRED & found
        assert not resurrected, "%s (%s) resurrected retired sites: %s" % (
            label, rel, ", ".join(sorted(resurrected)))


def test_no_duplicate_entries():
    for label, (rel, pattern) in INVENTORIES.items():
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as fh:
            all_hosts = [m.group(1).lower().rstrip("/")
                         for m in re.finditer(pattern, fh.read(), re.M)]
        dupes = {h for h in all_hosts if all_hosts.count(h) > 1}
        assert not dupes, "%s (%s) lists duplicates: %s" % (label, rel, ", ".join(sorted(dupes)))


def test_both_inventories_agree():
    """Neither tracker may monitor a site the other does not know about."""
    sm = hosts(*INVENTORIES["site monitor"])
    seo = hosts(*INVENTORIES["SEO tracker"])
    assert sm == seo, "inventories drifted — site-monitor-only: %s ; SEO-only: %s" % (
        ", ".join(sorted(sm - seo)) or "none", ", ".join(sorted(seo - sm)) or "none")


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
    print("\n%d passed, %d failed" % (4 - len(failures), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

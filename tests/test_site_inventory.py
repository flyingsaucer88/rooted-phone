#!/usr/bin/env python3
"""Guard: the nine mandatory production sites must be monitored by BOTH trackers.

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
# esim.ambimat.com became mandatory by owner decision on 2026-09-07 (it was previously
# configured but unratified); the estate is now nine sites.
MANDATORY = {
    "ambimat.com",
    "ambisecure.ambimat.com",
    "ambipower.ambimat.com",
    "ambiautomation.ambimat.com",
    "v2x.ambimat.com",
    "ai.ambimat.com",
    "roboracer.ambimat.com",
    "orders.ambimat.com",
    "esim.ambimat.com",
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


def test_measurement_experiment_stays_retired():
    """RETIRED — OWNER DECISION 2026-09-07.

    The authenticated-measurement experiment (measurement_queue, GA4/GSC service-account
    and Anthropic credentials) was retired. It must not reappear in the repo, and above
    all it must not reappear in the scheduler: while it was wired into the 30-minute
    watchdog it re-emitted a BLOCKED notification every half hour, forever.
    """
    assert not os.path.isdir(os.path.join(ROOT, "measurement_queue")), \
        "measurement_queue/ is back — the measurement experiment was retired 2026-09-07"

    watchdog = os.path.join(ROOT, "reports", "scheduler_verification",
                            "phone_scripts_snapshot", "ensure_scheduler.sh")
    if os.path.exists(watchdog):
        with open(watchdog, encoding="utf-8") as fh:
            body = fh.read()
        assert "measurement" not in body.lower(), \
            "the scheduler watchdog snapshot invokes the retired measurement queue"

    # No live code may ask the owner to install measurement credentials.
    banned = ("ambimat_measure_creds", "google_service_account.json", "anthropic_api_key")
    for sub in ("site_monitor", "cache_monitor", "scripts", "tests", "phone"):
        d = os.path.join(ROOT, sub)
        for dirpath, _, names in os.walk(d):
            if "__pycache__" in dirpath:
                continue
            for name in names:
                fp = os.path.join(dirpath, name)
                if os.path.abspath(fp) == os.path.abspath(__file__):
                    continue          # this guard names the tokens in order to ban them
                try:
                    with open(fp, encoding="utf-8") as fh:
                        text = fh.read().lower()
                except (UnicodeDecodeError, OSError):
                    continue
                for token in banned:
                    assert token not in text, "%s still references retired credential %s" % (fp, token)


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

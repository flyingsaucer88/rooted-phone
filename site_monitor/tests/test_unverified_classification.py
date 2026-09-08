#!/usr/bin/env python3
"""Regression: "unverified" must say WHY, a soft 404 must still be broken, and nothing may
stay unverified for ever.

2026-09-08 — the estate carried 7 unverified external links and every one of them read the
same in the report: an unexplained possible dead link. Checking each one from three different
networks showed they were four different things:

  entrust.com PDF          403 from every network, and a real Chrome gets an explicit
                           "Access Restricted ... blocked due to our security policies" page.
                           A permanent property of the remote. Not broken.
  cloudflare.com,          403 to automated clients, HTTP 200 with the real article in Chrome.
  centralbank.ae           Not broken.
  sanctionscanner.com      Verified 200 from the GoDaddy host. The monitor's connect timeout
                           was the LAN appliance at 192.168.3.1:8888 swallowing it, which says
                           nothing whatever about the remote. Not broken.
  kmu.ac.kr                TLS chain incomplete - the remote omits its intermediate, so strict
                           validators fail where a browser succeeds. Not broken.
  fime.com/whitepaper/...  ACTUALLY DEAD, and invisible to every status check ever run,
  fime.com/america.html    because fime.com answers dead paths with HTTP **200** on /404.

The last pair is the important one: two dead links sat in a "healthy" report indefinitely
because their status code was 200. Reading where the redirect landed is what caught them.

The staleness ledger exists so the other five cannot become permanently trusted. An anti-bot
403 is correctly not-broken today; if that page is deleted tomorrow the 403 looks identical.
So every unverified URL ages, and at the configured threshold a human is asked. Verifying on
any later run drops it from the ledger and restarts the clock - a re-verification schedule,
not an allowlist.
"""
import os
import sys
import types
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in ("requests", "bs4", "yaml"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            _m = types.ModuleType(_name)
            if _name == "requests":
                _m.Session = object
                _m.exceptions = types.SimpleNamespace(RequestException=Exception)
            elif _name == "bs4":
                _m.BeautifulSoup = object
            else:
                _m.safe_load = lambda *a, **k: {}
            sys.modules[_name] = _m

import run_site_monitor as M  # noqa: E402

# The verbatim error strings the phone recorded for the seven, so the classifier is tested
# against what actually came back rather than against a paraphrase.
ERR_APPLIANCE = ("HTTPSConnectionPool(host='www.fime.com', port=443): Max retries exceeded "
                 "with url: /whitepaper/EMVmigration (Caused by ConnectTimeoutError("
                 "<HTTPSConnection(host='www.fime.com', port=443) at 0xa86d92f0>, "
                 "'Connection to www.fime.com timed out. (connect timeout=5)'))")
ERR_TLS = ("HTTPSConnectionPool(host='www.kmu.ac.kr', port=443): Max retries exceeded with "
           "url: / (Caused by SSLError(SSLCertVerificationError(1, '[SSL: "
           "CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer "
           "certificate (_ssl.c:1032)')))")
ERR_READ = ("HTTPSConnectionPool(host='www.businesswire.com', port=443): Read timed out. "
            "(read timeout=10)")

failures = 0


def check(name, got, want):
    global failures
    if got == want:
        print("PASS %s" % name)
    else:
        failures += 1
        print("FAIL %s\n     -> got %r, want %r" % (name, got, want))


# ---------------------------------------------------------------- classification
check("403 -> expected anti-bot", M.classify_unverified(403, None), "unverified-expected-antibot")
check("401 -> expected anti-bot", M.classify_unverified(401, None), "unverified-expected-antibot")
check("429 -> expected anti-bot", M.classify_unverified(429, None), "unverified-expected-antibot")
check("connect timeout -> network blocked (our side, not theirs)",
      M.classify_unverified(None, ERR_APPLIANCE), "unverified-network-blocked")
check("connection refused -> network blocked",
      M.classify_unverified(None, "connect ECONNREFUSED 51.68.49.198:443"),
      "unverified-network-blocked")
check("DNS failure -> network blocked",
      M.classify_unverified(None, "Failed to resolve 'nope.example'"), "unverified-network-blocked")
check("incomplete cert chain -> tls-chain", M.classify_unverified(None, ERR_TLS),
      "unverified-tls-chain")
check("read timeout -> timeout (transient)", M.classify_unverified(None, ERR_READ),
      "unverified-timeout")
check("anything else stays honestly unknown",
      M.classify_unverified(None, "something nobody has seen before"), "unverified-unknown")
check("a classification is never empty", bool(M.classify_unverified(None, None)), True)

# The distinction that matters: none of these may be reported as BROKEN, and none of them
# may be silently dropped either.
for label in ("unverified-expected-antibot", "unverified-network-blocked",
              "unverified-tls-chain", "unverified-timeout", "unverified-unknown"):
    check("%s still starts with 'unverified'" % label, label.startswith("unverified"), True)

# ---------------------------------------------------------------- soft 404
sf = M.SiteCrawler._is_soft_404
check("fime.com/404 is a soft 404", sf("https://www.fime.com/404"), True)
check("trailing slash form too", sf("https://www.fime.com/404/"), True)
check("/not-found", sf("https://x.test/not-found"), True)
check("/page-not-found", sf("https://x.test/page_not_found"), True)
check("/error-404", sf("https://x.test/error-404"), True)
check("a real article at /404-explained/ is NOT swept up",
      sf("https://x.test/404-explained/"), False)
check("a real page is not a soft 404", sf("https://x.test/whitepaper/EMVmigration"), False)
check("a deep path ending in 404 is not matched (anchored)",
      sf("https://x.test/blog/http/404"), False)
check("no final url -> not a soft 404", sf(None), False)


# ---------------------------------------------------------------- staleness ledger
def ledger_run(tmpdir, recs, days_offset, stale_days=30):
    sites = [{"name": "T", "unverified_external_links": recs, "unverified_internal_links": [],
              "warnings": []}]
    today = dt.date(2026, 9, 8) + dt.timedelta(days=days_offset)
    led = M.age_unverified_links(sites, tmpdir, stale_days, today=today)
    M.save_ledger(led, tmpdir)
    return sites[0], led


import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    url = "https://www.entrust.com/brochure.pdf"
    rec = {"url": url, "status": 403, "classification": "unverified-expected-antibot"}
    site, led = ledger_run(tmp, [dict(rec)], 0)
    check("day 0: recorded, no warning", (len(site["warnings"]), led[url]["days_unverified"]),
          (0, 0))

    site, led = ledger_run(tmp, [dict(rec)], 29)
    check("day 29: still no warning", len(site["warnings"]), 0)
    check("  but the age is carried in the report",
          site["unverified_external_links"][0]["days_unverified"], 29)

    site, led = ledger_run(tmp, [dict(rec)], 30)
    check("day 30: a human is asked", len(site["warnings"]), 1)
    check("  the warning names the URL and the classification",
          all(t in site["warnings"][0]["detail"] for t in (url, "30 days",
                                                           "unverified-expected-antibot")), True)
    check("  and the record is flagged stale",
          site["unverified_external_links"][0].get("stale"), True)

with tempfile.TemporaryDirectory() as tmp:
    url = "https://sanctionscanner.com/blog/6-identity-verification-methods-272"
    rec = {"url": url, "status": None, "classification": "unverified-network-blocked"}
    ledger_run(tmp, [dict(rec)], 0)
    ledger_run(tmp, [dict(rec)], 40)          # would warn on the next run
    # It verifies (so it no longer appears in the unverified list at all) -> clock resets.
    site, led = ledger_run(tmp, [], 41)
    check("a link that verifies leaves the ledger", url in led, False)
    site, led = ledger_run(tmp, [dict(rec)], 42)
    check("  and its clock restarts from scratch", led[url]["days_unverified"], 0)
    check("  so it does not immediately warn again", len(site["warnings"]), 0)

with tempfile.TemporaryDirectory() as tmp:
    # The ledger must not be an allowlist: doing nothing cannot clear a stale entry.
    rec = {"url": "https://dead.example/x", "status": 403,
           "classification": "unverified-expected-antibot"}
    ledger_run(tmp, [dict(rec)], 0)
    for offset in (31, 45, 200):
        site, _ = ledger_run(tmp, [dict(rec)], offset)
        check("day %d: still warns (staleness cannot be waited out)" % offset,
              len(site["warnings"]), 1)

print()
print("%s: %d failed" % ("FAILURES" if failures else "all assertions passed", failures))
sys.exit(1 if failures else 0)

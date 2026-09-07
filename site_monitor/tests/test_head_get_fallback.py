#!/usr/bin/env python3
"""Regression: a HEAD-hostile host must not be reported as a broken link.

2026-09-07 — orders.ambimat.com's 15 AddToAny share links were listed as "broken
external links" for weeks. They were never broken: addtoany.com answers HEAD with
403 and GET with 302. Every one of them worked for real visitors. _status_only()
fell back to GET only on 405 and 5xx, so the 403 stood as the verdict.

A link is broken only if it fails the way a visitor would experience it, i.e. on GET.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# run_site_monitor exits at import if `requests` is absent. This test never makes a
# network call — it drives _status_only() with a fake session — so a stub is enough
# and keeps the test runnable on the Mac and in CI, not only on the phone.
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


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def close(self):
        pass


class FakeSession:
    """Mimics a HEAD-hostile host: HEAD -> head_status, GET -> get_status."""

    def __init__(self, head_status, get_status):
        self.head_status = head_status
        self.get_status = get_status
        self.calls = []

    def head(self, url, **kw):
        self.calls.append("HEAD")
        return FakeResponse(self.head_status)

    def get(self, url, **kw):
        self.calls.append("GET")
        return FakeResponse(self.get_status)


def _crawler(session):
    import run_site_monitor
    c = run_site_monitor.SiteCrawler.__new__(run_site_monitor.SiteCrawler)
    c.session = session
    c.timeout = (5, 10)
    c.fail_codes = {400, 401, 403, 404, 410, 429, 500, 502, 503, 504}
    return c


def check(name, got, want):
    if got == want:
        print("PASS %s" % name)
        return 0
    print("FAIL %s\n     -> got %r, want %r" % (name, got, want))
    return 1


def _classify_external(status):
    """Mirror of the external-link branch in check_links()."""
    import run_site_monitor
    fail_codes = {400, 401, 403, 404, 410, 429, 500, 502, 503, 504}
    if status in run_site_monitor.EXTERNAL_BLOCKING_CODES:
        return "unverified"
    if status in fail_codes:
        return "broken"
    return "ok"


def main():
    failures = 0

    # The real AddToAny behaviour: HEAD 403, GET 302 -> not broken.
    s = FakeSession(403, 302)
    st, err = _crawler(s)._status_only("https://www.addtoany.com/add_to/twitter?x=1")
    failures += check("HEAD 403 + GET 302 reports 302, not 403", st, 302)
    failures += check("  and it actually issued the GET", s.calls, ["HEAD", "GET"])

    # A genuinely dead link must still be reported broken.
    s = FakeSession(404, 404)
    st, _ = _crawler(s)._status_only("https://example.com/gone")
    failures += check("HEAD 404 + GET 404 stays 404", st, 404)

    # A host refusing HEAD but also refusing GET is genuinely forbidden.
    s = FakeSession(403, 403)
    st, _ = _crawler(s)._status_only("https://example.com/forbidden")
    failures += check("HEAD 403 + GET 403 stays 403", st, 403)

    # A healthy link costs exactly one request — no extra GET.
    s = FakeSession(200, 200)
    st, _ = _crawler(s)._status_only("https://example.com/ok")
    failures += check("HEAD 200 stays 200", st, 200)
    failures += check("  and no wasteful second request", s.calls, ["HEAD"])

    # 405 Method Not Allowed keeps working as before.
    s = FakeSession(405, 200)
    st, _ = _crawler(s)._status_only("https://example.com/no-head")
    failures += check("HEAD 405 + GET 200 reports 200", st, 200)

    # The fallback must not become a blanket amnesty: a host that refuses HEAD and
    # then 404s the GET is genuinely dead, and GET is the answer that counts.
    s = FakeSession(403, 404)
    st, _ = _crawler(s)._status_only("https://example.com/blocked-then-gone")
    failures += check("HEAD 403 + GET 404 reports 404, not 403", st, 404)
    failures += check("  and 404 is classified broken, not unverified",
                      _classify_external(404), "broken")

    # Same shape for a server error behind a HEAD refusal.
    s = FakeSession(403, 503)
    st, _ = _crawler(s)._status_only("https://example.com/blocked-then-down")
    failures += check("HEAD 403 + GET 503 reports 503", st, 503)
    failures += check("  and 503 is classified broken", _classify_external(503), "broken")

    # A third party refusing bots is not a broken link; a dead page still is.
    failures += check("external 403 -> unverified, not broken", _classify_external(403), "unverified")
    failures += check("external 401 -> unverified", _classify_external(401), "unverified")
    failures += check("external 429 -> unverified", _classify_external(429), "unverified")
    failures += check("external 404 -> still broken", _classify_external(404), "broken")
    failures += check("external 410 -> still broken", _classify_external(410), "broken")
    failures += check("external 503 -> still broken", _classify_external(503), "broken")
    failures += check("external 200 -> ok", _classify_external(200), "ok")

    print("\n%d passed, %d failed" % (18 - failures, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

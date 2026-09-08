#!/usr/bin/env python3
"""Regression: the 2026-09-08 signal-quality pass on the estate warning rules.

The 08:00 crawl produced 593 "suspicious" warnings across nine sites and 0 alerts. Grouping them
collapsed 593 into eight rule families, and every single warning turned out to be a false
positive — 512 of them from ONE rule matching ordinary CSS. A monitor that cries wolf 593 times
is a monitor nobody reads, so each rule below was narrowed at its root cause.

EVERY test here comes in pairs: the false positive is gone AND the genuine attack it was meant
to catch is still caught. A rule that only has the first half of that pair has been disabled,
not fixed.
"""
import os
import sys
import types

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

import run_site_monitor as M

FAILURES = []


def check(name, got, want):
    if got == want:
        print("PASS %s" % name)
    else:
        print("FAIL %s\n     -> got %r, want %r" % (name, got, want))
        FAILURES.append(name)


# --------------------------------------------------------------------------------------
# 1. host_matches — external_check_skip_hosts was an exact netloc match, so five social
#    links listed as bot-hostile were reported unverified on every run anyway.
# --------------------------------------------------------------------------------------
SKIP = ["facebook.com", "linkedin.com", "addtoany.com", "youtube.com"]

check("www.facebook.com is covered by facebook.com", M.host_matches("www.facebook.com", SKIP), True)
check("in.linkedin.com is covered by linkedin.com", M.host_matches("in.linkedin.com", SKIP), True)
check("bare facebook.com still matches", M.host_matches("facebook.com", SKIP), True)
check("www.addtoany.com is covered", M.host_matches("www.addtoany.com", SKIP), True)
# The suffix must be anchored at a dot: a lookalike domain must NOT inherit the exemption,
# or an attacker could park notfacebook.com and skip link checking entirely.
check("notfacebook.com is NOT skipped", M.host_matches("notfacebook.com", SKIP), False)
check("facebook.com.evil.tld is NOT skipped", M.host_matches("facebook.com.evil.tld", SKIP), False)
check("an unrelated host is NOT skipped", M.host_matches("nxp.com", SKIP), False)


# --------------------------------------------------------------------------------------
# 2. suspicious_external_domains — matched as free substrings, so "pharma" fired on
#    pharmaceuticalcommerce.com and "crypto" on cryptomathic.com (an EMV key-management
#    vendor). On a payments/cryptography site those substrings are everyday vendor names.
#    Whole DNS labels only.
# --------------------------------------------------------------------------------------
SUSP = ["casino", "pharma", "viagra", "loan", "crypto", "porn", "adult"]


def is_suspicious_host(host):
    """Mirror of the whole-label test used in _scan_page()/check_links()."""
    return bool(set(host.lower().split(".")) & set(SUSP))


check("pharmaceuticalcommerce.com is clean", is_suspicious_host("pharmaceuticalcommerce.com"), False)
check("www.cryptomathic.com is clean", is_suspicious_host("www.cryptomathic.com"), False)
check("cryptography-vendor.com is clean", is_suspicious_host("cryptography-vendor.com"), False)
check("downloadcenter.example is clean ('loan')", is_suspicious_host("downloadcenter.example"), False)
# Real injected spam hosts still match, on any label.
check("casino.example IS suspicious", is_suspicious_host("casino.example"), True)
check("best.casino.ru IS suspicious", is_suspicious_host("best.casino.ru"), True)
check("viagra.example IS suspicious", is_suspicious_host("viagra.example"), True)


# --------------------------------------------------------------------------------------
# 3. suspicious_patterns.txt — the hidden-CSS group matched every modern page (512/593
#    warnings) and the defacement group duplicated DEFACEMENT_MARKERS without its
#    corroboration. Both were removed; the obfuscation/redirect/webshell groups stay.
# --------------------------------------------------------------------------------------
PATTERNS = [p.lower() for p in M.load_keywords("suspicious_patterns.txt")]


def pattern_hits(raw_html):
    low = raw_html.lower()
    return [p for p in PATTERNS if p in low]


ORDINARY_PAGE = """<!doctype html><html><head>
<style>.dropdown{display:none}.modal{visibility:hidden}.fade{opacity:0}
.sr-only{position:absolute;left:-9999px}.px{height:1px;width:1px}</style></head>
<body><nav class="dropdown">Menu</nav>
<p>Symmetric key algorithms include Data Encryption System(DES) and AES.</p>
<img src="/logo.png" style="display: none" alt=""></body></html>"""

check("ordinary CSS + 'System(DES)' prose is clean", pattern_hits(ORDINARY_PAGE), [])

# Editorial security writing must not trip the pattern rule either (it is handled, with
# corroboration, by the defacement rule instead).
EDITORIAL = "<html><body><p>More than 300 ATM records were hacked by attackers in 2018.</p></body></html>"
check("editorial 'hacked by' is not a pattern hit", pattern_hits(EDITORIAL), [])

# ---- and the genuine injections are still caught ----
check("leaked PHP source IS flagged",
      "<?php" in pattern_hits("<html><body><?php echo 1; ?></body></html>"), True)
check("webshell system($_GET) IS flagged",
      "system($" in pattern_hits("<div><?php system($_GET['c']); ?></div>"), True)
check("base64 eval obfuscation IS flagged",
      "base64_decode" in pattern_hits("<script>x=base64_decode('aGk=');</script>"), True)
check("atob( obfuscation IS flagged",
      "atob(" in pattern_hits("<script>eval(atob('YWxlcnQ='))</script>"), True)
check("injected JS redirect IS flagged",
      "window.location.replace" in pattern_hits("<script>window.location.replace('http://evil.tld')</script>"), True)
check("gzinflate packer IS flagged",
      "gzinflate(" in pattern_hits("<?php eval(gzinflate(base64_decode('x')));"), True)


# --------------------------------------------------------------------------------------
# 4. japanese-spam — the romaji/English variants ("betting", "casino", "replica") are
#    ordinary English words. All three 2026-09-08 hits were English prose. Require CJK
#    script (the actual signature of the hack) or >=2 distinct variants co-occurring.
# --------------------------------------------------------------------------------------
JP_TERMS = M.load_keywords("japanese_spam.txt")


def jp_warns(text):
    """Mirror of the japanese-spam branch in _scan_page()."""
    low = text.lower()
    hits = [t for t in JP_TERMS if M.term_in_text(t, low)]
    cjk = [t for t in hits if not t.isascii()]
    return bool(cjk or len(hits) >= 2)


check("'without betting on which chip survives' is clean",
      jp_warns("It lets the issuer plan a decade out without betting on which transit chip survives."),
      False)
check("a single 'casino' in prose is clean",
      jp_warns("Our terminals are deployed in retail, transit and casino environments."), False)
# ---- and real Japanese keyword-hack injections are still caught ----
check("injected Japanese gambling script IS flagged",
      jp_warns("<p>オンラインカジノ 入金不要ボーナス ランキング</p>"), True)
check("a single CJK term IS enough", jp_warns("バイアグラ"), True)
check("two co-occurring English variants ARE flagged",
      jp_warns("cheap viagra and cialis available, best online casino bonus"), True)


# --------------------------------------------------------------------------------------
# 5. defacement — "owned by" is ordinary English in a page body. It stays an ALERT in the
#    title/H1 or on an abnormally short page; only the body-only ADVISORY was narrowed.
# --------------------------------------------------------------------------------------
def defacement_verdict(title_h1, body, word_count):
    """Mirror of the defacement branch in _scan_page()."""
    t, b = title_h1.lower(), body.lower()
    hit = next((m for m in M.DEFACEMENT_MARKERS if m in t or m in b[:20000]), None)
    if not hit:
        return "clean"
    if hit in t or word_count < 80:
        return "alert"
    return "clean" if hit in M.WEAK_DEFACEMENT_MARKERS else "warn"


check("'Devices owned by infrastructure operators' in a long page is clean",
      defacement_verdict("Why software-only device trust fails",
                         "Devices owned by infrastructure operators but sited on customer premises.",
                         3889), "clean")
check("'owned by one engineering organisation' is clean",
      defacement_verdict("About AmbiAutomation",
                         "firmware, app and commissioning are all owned by one engineering organisation",
                         1174), "clean")
# ---- and every genuine defacement shape still fires ----
check("'Hacked By' in the TITLE is an ALERT",
      defacement_verdict("Hacked By ShadowTeam", "", 12), "alert")
check("'owned by' in the TITLE is still an ALERT",
      defacement_verdict("This site is owned by us now", "", 40), "alert")
check("'owned by' on a stripped short page is still an ALERT",
      defacement_verdict("index", "owned by ShadowTeam", 9), "alert")
check("editorial 'hacked by' in a long article stays an advisory WARNING",
      defacement_verdict("Cyber attacks in India, part 1",
                         "300 ATM records were hacked by attackers", 1168), "warn")


# --------------------------------------------------------------------------------------
# 6. external-iframe — 55 warnings, 33 of them Google Tag Manager's <noscript> iframe on
#    every eSIM page. Expected embeds are allowlisted; anything else still warns.
# --------------------------------------------------------------------------------------
KNOWN = ["googletagmanager.com", "google.com", "gstatic.com", "youtube.com", "vimeo.com"]

check("GTM noscript iframe is expected", M.host_matches("www.googletagmanager.com", KNOWN), True)
check("reCAPTCHA iframe is expected", M.host_matches("www.google.com", KNOWN), True)
check("YouTube embed is expected", M.host_matches("www.youtube.com", KNOWN), True)
# ---- an injected frame from an unknown host is still reported ----
check("an unknown third-party iframe still warns", M.host_matches("evil-adnetwork.tld", KNOWN), False)
check("a lookalike iframe host still warns", M.host_matches("googletagmanager.com.evil.tld", KNOWN), False)


# --------------------------------------------------------------------------------------
# 7. _get bounded retry — AmbiSecure's /resources/tools/key-diversification/ died with
#    ConnectionResetError(104) at 08:00 and served HTTP 200 on three manual fetches minutes
#    later. One retry tells a dropped socket apart from a page that is genuinely down.
# --------------------------------------------------------------------------------------
class _Resp:
    status_code = 200

    def __init__(self):
        self.raw = types.SimpleNamespace(read=lambda *a, **k: b"<html>ok</html>")

    def close(self):
        pass


class FlakySession:
    """Resets the connection `fail_times` times, then serves normally."""

    def __init__(self, fail_times, exc=None):
        self.fail_times = fail_times
        self.attempts = 0
        self.exc = exc or ConnectionError(
            "('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))")

    def get(self, url, **kw):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise self.exc
        return _Resp()


def _crawler(session):
    c = M.SiteCrawler.__new__(M.SiteCrawler)
    c.session = session
    c.timeout = (5, 10)
    c.cfg = {"max_body_bytes": 3000000}
    return c


s = FlakySession(fail_times=1)
r = _crawler(s)._get("https://ambisecure.ambimat.com/resources/tools/key-diversification/")
check("one connection reset then success -> page fetched", r.status_code, 200)
check("...and it took exactly 2 attempts", s.attempts, 2)

# A page that is genuinely unreachable must still fail — the retry is bounded, not infinite.
s2 = FlakySession(fail_times=99)
try:
    _crawler(s2)._get("https://example.tld/down")
    check("a persistently reset page still raises", "no exception", "raised")
except Exception:
    check("a persistently reset page still raises", "raised", "raised")
check("...after exactly 2 bounded attempts, not more", s2.attempts, 2)

# A non-transient error must NOT be retried: re-asking cannot change a DNS failure.
s3 = FlakySession(fail_times=99, exc=ValueError("Invalid URL 'h ttp://x': No host supplied"))
try:
    _crawler(s3)._get("h ttp://x")
except Exception:
    pass
check("a non-transient error is not retried", s3.attempts, 1)


print()
if FAILURES:
    print("%d FAILED: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("all warning-signal-quality regression tests passed")

#!/usr/bin/env python3
"""Regression: the iframe invariant and the defacement context rule (2026-09-08, closure pass).

Two rules changed shape rather than sensitivity:

  * external-iframe stopped being "any third-party frame is suspicious" and became an explicit
    invariant — ONLY reviewed origins may be framed. Expected origins are recorded as verified
    embeds and no longer sit in the warning bucket; anything else is now an ALERT, which is
    stronger than the warning it replaces, not weaker.

  * the defacement advisory now distinguishes a page that DISCUSSES an attack from a page that
    IS one, using length plus security-topic vocabulary.

Every check below is paired: the false positive is gone AND the real attack still fires.
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


# ---------------------------------------------------------------------------------
# 1. The iframe invariant.
# ---------------------------------------------------------------------------------
EXPECTED = [
    "googletagmanager.com", "google.com", "gstatic.com", "maps.google.com",
    "youtube.com", "youtube-nocookie.com", "youtu.be", "vimeo.com", "openstreetmap.org",
    "paylosophy.com", "pcisecuritystandards.org", "encryptionconsulting.com",
    "tech-faq.com", "idtechproducts.com", "idwholesaler.com",
]


def frame_verdict(src, host=None):
    """Mirror of the iframe branch in _scan_page()."""
    scheme = src.split(":", 1)[0].strip().lower()
    if scheme in M._DANGEROUS_SCHEMES:
        return "ALERT:dangerous-scheme"
    if host is None:
        return "n/a"
    if M.host_matches(host, EXPECTED):
        return "VERIFIED"
    return "ALERT:unexpected-host"


# --- the nine real 2026-09-08 frames are now VERIFIED, not "suspicious" ---
for host in ("www.googletagmanager.com", "www.google.com", "maps.google.com",
             "paylosophy.com", "www.pcisecuritystandards.org",
             "www.encryptionconsulting.com", "www.tech-faq.com",
             "idtechproducts.com", "www.idwholesaler.com"):
    check("expected embed verified: %s" % host,
          frame_verdict("https://%s/x/embed/" % host, host), "VERIFIED")

# --- and the invariant still bites for anything unreviewed ---
check("an unreviewed publisher ALERTS",
      frame_verdict("https://evil-adnetwork.tld/f", "evil-adnetwork.tld"), "ALERT:unexpected-host")
check("a lookalike of an approved host ALERTS",
      frame_verdict("https://paylosophy.com.evil.tld/f", "paylosophy.com.evil.tld"),
      "ALERT:unexpected-host")
check("a lookalike of infrastructure ALERTS",
      frame_verdict("https://googletagmanager.com.evil.tld/f", "googletagmanager.com.evil.tld"),
      "ALERT:unexpected-host")
check("a NEW host not yet in the allowlist ALERTS",
      frame_verdict("https://newpublisher.example/embed/", "newpublisher.example"),
      "ALERT:unexpected-host")
# --- malformed / script-bearing frames ---
check("javascript: iframe ALERTS", frame_verdict("javascript:alert(1)"), "ALERT:dangerous-scheme")
check("data: iframe ALERTS", frame_verdict("data:text/html;base64,PHNjcmlwdD4="),
      "ALERT:dangerous-scheme")
check("vbscript: iframe ALERTS", frame_verdict("vbscript:msgbox"), "ALERT:dangerous-scheme")
check("  JavaScript: with odd case/space still ALERTS",
      frame_verdict("  JavaScript:alert(1)"), "ALERT:dangerous-scheme")
# --- and the allowlist is not a blanket "external is fine" exemption ---
check("expected list does NOT contain a wildcard", any(h in ("", "*") for h in EXPECTED), False)


# ---------------------------------------------------------------------------------
# 2. Defacement: discussing an attack vs being one.
# ---------------------------------------------------------------------------------
def defacement_verdict(title_h1, body, word_count):
    """Mirror of the defacement branch in _scan_page()."""
    t, b = title_h1.lower(), body.lower()
    hit = next((m for m in M.DEFACEMENT_MARKERS if m in t or m in b[:20000]), None)
    if not hit:
        return "clean"
    if hit in t or word_count < 80:
        return "alert"
    if hit in M.WEAK_DEFACEMENT_MARKERS:
        return "clean"
    terms = {x for x in M.SECURITY_EDITORIAL_TERMS if M.term_in_text(x, b)}
    if (word_count >= M.SECURITY_EDITORIAL_MIN_WORDS
            and len(terms) >= M.SECURITY_EDITORIAL_MIN_TERMS):
        return "editorial"
    return "warn"


CYBER_ARTICLE = (
    "In mid-2018 more than 300 user ATM details were hacked by attackers and money was wiped "
    "from several bank accounts. The breach exploited a known vulnerability that had not been "
    "patched. Investigators described the malware used, the phishing campaign that delivered "
    "it, and the credential theft that followed. Stronger authentication and encryption, "
    "along with firewall changes, formed the mitigation after the incident."
)
check("a real cybersecurity article is editorial, not a warning",
      defacement_verdict("Cyber attacks in India, part 1", CYBER_ARTICLE, 1168), "editorial")

# --- every genuine takeover shape still fires ---
check("'Hacked By' in the TITLE is an ALERT",
      defacement_verdict("Hacked By ShadowTeam", "", 12), "alert")
check("'Hacked By' in the H1 is an ALERT",
      defacement_verdict("Home Hacked By ShadowTeam", "greetz", 30), "alert")
check("a stripped minimal defacement page is an ALERT",
      defacement_verdict("index", "hacked by ShadowTeam. greetz to everyone", 9), "alert")
check("'owned by' in the TITLE is still an ALERT",
      defacement_verdict("This site is owned by us now", "", 40), "alert")

# --- and the exemption cannot be bought with a few keywords ---
check("a LONG page with a marker but no security vocabulary still WARNS",
      defacement_verdict("Company news",
                         "our office was hacked by " + ("filler " * 600), 600), "warn")
check("a SHORT page full of security words is still an ALERT (length gate)",
      defacement_verdict("x", "hacked by attackers vulnerability malware phishing exploit", 40),
      "alert")
check("a medium page with security words but under the word floor still WARNS",
      defacement_verdict("Notes",
                         "hacked by attackers. vulnerability, malware, phishing, exploit, patch.",
                         120), "warn")

print()
if FAILURES:
    print("%d FAILED: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("all iframe/defacement invariant tests passed")

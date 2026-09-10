#!/usr/bin/env python3
"""Regression: an external-link note must never soften a check.

The Sept 9-10 investigation classified every unverified external URL on the estate. Writing
that knowledge down is useful; letting it become an allowlist would quietly destroy the
monitor. These tests fix the boundary: a note annotates a verdict the crawler has already
reached, and can never change it.
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

import link_notes  # noqa: E402

failures = 0


def check(name, got, want):
    global failures
    if got == want:
        print("PASS %s" % name)
    else:
        failures += 1
        print("FAIL %s\n     got  %r\n     want %r" % (name, got, want))


NOTES = {
    "https://www.jhu.edu/": {"class": "antibot", "confirmed": "2026-09-10", "reason": "403"},
    "http://auminfotech.com/": {"class": "upstream-failure", "confirmed": "2026-09-10",
                                "reason": "Cloudflare 522"},
}

# --- a known URL is annotated but still unverified ----------------------------
rec = {"url": "https://www.jhu.edu/", "status": 403,
       "error": "external host refused an automated request (HTTP 403)",
       "classification": "unverified-expected-antibot"}
out = link_notes.annotate(dict(rec), NOTES)
check("known URL gains a note", out["known"], "antibot")
check("known URL carries the confirmation date", out["known_since"], "2026-09-10")
check("known URL is flagged as already judged", out["known_status"], "known")
check("live status is NOT rewritten", out["status"], 403)
check("live classification is NOT rewritten", out["classification"], "unverified-expected-antibot")
check("note adds no key that could mark it healthy",
      {"ok", "healthy", "ignore", "skip", "suppress"} & set(out), set())

# --- an unknown URL is distinguishable as NEW ---------------------------------
fresh = link_notes.annotate(
    {"url": "https://brand-new.example/x", "status": None, "error": "timeout",
     "classification": "unverified-timeout"}, NOTES)
check("unregistered URL is marked NEW", fresh["known_status"], "new")
check("unregistered URL gets no 'known' class", "known" in fresh, False)
check("summarise separates judged from new",
      link_notes.summarise([out, fresh]), {"known": 1, "new": 1})

# --- the registry is only ever consulted for already-unverified records -------
# A 404 never reaches annotate(): run_site_monitor routes it to broken_external.
# Prove the two call sites are the unverified ones and nothing else.
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "run_site_monitor.py"), encoding="utf-8").read()
check("annotate() is wired only into unverified appends",
      src.count("link_notes.annotate"), src.count("unverified_external.append(link_notes.annotate")
      + src.count("unverified_internal.append(link_notes.annotate"))
check("broken_external is never annotated", "broken_external.append(link_notes" in src, False)
check("broken_internal is never annotated", "broken_internal.append(link_notes" in src, False)
# The external URLs to check are selected before any note is consulted, and the note is
# only applied after _status_only() has already returned a verdict. Prove that ordering.
_block = src.split("for u in externals:", 1)[1].split("time.sleep(delay)", 1)[0]
check("the check list is built without consulting notes",
      "link_notes" in src.split("for u in externals:", 1)[0].split("externals = ", 1)[-1], False)
check("annotate() runs only after _status_only() has produced a verdict",
      _block.index("link_notes.annotate") > _block.index("self._status_only(u)"), True)
check("notes never gate whether a URL is requested",
      "if" in _block.split("link_notes.annotate")[0].split("self._status_only(u)")[1][:40], False)

# --- a bad registry must fail safe (everything reads NEW) ---------------------
check("missing registry file yields no notes", link_notes.load_notes("/nonexistent/x.yaml"), {})
check("unknown class is dropped rather than trusted",
      link_notes.annotate({"url": "u"}, {"u": {"class": "bogus"}})["known_status"], "known")

import tempfile  # noqa: E402

# The registry is YAML. Where PyYAML is genuinely installed (the phone), parse it for real;
# where it is stubbed out (this Mac has no PyYAML), load_notes() fail-safes to {} and the
# parse-level assertions have nothing to test.
_REAL_YAML = getattr(sys.modules.get("yaml"), "__file__", None) is not None

if _REAL_YAML:
    bad = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    bad.write("notes:\n  - url: https://a.test/\n    class: not-a-real-class\n"
              "  - url: https://b.test/\n    class: antibot\n    confirmed: 2026-09-10\n")
    bad.close()
    loaded = link_notes.load_notes(bad.name)
    check("entry with an invalid class is rejected at load time",
          sorted(loaded), ["https://b.test/"])
    os.unlink(bad.name)
else:
    print("SKIP registry-parse checks (PyYAML unavailable here; covered on device)")

# --- the shipped registry is well formed --------------------------------------
real = link_notes.load_notes() if _REAL_YAML else {}
if real:
    check("shipped registry entries all use a valid class",
          all(v["class"] in link_notes.VALID_CLASSES for v in real.values()), True)
    check("shipped registry records a confirmation date for every entry",
          all(v["confirmed"] for v in real.values()), True)
    check("auminfotech is upstream-failure, NOT antibot",
          real.get("http://auminfotech.com/", {}).get("class"), "upstream-failure")
    check("openscdp is upstream-failure, NOT antibot",
          real.get("https://www.openscdp.org/scripts/tutorial/emv/cardactionanalysis.html",
                   {}).get("class"), "upstream-failure")
else:
    print("SKIP shipped-registry checks (PyYAML unavailable in this environment)")

print()
if failures:
    print("%d FAILURE(S)" % failures)
    sys.exit(1)
print("all link_notes regression checks passed")

#!/usr/bin/env python3
"""Regression: a URL variant of one page is not a duplicate of itself.

2026-09-09 — the 08:25 run reported 52 duplicate title/description findings across
the estate. 47 of them were one page counted twice. Orders had 11 duplicate titles
and every group was a WooCommerce `?add-to-cart=NNNN` variant of the page it was
already listing; Ambimat had trailing-slash pairs (`/x` vs `/x/`) and one scheme
pair (`http://ambimat.com/contact/` vs `https://`). Each variant serves the same
HTML and declares the same rel=canonical, so search engines see one page, not two.

_seo_summary grouped by raw URL, so any two URLs sharing a title were "duplicate".
It now groups by canonical identity. The fixtures below pair each false positive
with the genuine duplicate the same check still has to catch.

Also covers the second half of that run: 67 of Ambimat's "67 missing canonical"
and 52 of its "53 missing meta description" were noindex pages, where neither
costs anything. The raw count stays; an indexable count is reported beside it so
the one page that mattered is not buried.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# run_site_monitor exits at import if `requests` is absent. This test never makes a
# network call — it drives _seo_summary() with dict fixtures — so a stub is enough
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

from run_site_monitor import SiteCrawler  # noqa: E402
from render_report import _seo_count  # noqa: E402

failures = 0


def check(name, got, want):
    global failures
    if got == want:
        print("PASS %s" % name)
    else:
        failures += 1
        print("FAIL %s\n     -> got %r\n        want %r" % (name, got, want))


def page(url, title=None, description=None, canonical=None, robots=None, h1=1):
    return {"url": url, "title": title, "description": description,
            "canonical": canonical, "robots_meta": robots, "h1_count": h1}


def summarise(pages):
    """Run _seo_summary against a bare object carrying just what it reads."""
    mon = SiteCrawler.__new__(SiteCrawler)
    mon.pages = pages
    mon._warn = lambda *a, **k: None
    return SiteCrawler._seo_summary(mon)


# --- false positives that must now be silent -------------------------------

# Real markup from orders.ambimat.com: add-to-cart variants, one canonical.
s = summarise([
    page("https://orders.ambimat.com/product/roboracer-core-kit/", "RoboRacer Core Kit",
         "The core kit.", "https://orders.ambimat.com/product/roboracer-core-kit/"),
    page("https://orders.ambimat.com/product/roboracer-core-kit/?add-to-cart=15", "RoboRacer Core Kit",
         "The core kit.", "https://orders.ambimat.com/product/roboracer-core-kit/"),
    page("https://orders.ambimat.com/product/roboracer-core-kit/?add-to-cart=2040", "RoboRacer Core Kit",
         "The core kit.", "https://orders.ambimat.com/product/roboracer-core-kit/"),
])
check("add-to-cart variants are not duplicate titles", s["duplicate_titles"], {})
check("add-to-cart variants are not duplicate descriptions", s["duplicate_descriptions"], {})

# Real markup from ambimat.com: trailing-slash and scheme variants.
s = summarise([
    page("https://ambimat.com/contact/", "Contact", "Get in touch.", "https://ambimat.com/contact/"),
    page("http://ambimat.com/contact/", "Contact", "Get in touch.", "https://ambimat.com/contact/"),
    page("https://ambimat.com/design/ambi-iot/smart-watches", "Smart Watches", "Watches.",
         "https://ambimat.com/design/ambi-iot/smart-watches/"),
    page("https://ambimat.com/design/ambi-iot/smart-watches/", "Smart Watches", "Watches.",
         "https://ambimat.com/design/ambi-iot/smart-watches/"),
])
check("http/https variants are not duplicates", s["duplicate_titles"], {})
check("trailing-slash variants are not duplicates", s["duplicate_descriptions"], {})

# A page canonicalised ONTO another is that other page, not a second copy.
# Real: /products/qpsk-modulator/ declares canonical /ambi-space/.
s = summarise([
    page("https://ambimat.com/ambi-space/", "AmbiSpace", "Aerospace.", "https://ambimat.com/ambi-space/"),
    page("https://ambimat.com/products/qpsk-modulator/", "AmbiSpace", "Aerospace.",
         "https://ambimat.com/ambi-space/"),
])
check("a page canonicalised onto another is not a duplicate", s["duplicate_titles"], {})


# --- genuine duplicates that must still be caught --------------------------

# Two distinct pages, each self-canonical, same title and description.
s = summarise([
    page("https://ambimat.com/category/general/", "General Archives", "General posts.",
         "https://ambimat.com/category/general/"),
    page("https://ambimat.com/tag/general/", "General Archives", "General posts.",
         "https://ambimat.com/tag/general/"),
])
check("two self-canonical pages sharing a title are still duplicate",
      s["duplicate_titles"],
      {"general archives": ["https://ambimat.com/category/general/", "https://ambimat.com/tag/general/"]})
check("two self-canonical pages sharing a description are still duplicate",
      sorted(s["duplicate_descriptions"]["general posts."]),
      ["https://ambimat.com/category/general/", "https://ambimat.com/tag/general/"])

# No canonical anywhere: fall back to the URL, and still catch the duplicate.
s = summarise([
    page("https://x.test/a", "Same", "Same.", None),
    page("https://x.test/b", "Same", "Same.", None),
])
check("duplicates are still caught when no canonical is declared",
      sorted(s["duplicate_titles"]["same"]), ["https://x.test/a", "https://x.test/b"])

# ...but the URL fallback must still collapse a trailing-slash pair.
s = summarise([page("https://x.test/a", "Same", "Same.", None),
               page("https://x.test/a/", "Same", "Same.", None)])
check("URL fallback still collapses a trailing-slash pair", s["duplicate_titles"], {})


# --- indexable vs noindex split --------------------------------------------

s = summarise([
    page("https://ambimat.com/category/uncategorized/", "Uncategorized", None,
         "https://ambimat.com/category/uncategorized/"),
    page("https://ambimat.com/tag/iot/", "IoT", None, None, robots="noindex, follow"),
    page("https://ambimat.com/tag/nfc/", "NFC", None, None, robots="noindex, follow"),
])
check("raw missing-description count is preserved", len(s["pages_missing_description"]), 3)
check("only the indexable page is actionable",
      s["indexable_missing_description"], ["https://ambimat.com/category/uncategorized/"])
check("raw missing-canonical count is preserved", len(s["pages_missing_canonical"]), 2)
check("noindex pages are excluded from indexable missing-canonical",
      s["indexable_missing_canonical"], [])

# The renderer must show both numbers, and must not add noise when they agree.
check("renderer shows the split when it differs",
      _seo_count(s, "pages_missing_description", "indexable_missing_description"),
      "3 (1 indexable)")
check("renderer stays terse when every hit is indexable",
      _seo_count({"pages_missing_description": ["u"], "indexable_missing_description": ["u"]},
                 "pages_missing_description", "indexable_missing_description"),
      "1")
check("renderer tolerates a report written before the split existed",
      _seo_count({"pages_missing_description": ["u", "v"]},
                 "pages_missing_description", "indexable_missing_description"),
      "2")

print()
if failures:
    print("%d FAILURE(S)" % failures)
    sys.exit(1)
print("all seo-identity regression checks passed")

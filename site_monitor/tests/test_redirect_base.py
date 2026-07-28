"""Regression test for the cross-domain-redirect relative-URL bug.

Reproduces the 2026-07-28 finding: ambimat.com/design/design-services/java-card-applet/
301s to ambisecure.ambimat.com/services/javacard-development/, whose root-relative hrefs
were being joined onto ambimat.com and reported as 22 phantom broken pages.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from run_site_monitor import SiteCrawler

KW = {"japanese": [], "spam": [], "patterns": []}
CRAWL = {"user_agent": "test"}
ALERTS = {"fail_on_status_codes": [404], "suspicious_external_domains": [],
          "external_check_skip_hosts": []}


class Resp:
    def __init__(self, text, url, status=200):
        self.text, self.url, self.status_code = text, url, status
        self.headers = {"Content-Type": "text/html"}


def crawler():
    return SiteCrawler({"name": "Ambimat", "base_url": "https://ambimat.com"},
                       CRAWL, ALERTS, [], KW, {})


def test_offsite_redirect_resolves_against_final_url():
    html = """<html><head><title>JavaCard Applet Development | AmbiSecure</title>
    <link rel="canonical" href="https://ambisecure.ambimat.com/services/javacard-development/">
    </head><body>
    <a href="/products/">Products</a>
    <a href="/services/fido-validation-server/">FIDO</a>
    <a href="/industries/smart-cities/">Smart Cities</a>
    </body></html>"""
    requested = "https://ambimat.com/design/design-services/java-card-applet/"
    landed = "https://ambisecure.ambimat.com/services/javacard-development/"

    c = crawler()
    c._analyze(requested, Resp(html, landed))

    phantom = [u for u in c.internal_links if u.startswith("https://ambimat.com/products")
               or u.startswith("https://ambimat.com/services")
               or u.startswith("https://ambimat.com/industries")]
    assert not phantom, f"phantom ambimat.com paths invented: {phantom}"

    resolved = sorted(c.external_links)
    for expected in ("https://ambisecure.ambimat.com/products/",
                     "https://ambisecure.ambimat.com/services/fido-validation-server/",
                     "https://ambisecure.ambimat.com/industries/smart-cities/"):
        assert expected in resolved, f"missing {expected} in {resolved}"

    assert any(w["type"] == "offsite-redirect" for w in c.warnings), \
        "off-host redirect was not surfaced as a warning"
    print("PASS offsite redirect resolves against final URL")


def test_normal_page_unaffected():
    html = '<html><head><title>T</title></head><body><a href="/about/">About</a></body></html>'
    u = "https://ambimat.com/some/page/"
    c = crawler()
    c._analyze(u, Resp(html, u))
    assert "https://ambimat.com/about/" in c.internal_links, c.internal_links
    assert not [w for w in c.warnings if w["type"] == "offsite-redirect"]
    print("PASS non-redirected page unchanged")


def test_base_href_honoured():
    html = ('<html><head><title>T</title><base href="https://ambimat.com/sub/">'
            '</head><body><a href="x/">X</a></body></html>')
    u = "https://ambimat.com/some/page/"
    c = crawler()
    c._analyze(u, Resp(html, u))
    assert "https://ambimat.com/sub/x/" in c.internal_links, c.internal_links
    print("PASS <base href> honoured")


def test_same_host_redirect_no_warning():
    html = '<html><head><title>T</title></head><body><a href="/a/">A</a></body></html>'
    c = crawler()
    c._analyze("https://ambimat.com/old/", Resp(html, "https://ambimat.com/new/"))
    assert not [w for w in c.warnings if w["type"] == "offsite-redirect"], c.warnings
    assert "https://ambimat.com/a/" in c.internal_links
    print("PASS same-host redirect produces no warning")


for fn in (test_offsite_redirect_resolves_against_final_url, test_normal_page_unaffected,
           test_base_href_honoured, test_same_host_redirect_no_warning):
    fn()
print("\nall tests passed")

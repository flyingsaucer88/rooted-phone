#!/usr/bin/env python3
"""Orders CSP, step 1 of 2 — ship a Report-Only policy derived from Orders' own runtime.

This policy is NOT ambimat.com's with the hostnames changed. Orders is a different application:
Astra + Elementor + WooCommerce with three live payment gateways, no consent tooling at all,
and a /contact/ page that pulls its assets from ambimat.com. Its dependency set was enumerated
from scratch — a 53-page static sweep plus a real browser walk of home, a purchasable product,
cart, checkout (all three gateways selected), /contact/, /my-account/ and search.

WHAT WAS FOUND, AND WHERE

  orders.ambimat.com    'self'          everything
  fonts.googleapis.com  style-src       Google Fonts stylesheet, 53/53 pages
  fonts.gstatic.com     font-src        the faces that stylesheet pulls
  static.addtoany.com   script, frame   the AddToAny share widget (script + iframe)
  www.googletagmanager.com  script, connect   GA4 gtag
  analytics.google.com  connect-src     GA4 /g/collect. Listed as the BARE host on purpose:
                                        `*.analytics.google.com` does NOT match it, which is
                                        exactly the defect found on ambimat.com.
  www.google-analytics.com script, connect   GA4's other endpoint, seen on /contact/
  www.google.co.in      img-src         Google Ads remarketing pixel
  pagead2.googlesyndication.com  script  the ad tag, /contact/ only
  ambimat.com           script, style, img   /contact/ loads Contact Form 7, block-library and
                                        theme CSS/JS straight from ambimat.com, and
                                        /electronic-manufacturing/ hotlinks one image
  www.paypal.com        script, connect  PayPal Commerce SDK, on product/cart/checkout
  c.paypal.com          script, frame    PayPal's own frame
  c6.paypal.com         img-src          PayPal
  s.w.org               img-src          WordPress emoji/SVG

NO CONSENT GATE EXISTS. Orders has no CookieYes or any other consent plugin (checked the active
plugin list and the runtime: zero `consent` entries in dataLayer), so GA4 fires unconditionally
and there is no accept/reject path to exercise here. That is a pre-existing finding about this
host, not something this policy changes.

form-action: 'self' plus the gateway hosts the gateway plugins name in their own source.
Juspay and PayGlocal both hand off with wp_redirect() — a 302, which CSP does not govern — so
in principle 'self' alone would do. The hosts are listed anyway because the payment hand-off is
the one step this campaign is not permitted to exercise, and being wrong there breaks revenue.

DELIBERATELY NOT INCLUDED YET
  'unsafe-eval'   no evidence anything needs it. If Elementor or a gateway bundle does, this
                  Report-Only pass will say so, with the script that wanted it.
  worker-src      nothing observed spawning a worker; default-src covers it if something does.
  paypalobjects / t.paypal.com  plausible for PayPal but NOT observed. Guessing them in would
                  defeat the point of a Report-Only pass.

upgrade-insecure-requests is carried over deliberately: it is currently the ONLY CSP this host
sends (Hostinger's default), and a `Header always set Content-Security-Policy` would otherwise
replace it and quietly lose it.
"""
import hashlib, os, shutil, sys, time

HT = "/home/u675763961/domains/orders.ambimat.com/public_html/.htaccess"
BAK = HT + ".pre-cspro-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

POLICY = " ".join([
    "default-src 'self';",
    "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com",
    "https://www.google-analytics.com https://pagead2.googlesyndication.com",
    "https://static.addtoany.com https://www.paypal.com https://c.paypal.com",
    "https://ambimat.com;",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://ambimat.com;",
    "font-src 'self' data: https://fonts.gstatic.com;",
    "img-src 'self' data: blob: https://www.google-analytics.com https://www.googletagmanager.com",
    "https://www.google.co.in https://c6.paypal.com https://static.addtoany.com",
    "https://s.w.org https://ambimat.com https://i0.wp.com;",
    "connect-src 'self' https://www.google-analytics.com https://analytics.google.com",
    "https://*.analytics.google.com https://*.googletagmanager.com",
    "https://stats.g.doubleclick.net https://www.paypal.com;",
    "frame-src 'self' https://static.addtoany.com https://www.paypal.com https://c.paypal.com;",
    "frame-ancestors 'self'; base-uri 'self'; object-src 'none';",
    "form-action 'self' https://www.paypal.com https://juspay.in https://*.juspay.in",
    "https://payglocal.in https://*.payglocal.in;",
    "upgrade-insecure-requests",
])

MARK_START = "# --- ambimat CSP (report-only) ------------------------------------------------\n"
BLOCK = (
    MARK_START +
    "# Derived from Orders' own runtime, not copied from ambimat.com. See the deploy script\n"
    "# for where every origin below was observed. Report-Only changes nothing about what\n"
    "# loads; it only reports what an enforcing policy WOULD block.\n"
    "<IfModule mod_headers.c>\n"
    "  Header onsuccess unset Content-Security-Policy-Report-Only\n"
    "  Header always unset Content-Security-Policy-Report-Only\n"
    '  Header always set Content-Security-Policy-Report-Only "' + POLICY + '"\n'
    "</IfModule>\n"
    "# --- end ambimat CSP ---------------------------------------------------------\n"
)

ANCHOR = "# --- end security headers ----------------------------------------------------"

src = open(HT, encoding="utf-8").read()
if "ambimat CSP" in src:
    print("ABORT: an ambimat CSP block is already present")
    sys.exit(1)
if src.count(ANCHOR) != 1:
    print("ABORT: expected exactly one security-header end marker, found %d" % src.count(ANCHOR))
    sys.exit(1)

out = src.replace(ANCHOR, ANCHOR + "\n\n" + BLOCK, 1)
before = hashlib.sha256(src.encode("utf-8")).hexdigest()
shutil.copy2(HT, BAK)
if hashlib.sha256(open(BAK, "rb").read()).hexdigest() != before:
    print("ABORT: backup mismatch")
    sys.exit(1)
open(HT, "w", encoding="utf-8").write(out)
print("ORDERS CSP REPORT-ONLY APPLIED")
print("  .htaccess %s -> %s" % (before[:12], hashlib.sha256(open(HT, "rb").read()).hexdigest()[:12]))
print("  backup    %s" % os.path.basename(BAK))

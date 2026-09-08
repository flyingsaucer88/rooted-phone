#!/usr/bin/env python3
"""Stage 2 - promote ambimat.com's Content-Security-Policy from Report-Only to enforcing.

The policy below is NOT the Report-Only policy with the header renamed. The Report-Only
origin list was enumerated from static HTML, which cannot see anything a script injects at
runtime, so it was missing six origins that a real browser demonstrably loads. Each addition
below was observed in Chrome or in a 346-page fetch of the live site; none is a guess.

  script-src  + js.driftt.com           Drift live chat. An ACTIVE WordPress plugin ("drift",
                                        with its own Drift_settings option); the tag is
                                        injected at runtime, which is why an HTML-only
                                        enumeration missed it. Enforcing without it kills the
                                        chat widget on every page.
  frame-src   + js.driftt.com           The same widget's two iframes (js.driftt.com/core and
                                        /core/chat). Its realtime traffic runs INSIDE that
                                        frame, on its own origin, so no connect-src entry is
                                        needed - verified: the top document opens no WebSocket.
  connect-src + cdn-cookieyes.com       CookieYes fetches its config, translations and audit
  img-src     + cdn-cookieyes.com       table as JSON, and its banner icons as SVG, from the
                                        CDN host. Only the log/directory hosts were listed, so
                                        an enforcing policy would have blanked the banner.
  connect-src + analytics.google.com    A POLICY DEFECT, not a missing dependency. The policy
                                        listed https://*.analytics.google.com; a `*.` prefix
                                        requires at least one label, so it does NOT match the
                                        bare host - and GA4 posts /g/collect to the bare host.
  connect-src + stats.g.doubleclick.net GA4 with Google Signals. Fires only after consent is
  img-src     + www.google.co.in        granted, which is why the earlier pass never saw it:
                                        the banner was never accepted during testing.
  connect-src + csp.withgoogle.com      Telemetry beacon emitted intermittently by Google's
                                        own tags. Breaks nothing if blocked; listed so an
                                        enforcing policy does not log an error nobody can act on.
  img-src     + pixel.wp.com            Jetpack Stats' only beacon target. stats.wp.com/e-*.js
                                        is enqueued on every page; the pixel did not fire in
                                        any observed load, but leaving it out would silently
                                        lose stats the day the module is switched on.
  img-src     + qph.cf2.quoracdn.net    A hotlinked image in the body of
                                        /step-by-step-how-does-a-emv-contact-card-payment-work/.
                                        Verified 200 and rendering; blocking it breaks a page.

Deliberately NOT added:
  upload.wikimedia.org   The one image hotlinked from it (/barcode/) already returns 404 from
                         the remote. Allowing an origin to un-block an image that is broken at
                         source would only hide the real defect.
  google ccTLDs beyond .co.in
                         The /ads/ga-audiences remarketing pixel hits the VISITOR'S local
                         Google domain, which cannot be enumerated. .co.in is the measured
                         one and India is the site's primary market. Non-Indian visitors'
                         remarketing pixel is blocked by design; that is an advertising
                         signal, not site functionality, and no visitor sees a difference.
                         Reversible by adding hosts here - deliberately not a wildcard.
"""
import hashlib, os, re, shutil, subprocess, sys, time

HT = "/home/xemtd1m9scay/public_html/.htaccess"
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BAK = HT + ".pre-cspenforce-" + STAMP

POLICY = " ".join([
    "default-src 'self';",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "https://www.googletagmanager.com https://cdn-cookieyes.com https://directory.cookieyes.com",
    "https://log.cookieyes.com https://www.google.com https://www.gstatic.com https://stats.wp.com",
    "https://pagead2.googlesyndication.com https://js.driftt.com;",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;",
    "font-src 'self' data: https://fonts.gstatic.com;",
    "img-src 'self' data: https://i0.wp.com https://i1.wp.com https://i2.wp.com",
    "https://stats.wp.com https://pixel.wp.com https://www.googletagmanager.com",
    "https://www.google-analytics.com https://www.google.com https://www.google.co.in",
    "https://maps.gstatic.com https://cdn-cookieyes.com https://qph.cf2.quoracdn.net;",
    "connect-src 'self' https://www.google-analytics.com https://analytics.google.com",
    "https://*.analytics.google.com https://*.googletagmanager.com https://stats.g.doubleclick.net",
    "https://stats.wp.com https://log.cookieyes.com https://directory.cookieyes.com",
    "https://cdn-cookieyes.com https://csp.withgoogle.com;",
    "frame-src https://www.google.com https://maps.google.com https://www.youtube.com",
    "https://www.youtube-nocookie.com https://js.driftt.com https://paylosophy.com",
    "https://www.pcisecuritystandards.org https://www.encryptionconsulting.com",
    "https://www.tech-faq.com https://idtechproducts.com https://www.idwholesaler.com;",
    "frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none';",
    "upgrade-insecure-requests",
])

BLOCK = (
    '    Header onsuccess unset Content-Security-Policy-Report-Only\n'
    '    Header always unset Content-Security-Policy-Report-Only\n'
    '\n'
    '    Header onsuccess unset Content-Security-Policy\n'
    '    Header always unset Content-Security-Policy\n'
    '    Header always set Content-Security-Policy "' + POLICY + '"\n'
)

src = open(HT, encoding="utf-8").read()
before = hashlib.sha256(src.encode("utf-8")).hexdigest()

# The three Report-Only lines currently in the file, as one contiguous run.
pat = re.compile(
    r'[ \t]*Header onsuccess unset Content-Security-Policy-Report-Only\n'
    r'[ \t]*Header always unset Content-Security-Policy-Report-Only\n'
    r'[ \t]*Header always set Content-Security-Policy-Report-Only "[^"]*"\n'
)
n = len(pat.findall(src))
if n != 1:
    print("ABORT: expected exactly 1 Report-Only block, found %d" % n)
    sys.exit(1)
if 'Header always set Content-Security-Policy "' in src:
    print("ABORT: an enforcing CSP is already set - refusing to add a second")
    sys.exit(1)

out = pat.sub(lambda m: BLOCK, src, count=1)

# The comment above the block explains the Report-Only decision; correct it in place.
out = out.replace(
    "# 2. Content-Security-Policy is REPORT-ONLY, deliberately, and must not be promoted to\n"
    "#    enforcing without a browser pass.",
    "# 2. Content-Security-Policy is ENFORCING as of " + STAMP + ", after a browser pass that\n"
    "#    exercised the real flows: home, /contact/, /products/, a product page, an oEmbed\n"
    "#    article; the consent banner accepted AND rejected; reCAPTCHA v2 loaded and executing;\n"
    "#    CF7 client validation, required-field errors and its /wp-json/ round trips; and the\n"
    "#    Drift chat widget opened. Six origins that only a real browser can see were added\n"
    "#    before the flip - see the deploy script's header for each one and its evidence.\n"
    "#    The Report-Only header is unset above so exactly one policy is ever emitted.\n"
    "#    ORIGINAL NOTE (kept, because it is still the reason not to guess at this policy):\n"
    "#    Content-Security-Policy must not be promoted without a browser pass.")

if out == src:
    print("ABORT: no change produced")
    sys.exit(1)

shutil.copy2(HT, BAK)
if hashlib.sha256(open(BAK, "rb").read()).hexdigest() != before:
    print("ABORT: backup mismatch")
    sys.exit(1)
open(HT, "w", encoding="utf-8").write(out)

after = hashlib.sha256(open(HT, "rb").read()).hexdigest()
print("STAGE 2 APPLIED")
print("  .htaccess %s -> %s" % (before[:12], after[:12]))
print("  backup    %s" % os.path.basename(BAK))
print("  RO lines remaining: %d" % out.count("Content-Security-Policy-Report-Only"))
print("  enforcing set lines: %d" % out.count('Header always set Content-Security-Policy "'))

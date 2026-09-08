#!/usr/bin/env python3
"""Orders CSP, step 2 of 2 — promote to enforcing.

The Report-Only pass walked home, a purchasable product, /cart/, /checkout/ (with a real cart,
all three gateways selected), /contact/, /my-account/, search and a quote-only product.
Seven of those eight reported ZERO violations. /contact/ reported 24, of exactly two kinds,
and neither is a missing dependency:

  16  http://ambimat.com/... style-src-elem and script-src-elem
      An artefact of Report-Only, not a real gap. `upgrade-insecure-requests` is enforced-only
      by spec, so a Report-Only policy evaluates the PRE-upgrade URL and reports http://. The
      live runtime already shows every one of these assets arriving over https, upgraded by
      the enforcing header this host has been sending all along. Under this policy the same
      upgrade happens first and they match https://ambimat.com. Re-checked immediately after
      this deploy.

   8  pagead2.googlesyndication.com and googleads.g.doubleclick.net
      Deliberately not allowed. See below.

WHAT IS ALLOWED, AND WHY (nothing here is copied from ambimat.com's policy)

  'self'                      everything; Astra + Elementor + WooCommerce
  'unsafe-inline' script      24 inline <script> per page from WP core, Woo and Elementor
  'unsafe-inline' style       12 inline <style> per page from the same
  fonts.googleapis.com        the Google Fonts stylesheet, on 53/53 pages
  fonts.gstatic.com           the faces it pulls
  static.addtoany.com         the share widget: script AND iframe
  www.googletagmanager.com    GA4 gtag
  www.google-analytics.com    GA4's script + collect endpoint
  analytics.google.com        GA4 /g/collect. The BARE host, listed explicitly, because
                              `*.analytics.google.com` does not match it — the exact defect
                              this estate already hit once on ambimat.com.
  stats.g.doubleclick.net     GA4 with Google Signals
  www.google.co.in            the Ads remarketing pixel
  ambimat.com                 script/style/font/img. /contact/ embeds the Central Intake
                              section, which brings ambimat.com's jQuery, Contact Form 7, the
                              CF7 validation and conditional-field plugins, an accordion menu
                              and its Font Awesome faces. That architecture is out of scope to
                              change, and the contact form does not work without them.
  www.paypal.com              PayPal Commerce SDK: script + XHR, on product/cart/checkout
  c.paypal.com                PayPal's own script and frame
  c6.paypal.com               PayPal imagery
  s.w.org                     WordPress emoji/SVG
  i0.wp.com                   Jetpack Photon images
  blob: (img, worker)         wp-emoji-loader builds its detection worker from a blob
  data: (img, font)           inline SVG/data-URI assets from WP and Astra

WHAT IS DELIBERATELY *NOT* ALLOWED

  pagead2.googlesyndication.com, googleads.g.doubleclick.net, ep1/ep2.adtrafficquality.google
      Site Kit's AdSense loader (ca-pub-9631847965894046) rides in with the Central Intake
      embed on /contact/. The page carries ZERO `ins.adsbygoogle` units, so the tag renders no
      advertisement at all — it only phones home. Permitting it would mean opening five
      further third-party surfaces, including doubleclick frames, on the host that takes
      payments, for an advert that does not exist. Declining the loader closes all of them at
      the root. Central Intake itself is untouched; the policy simply does not permit
      something this host never needed.

  'unsafe-eval'
      Nothing asked for it across eight pages including checkout with three gateways selected.
      Not added speculatively.

  paypalobjects.com, t.paypal.com
      Plausible for PayPal, never observed. Guessing origins in would defeat the pass.

form-action: 'self' plus the hosts the gateway plugins name in their own source. Juspay and
PayGlocal both hand off with wp_redirect() — a 302, which CSP does not govern — so 'self'
alone should suffice. They are listed anyway because completing a payment is the one step this
campaign is forbidden to exercise, and a wrong form-action there breaks real revenue.

upgrade-insecure-requests is carried explicitly: it was this host's ONLY CSP, and `Header
always set Content-Security-Policy` replaces that header rather than adding to it.
"""
import hashlib, os, re, shutil, sys, time

HT = "/home/u675763961/domains/orders.ambimat.com/public_html/.htaccess"
BAK = HT + ".pre-cspenforce-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

src = open(HT, encoding="utf-8").read()
m = re.search(r'Header always set Content-Security-Policy-Report-Only "([^"]*)"', src)
if not m:
    print("ABORT: no Report-Only policy to promote"); sys.exit(1)
policy = m.group(1)

for must in ("worker-src 'self' blob:", "https://ambimat.com;", "upgrade-insecure-requests"):
    if must not in policy:
        print("ABORT: policy is missing %r — is this the revised one?" % must); sys.exit(1)
if "pagead2" in policy:
    print("ABORT: the AdSense loader is still in the policy"); sys.exit(1)

BLOCK_OLD = re.search(
    r'# --- ambimat CSP \(report-only\).*?# --- end ambimat CSP -+\n', src, re.S)
if not BLOCK_OLD:
    print("ABORT: could not find the report-only block"); sys.exit(1)

NEW_BLOCK = (
    "# --- ambimat CSP (enforcing) --------------------------------------------------\n"
    "# Derived from Orders' own runtime, never copied from ambimat.com. Every origin below was\n"
    "# observed on this host; see the deploy script for where. Promoted after a Report-Only\n"
    "# pass over home, a purchasable product, cart, checkout with all three gateways selected,\n"
    "# /contact/, /my-account/, search and a quote-only product.\n"
    "#\n"
    "# Google AdSense is deliberately ABSENT: its loader arrives with the Central Intake embed\n"
    "# on /contact/, renders zero ad units, and permitting it would open doubleclick and\n"
    "# adtrafficquality frames on the host that takes payments for no advertisement at all.\n"
    "#\n"
    "# upgrade-insecure-requests is kept: it was this host's only CSP, and `Header always set`\n"
    "# REPLACES that header rather than adding to it.\n"
    "<IfModule mod_headers.c>\n"
    "  Header always unset Content-Security-Policy-Report-Only\n"
    "  Header always unset Content-Security-Policy\n"
    '  Header always set Content-Security-Policy "' + policy + '"\n'
    "</IfModule>\n"
    "# --- end ambimat CSP ---------------------------------------------------------\n"
)

out = src[:BLOCK_OLD.start()] + NEW_BLOCK + src[BLOCK_OLD.end():]
before = hashlib.sha256(src.encode()).hexdigest()
shutil.copy2(HT, BAK)
if hashlib.sha256(open(BAK, "rb").read()).hexdigest() != before:
    print("ABORT: backup mismatch"); sys.exit(1)
open(HT, "w", encoding="utf-8").write(out)
print("ORDERS CSP ENFORCING")
print("  .htaccess %s -> %s" % (before[:12], hashlib.sha256(open(HT, 'rb').read()).hexdigest()[:12]))
print("  backup    %s" % os.path.basename(BAK))
print("  report-only lines left: %d" % out.count("Content-Security-Policy-Report-Only"))
print("  enforcing set lines:    %d" % out.count('Header always set Content-Security-Policy "'))

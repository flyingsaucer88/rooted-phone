#!/usr/bin/env python3
"""Orders CSP Report-Only, revision 2 — act on what the first Report-Only pass reported.

THREE FINDINGS, THREE DIFFERENT ANSWERS.

1. ADD  worker-src 'self' blob:
   wp-includes/js/wp-emoji-loader.min.js builds its detection worker from a blob. First-party
   WordPress core, on every page. Legitimate required dependency.

2. ADD  https://ambimat.com to font-src
   /contact/ embeds the Central Intake contact section, which brings ambimat.com's stylesheets
   with it, and one of them (bellows-accordion-menu) pulls Font Awesome .woff2/.woff/.ttf from
   ambimat.com. Legitimate required dependency of an architecture this campaign must not alter.

3. REMOVE  https://pagead2.googlesyndication.com from script-src
   NOT whitelisted, and not merely left out: removed on purpose.
   The Central Intake embed also drags in Site Kit's Google AdSense loader
   (ca-pub-9631847965894046). The page contains ZERO `ins.adsbygoogle` ad units, so the tag
   loads, phones home and renders nothing. On the host that takes payments it was pulling in
   googleads.g.doubleclick.net frames, ep1/ep2.adtrafficquality.google (script + connect +
   frame) and www.google.com frames — six third-party surfaces for an advert that does not
   exist.
   Declining to allow the loader kills all six at the root rather than adding five more
   origins to permit a dead integration. Central Intake itself is untouched: the CSP simply
   does not permit something this host never needed.

The `http://ambimat.com` style-src/script-src reports from pass 1 are NOT a missing origin.
`upgrade-insecure-requests` is ignored in a Report-Only policy (spec: it is enforced-only), so
pass 1 saw the pre-upgrade URLs. The live runtime already shows these assets loading over
https, upgraded by the enforcing header this host already sends. Re-checked after enforcement.
"""
import hashlib, os, re, shutil, sys, time

HT = "/home/u675763961/domains/orders.ambimat.com/public_html/.htaccess"
BAK = HT + ".pre-cspro2-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

src = open(HT, encoding="utf-8").read()
m = re.search(r'(Header always set Content-Security-Policy-Report-Only ")([^"]*)(")', src)
if not m:
    print("ABORT: no Report-Only policy found"); sys.exit(1)
pol = m.group(2)

edits = [
    (" https://pagead2.googlesyndication.com", "", "remove AdSense loader from script-src"),
    ("font-src 'self' data: https://fonts.gstatic.com;",
     "font-src 'self' data: https://fonts.gstatic.com https://ambimat.com;",
     "add ambimat.com to font-src"),
    ("frame-ancestors 'self';",
     "worker-src 'self' blob:; frame-ancestors 'self';",
     "add worker-src"),
]
for old, new, why in edits:
    if new and new in pol:
        print("  already applied: %s" % why); continue
    if pol.count(old) != 1:
        print("ABORT: %r appears %d times (%s)" % (old[:40], pol.count(old), why)); sys.exit(1)
    pol = pol.replace(old, new, 1)
    print("  %s" % why)

out = src[:m.start(2)] + pol + src[m.end(2):]
before = hashlib.sha256(src.encode()).hexdigest()
shutil.copy2(HT, BAK)
open(HT, "w", encoding="utf-8").write(out)
print("REPORT-ONLY REV 2 APPLIED")
print("  .htaccess %s -> %s" % (before[:12], hashlib.sha256(open(HT,'rb').read()).hexdigest()[:12]))
print("  backup    %s" % os.path.basename(BAK))

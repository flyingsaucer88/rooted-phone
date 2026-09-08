#!/usr/bin/env python3
"""Stage 2c - add 'self' to frame-src.

The frame-src allowlist was built from the nine external publisher embeds and lists only
third-party origins, so under enforcement the site could not frame its own pages. A 346-page
sweep of the public site found ZERO same-origin iframes, so no public page needed this - but
this .htaccess sits at public_html root and therefore also governs /wp-admin/, where the
Customizer preview and the TinyMCE editor body ARE same-origin frames. Blocking those would
break the admin UI to protect nothing: same-origin framing of this site is already bounded by
frame-ancestors 'self'.

Found while a measurement script tried to load ambimat.com in an iframe on ambimat.com and
Chrome refused - the kind of thing that only shows up when something actually tries it.
"""
import hashlib, os, shutil, sys, time

HT = "/home/xemtd1m9scay/public_html/.htaccess"
BAK = HT + ".pre-cspframeself-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

OLD = "frame-src https://www.google.com"
NEW = "frame-src 'self' https://www.google.com"

src = open(HT, encoding="utf-8").read()
if "frame-src 'self'" in src:
    print("already applied")
    sys.exit(0)
if src.count(OLD) != 1:
    print("ABORT: expected 1 occurrence of the frame-src prefix, found %d" % src.count(OLD))
    sys.exit(1)

before = hashlib.sha256(src.encode("utf-8")).hexdigest()
shutil.copy2(HT, BAK)
if hashlib.sha256(open(BAK, "rb").read()).hexdigest() != before:
    print("ABORT: backup mismatch")
    sys.exit(1)
open(HT, "w", encoding="utf-8").write(src.replace(OLD, NEW, 1))
print("STAGE 2c APPLIED")
print("  .htaccess %s -> %s" % (before[:12], hashlib.sha256(open(HT, "rb").read()).hexdigest()[:12]))
print("  backup    %s" % os.path.basename(BAK))

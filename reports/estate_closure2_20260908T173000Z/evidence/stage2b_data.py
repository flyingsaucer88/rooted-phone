#!/usr/bin/env python3
"""Stage 2b - allow data: in script-src, because the site's own optimiser requires it.

Found by the post-enforcement browser pass, not by reading the policy: with the enforcing
header live, Chrome reported `script-src-elem <- data` four times on the home page and the
Drift widget never appeared.

Root cause is flying-scripts/html-rewrite.php:52, which takes an INLINE script, base64s its
body, and parks it in data-src="data:text/javascript;base64,..." until the visitor interacts.
So the delayed scripts are not third-party fetches at all - they are this site's own inline
scripts, re-transported as data: URIs.

flying_scripts_include_list is:
    driftt, js.driftt.com, adsbygoogle, googlesyndication, pagead2,
    maps.googleapis, recaptcha/api.js
which means blocking data: takes out the live chat, the ad tag, the Maps JS API and - the
serious one - the reCAPTCHA bootstrap that the contact form depends on.

On risk: this policy already carries 'unsafe-inline' and 'unsafe-eval' in script-src, because
WordPress core, the theme and GTM all emit inline script. Against a policy that already
permits arbitrary inline script, `data:` grants an attacker nothing further - it is the same
inline script with a different transport. It is listed last so that whoever eventually removes
'unsafe-inline' removes this at the same time; on its own, next to a nonce/hash policy, `data:`
WOULD be a real hole and must not survive that migration.
"""
import hashlib, os, shutil, sys, time

HT = "/home/xemtd1m9scay/public_html/.htaccess"
BAK = HT + ".pre-cspdata-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

OLD = "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com"
NEW = "script-src 'self' 'unsafe-inline' 'unsafe-eval' data: https://www.googletagmanager.com"

src = open(HT, encoding="utf-8").read()
if src.count(OLD) != 1:
    print("ABORT: expected 1 occurrence of the script-src prefix, found %d" % src.count(OLD))
    sys.exit(1)
if "'unsafe-eval' data:" in src:
    print("already applied")
    sys.exit(0)

before = hashlib.sha256(src.encode("utf-8")).hexdigest()
shutil.copy2(HT, BAK)
if hashlib.sha256(open(BAK, "rb").read()).hexdigest() != before:
    print("ABORT: backup mismatch")
    sys.exit(1)
open(HT, "w", encoding="utf-8").write(src.replace(OLD, NEW, 1))
print("STAGE 2b APPLIED")
print("  .htaccess %s -> %s" % (before[:12], hashlib.sha256(open(HT, "rb").read()).hexdigest()[:12]))
print("  backup    %s" % os.path.basename(BAK))

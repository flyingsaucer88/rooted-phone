#!/usr/bin/env python3
"""Remove the `Header onsuccess unset` line: this host's mod_headers emulation does not
support the `onsuccess` condition and emitted a literal, malformed `ss: unset ...` response
header instead of honouring it. `Header always unset` on its own does the job here."""
import hashlib, os, shutil, sys, time
HT = "/home/u675763961/domains/orders.ambimat.com/public_html/.htaccess"
BAK = HT + ".pre-onsuccessfix-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
BAD = "  Header onsuccess unset Content-Security-Policy-Report-Only\n"
src = open(HT, encoding="utf-8").read()
if BAD not in src:
    print("nothing to remove"); sys.exit(0)
before = hashlib.sha256(src.encode()).hexdigest()
shutil.copy2(HT, BAK)
open(HT, "w", encoding="utf-8").write(src.replace(BAD, "", 1))
print("removed the onsuccess line")
print("  .htaccess %s -> %s" % (before[:12], hashlib.sha256(open(HT,'rb').read()).hexdigest()[:12]))
print("  backup    %s" % os.path.basename(BAK))

#!/usr/bin/env python3
"""Stage 6 - the three developer-resource cards on /careers/ are h4 under an h2.

Same defect and same component as the front page, but NOT the same measurements: on /careers/
the card h4 is 20px/600 at both widths and differs from an h3 only in line-height (22px desktop,
26px at <=767px, against 27px for h3). The front page's guard class pins font-size and
font-weight too and would be wrong here, so this gets its own class.

The <h4> open tag appears exactly 3 times in this file and every one of them is a card title,
so all three are promoted together - promoting one would just move the skip.
"""
import hashlib, os, shutil, subprocess, sys, time

T = "/home/xemtd1m9scay/public_html/wp-content/themes/launchseat/page-careers.php"
PHP = "/usr/local/bin/php"
BAK = T + ".pre-cardheading-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

OLD_OPEN = '<h4 class="pmd-card-title-text">'
NEW_OPEN = '<h3 class="pmd-card-title-text ambi-outline-careers-card">'

src = open(T, encoding="utf-8").read()
if "ambi-outline-careers-card" in src:
    print("already applied")
    sys.exit(0)

n_open = src.count(OLD_OPEN)
n_close = src.count("</h4>")
if n_open != 3 or n_close != 3:
    print("ABORT: expected 3 card <h4> and 3 </h4>, found %d and %d" % (n_open, n_close))
    sys.exit(1)

out = src.replace(OLD_OPEN, NEW_OPEN).replace("</h4>", "</h3>")
if out.count("<h4") != 0 or out.count("</h4>") != 0:
    print("ABORT: an h4 survived")
    sys.exit(1)

before = hashlib.sha256(src.encode("utf-8")).hexdigest()
shutil.copy2(T, BAK)
if hashlib.sha256(open(BAK, "rb").read()).hexdigest() != before:
    print("ABORT: backup mismatch")
    sys.exit(1)
open(T, "w", encoding="utf-8").write(out)
r = subprocess.run([PHP, "-l", T], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
if r.returncode != 0:
    shutil.copy2(BAK, T)
    print("ABORT: php -l failed, ROLLED BACK\n%s" % r.stdout.decode())
    sys.exit(1)
print("STAGE 6 APPLIED")
print("  page-careers.php %s -> %s" % (before[:12], hashlib.sha256(open(T, "rb").read()).hexdigest()[:12]))
print("  backup           %s" % os.path.basename(BAK))

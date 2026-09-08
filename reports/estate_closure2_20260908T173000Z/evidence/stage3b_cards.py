#!/usr/bin/env python3
"""Stage 3b - the two product-category grids emit h5 card titles where the identical
component emits h3 on /products/.

With Stage 3's section heading in place, /by-industry/ and /by-technologies/ read
h1 h2 h5 - still a skip, because the card sits two levels below its section. The card
component in page-products-landing.php, with the same classes and the same markup shape, is
an h3. So this is an inconsistency in the theme, not a design decision, and h3 is the level
the rest of the theme already uses for this card.

Measured in Chrome by swapping the tag in place on the live page before writing this:

    card box      360x300 @272   ->  360x300 @272    identical
    media box     360x180 @272   ->  360x180 @272    identical
    title box     360x56  @396   ->  360x60  @392    +4px, growing upward
    document height                  unchanged

The card is a fixed 300px and the title is bottom-anchored inside the image overlay, so the
title block grows into space it already had. Nothing reflows and nothing overflows. The
result is that these two grids now render exactly like the /products/ grid.

No CSS guard: freezing the h5 line-height here would preserve the inconsistency instead of
removing it, and the target appearance already ships on a sibling page.
"""
import hashlib, os, shutil, subprocess, sys, time

T = "/home/xemtd1m9scay/public_html/wp-content/themes/launchseat"
PHP = "/usr/local/bin/php"
SUF = ".pre-cardlevel-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

FILES = ["taxonomy-product_categories-by-industries.php",
         "taxonomy-product_categories-by-technologies.php"]
OLD = '<h5 class="pmd-card-title-text pmd-card-title-overlay">'
NEW = '<h3 class="pmd-card-title-text pmd-card-title-overlay">'


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def lint(p):
    r = subprocess.run([PHP, "-l", p], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode("utf-8", "replace")


staged = {}
for fn in FILES:
    p = os.path.join(T, fn)
    src = open(p, encoding="utf-8").read()
    n_old, n_new = src.count(OLD), src.count(NEW)
    if n_old == 0 and n_new >= 1:
        continue
    if n_old != 1:
        print("ABORT %s: expected 1 h5 card title, found %d" % (fn, n_old))
        sys.exit(1)
    body = src.replace(OLD, NEW, 1)
    # the closing tag must be demoted too, and there must be exactly one
    if body.count("</h5>") != 1:
        print("ABORT %s: expected 1 </h5>, found %d" % (fn, body.count("</h5>")))
        sys.exit(1)
    staged[p] = body.replace("</h5>", "</h3>", 1)

if not staged:
    print("nothing to do - already applied")
    sys.exit(0)

for p, out in staged.items():
    before = sha(p)
    shutil.copy2(p, p + SUF)
    if sha(p + SUF) != before:
        print("ABORT: backup mismatch %s" % p)
        sys.exit(1)
    open(p, "w", encoding="utf-8").write(out)
    rc, msg = lint(p)
    if rc != 0:
        shutil.copy2(p + SUF, p)
        print("ABORT %s: php -l failed, ROLLED BACK\n%s" % (os.path.basename(p), msg))
        sys.exit(1)
    print("  %-48s %s -> %s" % (os.path.basename(p), before[:12], sha(p)[:12]))
print("STAGE 3b APPLIED  (backup suffix %s)" % SUF)

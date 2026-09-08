#!/usr/bin/env python3
"""Stage 3 - close the three "h1 straight to a card grid" heading advisories at their cause.

/products/, /by-industry/ and /by-technologies/ each render an <h1> and then a grid of card
titles at h3 or h5, with nothing in between. The reported skip (h1->h3, h1->h5) is real, and
the actual defect is the missing one: the card grid is a section of the page and has no
section heading at all.

The fix is that heading, not a renumbering of the cards. Promoting fifteen card titles to h2
was measured and is NOT visually neutral - .pmd-card-title-text leaves line-height to the base
heading rules, so an h5 card renders at line-height 1.1 (22px) and an h2 card at 1.3 (26px),
five pixels taller on every card in the grid. Adding the section heading changes no card at
all.

<h2 class="screen-reader-text"> is the theme's own visually-hidden utility, already used in
header.php for the search label. Measured on the live page before writing this: computed
position absolute, 1x1, overflow hidden, clip-path inset(50%), rendered box 0x0, and document
scrollHeight identical with and without it (1862px both ways).
"""
import hashlib, os, shutil, subprocess, sys, time

T = "/home/xemtd1m9scay/public_html/wp-content/themes/launchseat"
PHP = "/usr/local/bin/php"
SUF = ".pre-headingsection-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

LOOP_ANCHOR = "\t\t\t\t\t<?php\n\t\t\t\t\tforeach ($child_categories As $Category) {"

EDITS = {
    "page-products-landing.php": [(
        "\t\t\t\t\t<?php if ( $ambi_products ) : ?>\n\t\t\t\t\t<div class=\"row\">",
        "\t\t\t\t\t<?php if ( $ambi_products ) : ?>\n"
        "\t\t\t\t\t<h2 class=\"screen-reader-text\">Products</h2>\n"
        "\t\t\t\t\t<div class=\"row\">", 1)],
    "taxonomy-product_categories-by-industries.php": [(
        LOOP_ANCHOR,
        "\t\t\t\t\t<h2 class=\"screen-reader-text\">Industries</h2>\n" + LOOP_ANCHOR, 1)],
    "taxonomy-product_categories-by-technologies.php": [(
        LOOP_ANCHOR,
        "\t\t\t\t\t<h2 class=\"screen-reader-text\">Technologies</h2>\n" + LOOP_ANCHOR, 1)],
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def lint(p):
    r = subprocess.run([PHP, "-l", p], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode("utf-8", "replace")


staged = {}
for fn, edits in EDITS.items():
    p = os.path.join(T, fn)
    src = open(p, encoding="utf-8").read()
    out = src
    for old, new, n in edits:
        c = out.count(old)
        if c == 0 and out.count(new) >= n:
            continue
        if c != n:
            print("ABORT %s: expected %d occurrence(s), found %d" % (fn, n, c))
            sys.exit(1)
        out = out.replace(old, new, n)
    if out != src:
        staged[p] = out

if not staged:
    print("nothing to do - all edits already applied")
    sys.exit(0)

report = []
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
    report.append((os.path.basename(p), before, sha(p)))

print("STAGE 3 APPLIED  (backup suffix %s)" % SUF)
for fn, b, a in report:
    print("  %-48s %s -> %s" % (fn, b[:12], a[:12]))

#!/usr/bin/env python3
"""Stage 1 - add the missing <main> landmark at the shared theme source, and repair the
two genuine accessibility defects in the contact-page map block.

Every edit is an exact-string replacement with an asserted occurrence count, each file is
sha256'd and backed up before the write, and PHP syntax is checked after. Nothing is written
unless every replacement in the file matched exactly once.

Idempotent: an edit whose replacement text is already present and whose search text is gone
is treated as already applied, so a partially-completed run can simply be re-run.
"""
import hashlib, os, shutil, subprocess, sys, time

T = "/home/xemtd1m9scay/public_html/wp-content/themes/launchseat"
PHP = "/usr/local/bin/php"
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
SUF = ".pre-mainlandmark-" + STAMP

EDITS = {
    "header.php": [
        # header.php currently ends after the navbar with no content landmark opened.
        ("    <!--navbar -->\n",
         "    <!--navbar -->\n\n    <main id=\"main\" class=\"site-main\">\n", 1),
    ],
    "footer.php": [
        # footer.php opens the site footer directly; close the landmark before it.
        ("\t<footer id=\"contact\">",
         "\t</main><!-- #main -->\n\n\t<footer id=\"contact\">", 1),
    ],
    "search.php": [
        # search.php already had its own <main>; demote it so header.php's is the only one.
        ("<main id=\"main\" class=\"site-main\" role=\"main\">",
         "<div class=\"site-main\">", 1),
        ("</main><!-- #main -->",
         "</div><!-- .site-main -->", 1),
    ],
    "page-contact.php": [
        # A Google Maps embed with no accessible name.
        ('id="gmap_canvas" src=',
         'id="gmap_canvas" title="Ambimat Electronics office location on Google Maps" src=', 1),
        # An empty anchor left behind by the map-generator tool: no accessible name, no text,
        # and an uncontrolled outbound link to a site nobody chose to endorse.
        ('<a href="https://google-map-generator.com"></a>', '', 1),
    ],
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def lint(p):
    r = subprocess.run([PHP, "-l", p], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return r.returncode, r.stdout.decode("utf-8", "replace")


staged = {}
skipped = []
for fn, edits in EDITS.items():
    p = os.path.join(T, fn)
    src = open(p, encoding="utf-8").read()
    out = src
    for old, new, n in edits:
        c = out.count(old)
        if c == n:
            out = out.replace(old, new)
            continue
        # already applied?
        if c == 0 and (new == "" or out.count(new) >= n):
            continue
        print("ABORT %s: expected %d occurrence(s) of %r, found %d" % (fn, n, old[:60], c))
        sys.exit(1)
    if out == src:
        skipped.append(fn)
        continue
    staged[p] = out

report = []
for p, out in staged.items():
    before = sha(p)
    shutil.copy2(p, p + SUF)
    if sha(p + SUF) != before:
        print("ABORT: backup mismatch for %s" % p)
        sys.exit(1)
    open(p, "w", encoding="utf-8").write(out)
    rc, msg = lint(p)
    if rc != 0:
        shutil.copy2(p + SUF, p)
        print("ABORT %s: php -l failed, ROLLED BACK\n%s" % (os.path.basename(p), msg))
        sys.exit(1)
    report.append((os.path.basename(p), before, sha(p), os.path.basename(p + SUF)))

for fn in sorted(EDITS):
    p = os.path.join(T, fn)
    rc, msg = lint(p)
    print("lint %-20s %s" % (fn, "OK" if rc == 0 else "FAIL " + msg))

print("STAGE 1 APPLIED")
for fn, b, a, bak in report:
    print("  %-20s %s -> %s   backup %s" % (fn, b[:12], a[:12], bak))
for fn in skipped:
    print("  %-20s already applied, untouched" % fn)

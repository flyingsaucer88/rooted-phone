#!/usr/bin/env python3
"""Stage 5 - the front page's three blog cards are h4 directly under the section's h2.

front-page.php emits the card title for the "latest posts" grid at h4 while the section above
it is an h2, so the home page - the estate's most-visited URL - carries an h2->h4 skip.

The card's TYPE lives in .pmd-card-title-text, but not all of it: font-size, font-weight and
line-height still come from the bare heading element, so a naked h4->h3 swap was measured at
+13px of document height and a visibly larger card title. Measured in Chrome inside
.pmd-card-body on the live front page:

                desktop            <=767px
    h3     24px / 600 / 26.4px   20px / 600 / 26px
    h4     20px / 500 / 22px     18px / 500 / 23.4px

so the guard class restates the h4 values at both breakpoints and only those three properties.

The open tag is unique in front-page.php (verified: exactly one occurrence), so the whole
h4 block is replaced as one exact string rather than by line number.
"""
import hashlib, os, shutil, subprocess, sys, time

T = "/home/xemtd1m9scay/public_html/wp-content/themes/launchseat/front-page.php"
PHP = "/usr/local/bin/php"
BAK = T + ".pre-cardheading-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

OLD = ('<h4 class="pmd-card-title-text">\n'
       '                                        <a href="<?php the_permalink(); ?>" title="<?php the_title(); ?>">\n'
       '                                            <?php the_title(); ?>\n'
       '                                        </a>\n'
       '                                    </h4>')
NEW = ('<h3 class="pmd-card-title-text ambi-outline-card-h4-as-h3">\n'
       '                                        <a href="<?php the_permalink(); ?>" title="<?php the_title(); ?>">\n'
       '                                            <?php the_title(); ?>\n'
       '                                        </a>\n'
       '                                    </h3>')

src = open(T, encoding="utf-8").read()
if "ambi-outline-card-h4-as-h3" in src:
    print("already applied")
    sys.exit(0)
n = src.count(OLD)
if n != 1:
    print("ABORT: expected 1 occurrence of the card block, found %d" % n)
    sys.exit(1)

before = hashlib.sha256(src.encode("utf-8")).hexdigest()
shutil.copy2(T, BAK)
if hashlib.sha256(open(BAK, "rb").read()).hexdigest() != before:
    print("ABORT: backup mismatch")
    sys.exit(1)
open(T, "w", encoding="utf-8").write(src.replace(OLD, NEW, 1))
r = subprocess.run([PHP, "-l", T], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
if r.returncode != 0:
    shutil.copy2(BAK, T)
    print("ABORT: php -l failed, ROLLED BACK\n%s" % r.stdout.decode())
    sys.exit(1)
print("STAGE 5 APPLIED")
print("  front-page.php %s -> %s" % (before[:12], hashlib.sha256(open(T, "rb").read()).hexdigest()[:12]))
print("  backup         %s" % os.path.basename(BAK))

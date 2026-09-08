#!/usr/bin/env python3
"""Stage 7 - the lone <h5> in the company timeline is a date label, not a section heading.

Post 1823 (post_type `timeline`, title "1982") is the ONLY one of 27 timeline entries that
contains any heading at all:

    <ul>
      <li><h5>April, 1982</h5> Ambimat Electronics is a registered partnership firm</li>
      <li>Ambimat Electronics starts building microprocessor trainer kits ...</li>
    </ul>

Its two sibling <li> in the same list have no heading, and no other year entry has one. So it
does not open a section - it labels a date inside one bullet. Renumbering it to <h3> would keep
a heading that describes nothing; it is demoted out of the hierarchy instead.

WHY A DATABASE WRITE HERE, when every other heading fix in this campaign avoided one:
ang-timeline renders with `echo $post->post_content;` (public/widgets/timeline-wgt.php:455) -
raw, no `the_content`, no filter of any kind. There is no filter mechanism to prefer. The
alternative would be patching a third-party plugin, which an update would silently revert.

Blast radius is bounded and checked: `timeline` has a Yoast indexable row
(https://ambimat.com/timeline/1982/) but that post type is NOT in sitemap_index.xml, and the
visible text is unchanged - only the tag around "April, 1982" moves. The indexable row is
captured before and compared after.

Visual is preserved by p.ambi-timeline-date in ambi-heading-outline.php, from the measured h5:
18px / 500 / 19.8px / margin 10px 0 0 / Montserrat / uppercase / rgb(46,52,61).
"""
import hashlib, subprocess, sys

WP = ["wp", "--path=/home/xemtd1m9scay/public_html"]
POST = "1823"
OLD = "<h5>April, 1982</h5>"
NEW = '<p class="ambi-timeline-date">April, 1982</p>'


def wp(*args):
    r = subprocess.run(WP + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print("WP FAILED: %s\n%s" % (" ".join(args)[:120], r.stderr.decode()[:300]))
        sys.exit(1)
    return r.stdout.decode("utf-8", "replace")


def indexable():
    return wp("db", "query",
              "SELECT object_id,permalink,title,description,open_graph_image,canonical,"
              "is_robots_noindex FROM wp_yoast_indexable WHERE object_id=%s;" % POST,
              "--skip-column-names")


content = wp("post", "get", POST, "--field=post_content")
print("content sha before: %s (%d bytes)" % (hashlib.sha256(content.encode()).hexdigest()[:16], len(content)))

n = content.count(OLD)
print("occurrences of the h5: %d" % n)
if n != 1:
    if content.count(NEW) == 1:
        print("already applied")
        sys.exit(0)
    print("ABORT: expected exactly 1")
    sys.exit(1)

new = content.replace(OLD, NEW, 1)
if "<h5" in new or "</h5>" in new:
    print("ABORT: an h5 survived")
    sys.exit(1)
if "April, 1982" not in new:
    print("ABORT: the date text did not survive")
    sys.exit(1)
# visible text must be byte-identical once tags are stripped
import re
strip = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()
if strip(content) != strip(new):
    print("ABORT: visible text changed\n  before=%r\n  after =%r" % (strip(content)[:120], strip(new)[:120]))
    sys.exit(1)
print("visible text identical after tag change: yes")

before_idx = indexable()
print("indexable before: %s" % before_idx.strip()[:200])
open("/tmp/1823_after.html", "w", encoding="utf-8").write(new)
print(wp("eval",
         "$c=file_get_contents('/tmp/1823_after.html');"
         "$r=wp_update_post(array('ID'=>%s,'post_content'=>wp_slash($c)),true);"
         "echo is_wp_error($r)?('ERR '.$r->get_error_message()):('OK '.$r);" % POST))

after = wp("post", "get", POST, "--field=post_content")
print("content sha after : %s (%d bytes)" % (hashlib.sha256(after.encode()).hexdigest()[:16], len(after)))
if after.rstrip("\n") != new.rstrip("\n"):
    print("WARNING: stored content differs from what was submitted (slash handling?)")
after_idx = indexable()
print("indexable after : %s" % after_idx.strip()[:200])
print("INDEXABLE UNCHANGED" if before_idx == after_idx else "*** INDEXABLE MOVED - INSPECT ***")

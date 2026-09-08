#!/usr/bin/env python3
"""Stage 4 - repair the two dead fime.com references on post 17443.

fime.com serves its 404 page with HTTP **200**, so neither link ever showed up as broken:

    https://www.fime.com/whitepaper/EMVmigration -> 200 -> https://www.fime.com/404  ("404 | Fime")
    https://www.fime.com/america.html            -> 200 -> https://www.fime.com/404  ("404 | Fime")
    https://www.fime.com/                        -> 200 -> https://www.fime.com/     ("Home | Fime")

Proven from the GoDaddy production host, a completely different network from the LAN this
session runs on - the LAN appliance at 192.168.3.1:8888 blocks fime.com outright and returns
its own "Blocked" page, which is why the monitor only ever recorded a connect timeout.

The whitepaper ("EMV Chip Migration for U.S. Merchant Community: Implementing Chip in the
Complex U.S. Acceptance Environment", FIME, 2015) has no live copy anywhere: every reference
still found on the web points back at this same fime.com URL. So the anchor is removed and the
title text is kept - the sentence already names the paper in quotes, so the citation survives
in full and only the dead hyperlink goes.

"FIME America" is repointed at https://www.fime.com/ , verified 200 with the real homepage
title. FIME as a company is alive; only the old path structure is gone.

Yoast: this is a content write, and a content write rebuilds the indexable row. The row is
captured before and compared after; if anything but the content-derived fields moved, the
script says so loudly. wp_slash() is applied because wp_update_post unslashes its input and
would otherwise eat backslashes out of post_content.
"""
import hashlib, json, subprocess, sys

WP = ["wp", "--path=/home/xemtd1m9scay/public_html"]
POST = "17443"

OLD_WP = '<a href="https://www.fime.com/whitepaper/EMVmigration"'
OLD_AM = 'href="https://www.fime.com/america.html"'
NEW_AM = 'href="https://www.fime.com/"'


def wp(*args, ok=(0,)):
    r = subprocess.run(WP + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode not in ok:
        print("WP FAILED: %s\n%s" % (" ".join(args)[:120], r.stderr.decode()[:400]))
        sys.exit(1)
    return r.stdout.decode("utf-8", "replace")


def indexable():
    q = ("SELECT object_id,permalink,title,description,open_graph_image,open_graph_title,"
         "open_graph_description,twitter_image,canonical,is_robots_noindex,primary_focus_keyword "
         "FROM wp_yoast_indexable WHERE object_id=%s AND object_type='post';" % POST)
    return wp("db", "query", q, "--skip-column-names")


content = wp("post", "get", POST, "--field=post_content")
before_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
print("post_content sha before: %s  (%d bytes)" % (before_sha[:16], len(content)))

n_wp = content.count(OLD_WP)
n_am = content.count(OLD_AM)
print("occurrences: whitepaper-anchor=%d  america-href=%d" % (n_wp, n_am))
if n_wp != 1 or n_am != 1:
    print("ABORT: expected exactly one of each")
    sys.exit(1)

# Unwrap the whitepaper anchor: keep its inner text, drop the <a>.
start = content.index(OLD_WP)
gt = content.index(">", start)
end = content.index("</a>", gt)
inner = content[gt + 1:end]
print("whitepaper anchor inner text: %r" % inner[:110])
new = content[:start] + inner + content[end + len("</a>"):]
new = new.replace(OLD_AM, NEW_AM, 1)

if "fime.com/whitepaper" in new or "fime.com/america.html" in new:
    print("ABORT: a dead fime URL survived the edit")
    sys.exit(1)
if inner not in new:
    print("ABORT: the whitepaper title text did not survive")
    sys.exit(1)

before_idx = indexable()
print("indexable before: %s" % before_idx.strip()[:220])

open("/tmp/17443_before.html", "w", encoding="utf-8").write(content)
open("/tmp/17443_after.html", "w", encoding="utf-8").write(new)

php = (
    "$c = file_get_contents('/tmp/17443_after.html');"
    "$r = wp_update_post(array('ID'=>%s,'post_content'=>wp_slash($c)), true);"
    "if (is_wp_error($r)) { echo 'ERR '.$r->get_error_message(); } else { echo 'OK '.$r; }"
) % POST
print(wp("eval", php))

after = wp("post", "get", POST, "--field=post_content")
print("post_content sha after : %s  (%d bytes)" % (hashlib.sha256(after.encode('utf-8')).hexdigest()[:16], len(after)))
if after.rstrip("\n") != new.rstrip("\n"):
    print("WARNING: stored content differs from what was submitted (slash handling?)")
    print("  submitted len %d, stored len %d" % (len(new), len(after)))

after_idx = indexable()
print("indexable after : %s" % after_idx.strip()[:220])
print("INDEXABLE UNCHANGED" if before_idx == after_idx else "*** INDEXABLE MOVED - INSPECT ***")

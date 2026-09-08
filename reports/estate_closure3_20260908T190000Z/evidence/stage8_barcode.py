#!/usr/bin/env python3
"""Stage 8 - remove the dead Wikimedia hotlink and its now-orphaned wrapper from /barcode/.

The image is broken AT SOURCE, not merely blocked. Verified from the GoDaddy production host
(a clean network, not the LAN this session runs on), with and without a Referer:

    .../thumb/a/ae/Barcodes_..._000130.jpg/250px-Barcodes_..._000130.jpg   404
    .../commons/a/ae/Barcodes_..._000130.jpg  (the original, not the thumb)  404

so no thumb-regeneration trick brings it back. Per the owner's instruction it is removed and
NOT replaced, and no substitute image is sourced.

WHAT IS ORPHANED, AND HOW THAT WAS ESTABLISHED
This is a block pasted from Wikipedia. Everything inside `<div class="thumb tright">` exists
only to present that one image:
  * the <a class="image"> wrapper links only to the Wikimedia File: page and wraps only the img
  * <div class="thumbcaption"> holds only the caption "Barcoded rolling stock in the UK, 1962"
  * <div class="magnify"></div> is Wikipedia's zoom-icon hook and is already empty
  * .thumb / .thumbinner are the float wrapper for that image alone
It is the ONLY .thumb block on the page (checked), and the ONLY upload.wikimedia.org image
(checked). The whole block therefore goes; nothing else in the article references it.

WHAT IS DELIBERATELY NOT TOUCHED
The surrounding prose, and every en.wikipedia.org text citation on the page, stay exactly as
they are - those are working links to articles, not to the dead file. og:image is a local
Ambimat card (i0.wp.com/.../ambimat-barcode-1200x630-1.png) and never referenced this image;
there is no JSON-LD image, no preload/prefetch, no CSS background and no lazy-load data
attribute pointing at Wikimedia (all four checked in the served HTML).

Layout: the block is floated right (`thumb tright`). Removing it lets the body text reflow into
the space rather than leaving a hole, and there is no fixed-height container left behind. The
caption text disappears with it, which is intended - it captions nothing now.
"""
import hashlib, re, subprocess, sys

WP = ["wp", "--path=/home/xemtd1m9scay/public_html"]
POST = "16871"


def wp(*args):
    r = subprocess.run(WP + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print("WP FAILED: %s\n%s" % (" ".join(args)[:100], r.stderr.decode()[:300]))
        sys.exit(1)
    return r.stdout.decode("utf-8", "replace")


def snapshot():
    return wp("db", "query",
              "SELECT object_id,permalink,title,description,open_graph_image,open_graph_title,"
              "twitter_image,canonical,is_robots_noindex FROM wp_yoast_indexable "
              "WHERE object_id=%s AND object_type='post';" % POST, "--skip-column-names")


content = wp("post", "get", POST, "--field=post_content")
print("content sha before: %s (%d bytes)" % (hashlib.sha256(content.encode()).hexdigest()[:16], len(content)))
print("upload.wikimedia.org occurrences before: %d" % content.count("upload.wikimedia.org"))

if "upload.wikimedia.org" not in content:
    print("already applied")
    sys.exit(0)

# Match the whole thumb block by structure, anchored on the class that opens it.
pat = re.compile(r'<div class="thumb tright">.*?</div>\s*</div>\s*</div>\s*', re.S)
found = pat.findall(content)
print("thumb blocks matched: %d" % len(found))
if len(found) != 1:
    print("ABORT: expected exactly one .thumb block")
    sys.exit(1)
block = found[0]
if "upload.wikimedia.org" not in block:
    print("ABORT: the matched block does not contain the dead image")
    sys.exit(1)
if block.count("<img") != 1:
    print("ABORT: the block holds %d images, expected 1" % block.count("<img"))
    sys.exit(1)

new = pat.sub("", content, count=1)

# Post-conditions
for bad in ("upload.wikimedia.org", 'class="thumb tright"', "thumbinner", "thumbcaption",
            "magnify", "thumbimage", "Barcoded rolling stock in the UK, 1962"):
    if bad in new:
        print("ABORT: %r survived the removal" % bad)
        sys.exit(1)
# every working wikipedia article citation must survive untouched
before_links = re.findall(r'href="(https://en\.wikipedia\.org/wiki/[^"]+)"', content)
after_links = re.findall(r'href="(https://en\.wikipedia\.org/wiki/[^"]+)"', new)
removed = [l for l in before_links if l not in after_links]
print("en.wikipedia.org citations: %d -> %d" % (len(before_links), len(after_links)))
print("removed citations: %s" % (removed or "none"))
if any("File:" not in l for l in removed):
    print("ABORT: removed a citation that was not the dead File: link")
    sys.exit(1)

before_idx = snapshot()
print("indexable before: %s" % before_idx.strip()[:190])

open("/tmp/16871_after.html", "w", encoding="utf-8").write(new)
print(wp("eval",
         "$c=file_get_contents('/tmp/16871_after.html');"
         "$r=wp_update_post(array('ID'=>%s,'post_content'=>wp_slash($c)),true);"
         "echo is_wp_error($r)?('ERR '.$r->get_error_message()):('OK '.$r);" % POST))

after = wp("post", "get", POST, "--field=post_content")
print("content sha after : %s (%d bytes)" % (hashlib.sha256(after.encode()).hexdigest()[:16], len(after)))
print("upload.wikimedia.org occurrences after: %d" % after.count("upload.wikimedia.org"))
if after.rstrip("\n") != new.rstrip("\n"):
    print("WARNING: stored content differs from what was submitted (slash handling?)")
after_idx = snapshot()
print("indexable after : %s" % after_idx.strip()[:190])
print("INDEXABLE UNCHANGED" if before_idx == after_idx else "*** INDEXABLE MOVED - INSPECT ***")

#!/usr/bin/env python3
"""Phase 13 — enumerate every skipped heading level across the estate's sitemap URLs.

Records, per offending page: the full heading sequence, the exact offending jump, the heading
text, and whether the offender sits inside the article body (content) or outside it (template).
That split is what decides where the fix belongs — one template edit versus N content edits.
"""
import json, re, sys, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
TAG = re.compile(rb"<(h[1-6])\b[^>]*>(.*?)</\1>", re.I | re.S)
STRIP = re.compile(rb"<[^>]+>")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read()


def sitemap_urls(root):
    """All <loc> URLs from a sitemap index, one level deep."""
    out = []
    try:
        top = fetch(root)
    except Exception as e:
        print(f"  ! {root}: {e}", file=sys.stderr)
        return out
    locs = re.findall(rb"<loc>(.*?)</loc>", top)
    children = [l.decode() for l in locs if l.decode().endswith(".xml")]
    if not children:
        return [l.decode() for l in locs]
    for c in children:
        try:
            for l in re.findall(rb"<loc>(.*?)</loc>", fetch(c)):
                u = l.decode()
                if not u.endswith(".xml"):
                    out.append(u)
        except Exception:
            pass
    return out


def analyse(url):
    try:
        html = fetch(url)
    except Exception as e:
        return {"url": url, "error": str(e)[:80]}
    heads = [(m.group(1).decode().lower(),
              STRIP.sub(b" ", m.group(2)).decode("utf-8", "replace").strip()[:60],
              m.start())
             for m in TAG.finditer(html)]
    if not heads:
        return None
    # Where does the article body start/end? Used to attribute an offender to
    # template furniture vs authored content.
    body_start = body_end = None
    for pat in (rb'<div[^>]*class="[^"]*entry-content', rb'<div[^>]*class="[^"]*post-content',
                rb'<article\b', rb'<main\b'):
        m = re.search(pat, html, re.I)
        if m:
            body_start = m.start()
            break
    m = re.search(rb'<footer\b', html, re.I)
    body_end = m.start() if m else len(html)

    skips = []
    prev = None
    for lvl, txt, pos in heads:
        n = int(lvl[1])
        if prev is not None and n > prev + 1:
            where = "content" if (body_start is not None and body_start <= pos < body_end) else "template"
            skips.append({"from": f"h{prev}", "to": lvl, "text": txt, "where": where})
        prev = n
    if not skips:
        return None
    return {"url": url, "sequence": " ".join(h[0] for h in heads[:40]),
            "skips": skips, "n_headings": len(heads)}


SITES = {
    "ambimat": "https://ambimat.com/sitemap_index.xml",
    "orders": "https://orders.ambimat.com/wp-sitemap.xml",
}

results = {}
for slug, sm in SITES.items():
    urls = sitemap_urls(sm)
    print(f"{slug}: {len(urls)} sitemap URLs", file=sys.stderr)
    found = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(analyse, urls):
            if r and "skips" in r:
                found.append(r)
    results[slug] = found
    print(f"{slug}: {len(found)} pages with skipped headings", file=sys.stderr)

json.dump(results, open(sys.argv[1], "w"), indent=1)

for slug, found in results.items():
    print(f"\n===== {slug}: {len(found)} pages =====")
    from collections import Counter
    c = Counter()
    for f in found:
        for s in f["skips"]:
            c[(s["from"], s["to"], s["where"])] += 1
    for (a, b, w), n in c.most_common():
        print(f"  {n:4d}  {a} -> {b}   ({w})")

#!/usr/bin/env python3
"""Phase 15 — objective, deterministic accessibility checks across the estate.

Only things that are true or false from the served HTML: heading hierarchy, exactly one H1,
image alt presence, iframe accessible names, form-control labels, link/button accessible
names, and landmark presence. No judgement calls, no visual review.
"""
import json, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")


def fetch(u):
    return urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45).read().decode("utf-8", "replace")


def audit(url):
    try:
        h = fetch(url)
    except Exception as e:
        return {"url": url, "error": str(e)[:70]}
    issues = []

    heads = [(m.group(1).lower(), m.start()) for m in re.finditer(r"<(h[1-6])\b", h, re.I)]
    h1n = sum(1 for t, _ in heads if t == "h1")
    if h1n == 0:
        issues.append("no H1")
    elif h1n > 1:
        issues.append(f"{h1n} H1s")
    prev = None
    for t, _ in heads:
        n = int(t[1])
        if prev is not None and n > prev + 1:
            issues.append(f"skip h{prev}->{t}")
        prev = n

    imgs = re.findall(r"<img\b[^>]*>", h, re.I)
    noalt = [i for i in imgs if not re.search(r'\balt\s*=', i, re.I)]
    if noalt:
        issues.append(f"{len(noalt)}/{len(imgs)} img without alt")

    frames = re.findall(r"<iframe\b[^>]*>", h, re.I)
    noname = [f for f in frames
              if not re.search(r'\b(title|aria-label)\s*=', f, re.I)]
    if noname:
        issues.append(f"{len(noname)}/{len(frames)} iframe without title")

    # form controls that need a name
    ctrls = re.findall(r"<(input|select|textarea)\b[^>]*>", h, re.I)
    unlabelled = 0
    for c in re.finditer(r"<(input|select|textarea)\b([^>]*)>", h, re.I):
        attrs = c.group(2)
        typ = (re.search(r'type\s*=\s*"([^"]*)"', attrs, re.I) or [None, ""])[1].lower()
        if typ in ("hidden", "submit", "button", "image", "reset"):
            continue
        has_name = re.search(r'\b(aria-label|aria-labelledby|title|placeholder)\s*=', attrs, re.I)
        idm = re.search(r'\bid\s*=\s*"([^"]+)"', attrs, re.I)
        has_for = idm and re.search(r'<label\b[^>]*\bfor\s*=\s*"%s"' % re.escape(idm.group(1)), h, re.I)
        if not (has_name or has_for):
            unlabelled += 1
    if unlabelled:
        issues.append(f"{unlabelled} unlabelled form control(s)")

    # links whose entire content is an image with no alt, or which are empty
    empty_links = 0
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", h, re.I | re.S):
        attrs, inner = m.group(1), m.group(2)
        if re.search(r'\b(aria-label|aria-labelledby|title)\s*=', attrs, re.I):
            continue
        text = re.sub(r"<[^>]+>", "", inner).strip()
        if text:
            continue
        imgs_in = re.findall(r"<img\b[^>]*>", inner, re.I)
        if imgs_in and all(re.search(r'\balt\s*=\s*"\s*"', i, re.I) or not re.search(r'\balt\s*=', i, re.I)
                           for i in imgs_in):
            empty_links += 1
        elif not imgs_in and not re.search(r"<(svg|i|span)\b", inner, re.I):
            empty_links += 1
    if empty_links:
        issues.append(f"{empty_links} link(s) with no accessible name")

    if not re.search(r"<main\b|role\s*=\s*\"main\"", h, re.I):
        issues.append("no <main> landmark")
    if not re.search(r"<html[^>]*\blang\s*=", h, re.I):
        issues.append("no html lang")

    return {"url": url, "issues": issues, "headings": len(heads), "images": len(imgs)}


URLS = json.load(open(sys.argv[1]))
res = []
with ThreadPoolExecutor(max_workers=6) as ex:
    for r in ex.map(audit, URLS):
        res.append(r)
json.dump(res, open(sys.argv[2], "w"), indent=1)

import collections
c = collections.Counter()
for r in res:
    for i in r.get("issues", []):
        c[re.sub(r"^\d+", "N", re.sub(r"h\d->h\d", "hN->hM", i))] += 1
clean = sum(1 for r in res if not r.get("issues") and not r.get("error"))
print(f"pages audited: {len(res)}   fully clean: {clean}")
for k, v in c.most_common():
    print(f"  {v:4d}  {k}")

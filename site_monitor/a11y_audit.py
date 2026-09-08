#!/usr/bin/env python3
"""Objective, deterministic accessibility checks across the estate.

Only things that are true or false from the served HTML: heading hierarchy, exactly one H1,
image alt presence, iframe accessible names, form-control labels, link/button accessible
names, and landmark presence. No judgement calls, no visual review.

2026-09-08 — the first version of this script was regex-only and reported 13 unlabelled form
controls on ambimat.com/contact/. Every single one was a false positive, in three ways:

  * It only looked for <label for="id">. The HTML spec gives a control its name from a
    WRAPPING <label> too, and that is exactly what the theme and Contact Form 7 emit:
        <label class="radio-inline"><input type="radio" id="Vendors"><span>Vendor</span></label>
        <label><input type="checkbox" name="PCB-Types[]"><span>Flexible PCBs</span></label>
    Five radios and four checkboxes, all correctly named, all reported as defects.

  * It counted controls inside <noscript>. The four reCAPTCHA fallback iframes only exist for
    a visitor with JavaScript disabled and are never in the accessibility tree otherwise.

  * It counted controls inside a display:none subtree. The remaining four were Akismet's
    honeypot textareas in <p style="display: none !important;" class="akismet-fields-container">.
    Those must NOT be given a real label - naming a honeypot is how you tell a spam bot which
    field to skip.

So the rule was wrong three times over on one page, and "13 unlabelled controls" was 13 - 13.
This version parses the document instead of pattern-matching it, tracking open elements so a
wrapping label, a <noscript> and a hidden subtree can each be recognised for what they are.

The checks it applies are unchanged in strictness: a control with no name from ANY of
label[for], a wrapping label, aria-label, aria-labelledby or title is still a defect, and
placeholder is deliberately NOT accepted on its own.
"""
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}
SKIP_INPUT_TYPES = {"hidden", "submit", "button", "image", "reset"}
# A subtree the browser never paints is a subtree the accessibility tree never sees.
HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)


class A11yParser(HTMLParser):
    """Single pass over the document, tracking just enough element context to answer:
    is this control inside a <label>? inside <noscript>? inside something hidden?"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []              # (tag, attrs dict)
        self.headings = []           # (level, text)
        self._heading = None         # (level, [text parts])
        self.images = []             # attrs
        self.iframes = []            # attrs
        self.controls = []           # (tag, attrs, in_label, hidden, in_noscript)
        self.labels_for = set()      # ids named by a label's for=
        self.links = []              # (attrs, inner_text, img_attrs, has_child_elements)
        self._link = None
        self.has_main = False
        self.html_lang = False

    # -- helpers
    def _hidden_depth(self):
        for _tag, a in self.stack:
            if "hidden" in a or a.get("aria-hidden") == "true":
                return True
            if HIDDEN_STYLE.search(a.get("style") or ""):
                return True
        return False

    def _in(self, tag):
        return any(t == tag for t, _ in self.stack)

    # -- parser callbacks
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag == "html" and "lang" in a:
            self.html_lang = True
        if tag == "main" or a.get("role") == "main":
            self.has_main = True
        if tag == "label" and a.get("for"):
            self.labels_for.add(a["for"])
        if tag == "img":
            self.images.append(a)
        if tag == "iframe":
            self.iframes.append((a, self._in("noscript")))
        if tag in ("input", "select", "textarea"):
            self.controls.append((tag, a, self._in("label"), self._hidden_depth(),
                                  self._in("noscript")))
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = (int(tag[1]), [], self._hidden_depth() or self._in("noscript"))
        if tag == "a":
            self._link = (a, [], [], False)
        elif self._link is not None and tag not in ("br", "wbr"):
            if tag == "img":
                self._link[2].append(a)
            self._link = (self._link[0], self._link[1], self._link[2], True)
        if tag not in VOID:
            self.stack.append((tag, a))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag) and self._heading:
            self.headings.append((self._heading[0], "".join(self._heading[1]).strip(),
                                  self._heading[2]))
            self._heading = None
        if tag == "a" and self._link is not None:
            self.links.append(self._link)
            self._link = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self._heading:
            self._heading[1].append(data)
        if self._link is not None:
            self._link[1].append(data)


def named(attrs, labels_for, in_label):
    """Does this control have an accessible name? placeholder alone deliberately does not count."""
    if attrs.get("aria-label", "").strip() or attrs.get("aria-labelledby", "").strip():
        return True
    if attrs.get("title", "").strip():
        return True
    if attrs.get("id") and attrs["id"] in labels_for:
        return True
    return in_label


def audit_html(html):
    p = A11yParser()
    p.feed(html)
    issues = []

    # A heading the browser never paints is not part of the outline anyone is given, so it is
    # not counted — the same rule already applied to form controls and to <noscript>.
    #
    # 2026-09-08: orders.ambimat.com/contact/ reported an h2->h5 skip for four labels sitting
    # inside <div class="col-sm-5 col-xs-12 form-section" style="display:none"> — a leftover
    # form block that renders at NO viewport (measured: offsetParent null, 0x0 box, document
    # height unchanged with and without them).
    #
    # Deliberately keyed on INLINE hiding only (style/hidden/aria-hidden on an ancestor), never
    # on a CSS class. ambimat.com/careers/ hides 29 job-field headings behind .tab-pane, which
    # JavaScript reveals when a visitor opens that job — those are real headings a real reader
    # meets, and they must keep being checked.
    live = [h for h in p.headings if not h[2]]
    inert = len(p.headings) - len(live)

    h1s = [h for h in live if h[0] == 1]
    if not h1s:
        issues.append("no H1")
    elif len(h1s) > 1:
        issues.append("%d H1s" % len(h1s))
    prev = None
    for lvl, _text, _inert in live:
        if prev is not None and lvl > prev + 1:
            issues.append("skip h%d->h%d" % (prev, lvl))
        prev = lvl

    noalt = [i for i in p.images if "alt" not in i]
    if noalt:
        issues.append("%d/%d img without alt" % (len(noalt), len(p.images)))

    # <noscript> iframes are vendor fallback markup a JS-enabled visitor never renders.
    visible_frames = [a for a, in_ns in p.iframes if not in_ns]
    unnamed_frames = [a for a in visible_frames
                      if not (a.get("title", "").strip() or a.get("aria-label", "").strip())]
    if unnamed_frames:
        issues.append("%d/%d iframe without title" % (len(unnamed_frames), len(visible_frames)))

    unlabelled = 0
    for tag, a, in_label, hidden, in_noscript in p.controls:
        if tag == "input" and a.get("type", "").lower() in SKIP_INPUT_TYPES:
            continue
        if hidden or in_noscript:
            continue
        if not named(a, p.labels_for, in_label):
            unlabelled += 1
    if unlabelled:
        issues.append("%d unlabelled form control(s)" % unlabelled)

    empty_links = 0
    for a, text_parts, imgs, had_children in p.links:
        if any(a.get(k, "").strip() for k in ("aria-label", "aria-labelledby", "title")):
            continue
        if "".join(text_parts).strip():
            continue
        if imgs:
            if all(not i.get("alt", "").strip() for i in imgs):
                empty_links += 1
        elif not had_children:
            empty_links += 1
    if empty_links:
        issues.append("%d link(s) with no accessible name" % empty_links)

    if not p.has_main:
        issues.append("no <main> landmark")
    if not p.html_lang:
        issues.append("no html lang")

    return {"issues": issues, "headings": len(live), "headings_inert": inert,
            "images": len(p.images)}


def audit(url):
    try:
        html = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}),
            timeout=45).read().decode("utf-8", "replace")
    except Exception as e:
        return {"url": url, "error": str(e)[:70]}
    r = audit_html(html)
    r["url"] = url
    return r


def main():
    urls = json.load(open(sys.argv[1]))
    res = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(audit, urls):
            res.append(r)
    if len(sys.argv) > 2:
        json.dump(res, open(sys.argv[2], "w"), indent=1)

    import collections
    c = collections.Counter()
    for r in res:
        for i in r.get("issues", []):
            c[re.sub(r"^\d+", "N", re.sub(r"h\d->h\d", "hN->hM", i))] += 1
    clean = sum(1 for r in res if not r.get("issues") and not r.get("error"))
    print("pages audited: %d   fully clean: %d" % (len(res), clean))
    for k, v in c.most_common():
        print("  %4d  %s" % (v, k))
    for r in res:
        if r.get("issues"):
            print("\n%s" % r["url"])
            for i in r["issues"]:
                print("    %s" % i)
        elif r.get("error"):
            print("\n%s\n    ERROR %s" % (r["url"], r["error"]))


if __name__ == "__main__":
    main()

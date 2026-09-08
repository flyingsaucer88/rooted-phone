#!/usr/bin/env python3
"""Regression: the accessibility checks must not invent defects, and must not lose real ones.

2026-09-08 — the audit reported "13 unlabelled form control(s)" on ambimat.com/contact/.
All 13 were false positives and the rule was wrong three separate ways. Each fixture below is
the real markup from that page, paired with the genuine defect the same rule still has to
catch, so a future simplification cannot quietly re-open any of them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from a11y_audit import audit_html  # noqa: E402

failures = 0


def issues(html):
    return audit_html("<html lang='en'><body><main><h1>T</h1>%s</main></body></html>" % html)["issues"]


def check(name, got, want):
    global failures
    if got == want:
        print("PASS %s" % name)
    else:
        failures += 1
        print("FAIL %s\n     -> got %r, want %r" % (name, got, want))


def count(html, needle="unlabelled"):
    return sum(1 for i in issues(html) if needle in i)


# ---------------------------------------------------------------- wrapping <label>
# The theme's inquiry-type switcher, verbatim.
RADIOS = "".join(
    '<label class="radio-inline pmd-radio pmd-radio-ripple-effect">'
    '<input type="radio" name="inlineRadioOptions" id="%s" value="%s" class="form-switcher">'
    '<span for="%s">%s</span></label>' % (i, i, i, t)
    for i, t in [("Vendors", "Vendor"), ("NewClient", "New Client"),
                 ("SupportRequest", "Support Request"), ("JobSeeker", "JobSeeker"),
                 ("DistributorRequest", "Distributor Request")])
check("5 wrapped radios are named, not defects", count(RADIOS), 0)

# Contact Form 7's checkbox list, verbatim.
CHECKS = "".join(
    '<span class="wpcf7-list-item"><label>'
    '<input type="checkbox" name="PCB-Types[]" value="%s" />'
    '<span class="wpcf7-list-item-label">%s</span></label></span>' % (v, v)
    for v in ["Flexible PCBs", "Rigid PCBs", "Flexi-Rigid PCBs", "Multi-layer PCBs"])
check("4 wrapped CF7 checkboxes are named", count(CHECKS), 0)

# ...and the defect the same rule must still catch: the identical control, unwrapped.
check("a bare radio with no label at all IS a defect",
      count('<input type="radio" name="x" id="y" value="y"><span>Vendor</span>'), 1)
check("a bare checkbox with only a sibling span IS a defect",
      count('<input type="checkbox" name="p[]"><span>Flexible PCBs</span>'), 1)

# ---------------------------------------------------------------- <noscript>
NOSCRIPT = ('<noscript><div class="grecaptcha-noscript">'
            '<iframe src="https://www.google.com/recaptcha/api/fallback?k=K" '
            'frameborder="0" scrolling="no" width="310" height="430"></iframe>'
            '<textarea name="g-recaptcha-response" rows="3" cols="40"></textarea>'
            '</div></noscript>')
check("a control inside <noscript> is not counted", count(NOSCRIPT), 0)
check("an iframe inside <noscript> is not counted", count(NOSCRIPT, "iframe"), 0)
# The genuine version: the same iframe, actually rendered.
check("an untitled iframe OUTSIDE noscript is still a defect",
      count('<iframe src="https://maps.google.com/maps?q=x"></iframe>', "iframe"), 1)
check("  and a titled one is not",
      count('<iframe title="Office location" src="https://maps.google.com/maps?q=x"></iframe>',
            "iframe"), 0)

# ---------------------------------------------------------------- hidden subtrees
HONEYPOT = ('<p style="display: none !important;" class="akismet-fields-container" '
            'data-prefix="_wpcf7_ak_"><label>&#916;<textarea name="_wpcf7_ak_hp_textarea" '
            'cols="45" rows="8" maxlength="100"></textarea></label></p>')
check("Akismet's display:none honeypot is not a defect", count(HONEYPOT), 0)
check("a control under [hidden] is not a defect",
      count('<div hidden><input type="text" name="x"></div>'), 0)
check("a control under aria-hidden is not a defect",
      count('<div aria-hidden="true"><input type="text" name="x"></div>'), 0)
# The genuine version: same control, visible.
check("the SAME textarea when visible IS a defect",
      count('<p class="fields"><textarea name="message" cols="45" rows="8"></textarea></p>'), 1)

# ---------------------------------------------------------------- naming methods
check("label[for] still names a control",
      count('<label for="a">Name</label><input type="text" id="a">'), 0)
check("aria-label still names a control", count('<input type="text" aria-label="Search">'), 0)
check("aria-labelledby still names a control",
      count('<span id="l">Search</span><input type="text" aria-labelledby="l">'), 0)
check("title still names a control", count('<input type="text" title="Search">'), 0)
check("placeholder alone is STILL not an accessible name",
      count('<input type="text" placeholder="Your email">'), 1)
check("an empty aria-label is not a name", count('<input type="text" aria-label="  ">'), 1)
check("hidden/submit/button/reset inputs are never counted",
      count('<input type="hidden" name="a"><input type="submit" value="Send">'
            '<input type="button" value="X"><input type="reset" value="R">'), 0)

# ---------------------------------------------------------------- landmarks, headings, links
def raw(html):
    return audit_html(html)["issues"]


check("no <main> is reported",
      "no <main> landmark" in raw("<html lang='en'><body><h1>T</h1></body></html>"), True)
check("<main> satisfies the landmark check",
      "no <main> landmark" in raw("<html lang='en'><body><main><h1>T</h1></main></body></html>"),
      False)
check('role="main" also satisfies it',
      "no <main> landmark" in raw('<html lang="en"><body><div role="main"><h1>T</h1></div></body></html>'),
      False)
check("a heading skip is still reported", issues("<h2>a</h2><h4>b</h4>"), ["skip h2->h4"])
check("a contiguous sequence is not", issues("<h2>a</h2><h3>b</h3><h2>c</h2>"), [])
check("two H1s are still reported", "2 H1s" in raw(
    "<html lang='en'><body><main><h1>a</h1><h1>b</h1></main></body></html>"), True)
check("the empty map-generator anchor is still a defect",
      count('<a href="https://google-map-generator.com"></a>', "no accessible name"), 1)
check("an anchor with text is not", count('<a href="/x">Read more</a>', "no accessible name"), 0)
check("an image link with alt is not",
      count('<a href="/x"><img src="a.png" alt="Product"></a>', "no accessible name"), 0)
check("an image link with empty alt IS a defect",
      count('<a href="/x"><img src="a.png" alt=""></a>', "no accessible name"), 1)
check("an icon-only link with aria-label is not",
      count('<a href="/x" aria-label="Search"><i class="material-icons">search</i></a>',
            "no accessible name"), 0)
check("missing img alt is still reported",
      count('<img src="a.png">', "img without alt"), 1)
check("html lang is still checked",
      "no html lang" in raw("<html><body><main><h1>T</h1></main></body></html>"), True)

# ---------------------------------------------------------------- the whole contact page shape
CONTACT = RADIOS + CHECKS + NOSCRIPT * 4 + HONEYPOT * 4
check("the real /contact/ control set reports ZERO unlabelled controls (was 13)",
      count(CONTACT), 0)
check("  and one genuinely unnamed control added to it is still found",
      count(CONTACT + '<input type="text" name="orphan">'), 1)

# ---------------------------------------------------------------- inert headings
# A heading the browser never paints is not in anyone's outline. But "hidden" has to mean
# hidden, not "hidden right now" — a tab panel is display:none until its tab is opened, and
# those headings are read by real people.
ORDERS_DEAD_BLOCK = ('<h2>Contact Details</h2>'
                     '<div class="col-sm-5 col-xs-12 form-section" style="display:none">'
                     '<div class="media-body"><h5>Works</h5></div>'
                     '<div class="media-body"><h5>Local Inquiry</h5></div></div>')
check("headings inside an inline display:none block are not counted",
      issues(ORDERS_DEAD_BLOCK), [])
check("  nor do they leave a phantom H1 problem",
      audit_html("<html lang='en'><body><main><h1>T</h1>" + ORDERS_DEAD_BLOCK
                 + "</main></body></html>")["issues"], [])
check("headings under [hidden] are not counted",
      issues('<h2>S</h2><div hidden><h5>Label</h5></div>'), [])
check("headings under aria-hidden are not counted",
      issues('<h2>S</h2><div aria-hidden="true"><h5>Label</h5></div>'), [])
check("visibility:hidden counts as inert too",
      issues('<h2>S</h2><div style="visibility:hidden"><h5>L</h5></div>'), [])

# The careers page: 29 job-field headings hidden by a CSS CLASS that JS reveals. These are
# real headings a real reader meets, and the skip they cause must still be reported.
CAREERS_TABS = ('<h2>JOIN US</h2>'
                '<div class="tab-pane" id="job1" role="tabpanel" aria-labelledby="tab1">'
                '<div class="panel-body"><h5>Job Description</h5><h5>Skill Required</h5></div></div>')
check("a heading hidden only by a CSS class IS still counted",
      issues(CAREERS_TABS), ["skip h2->h5"])
check("  and once promoted to h3 it passes",
      issues(CAREERS_TABS.replace("<h5>", "<h3>").replace("</h5>", "</h3>")), [])

# Inert headings must not be silently discarded from the record either.
r = audit_html("<html lang='en'><body><main><h1>T</h1><h2>S</h2>"
               '<div style="display:none"><h5>X</h5></div></main></body></html>')
check("the inert count is reported, not hidden", (r["headings"], r["headings_inert"]), (2, 1))

# A real defect on visible content is still found next to an inert block.
check("an inert block cannot mask a real skip elsewhere",
      issues('<h2>A</h2><div style="display:none"><h5>hidden</h5></div><h4>visible</h4>'),
      ["skip h2->h4"])

print()
print("%s: %d failed" % ("FAILURES" if failures else "all assertions passed", failures))
sys.exit(1 if failures else 0)

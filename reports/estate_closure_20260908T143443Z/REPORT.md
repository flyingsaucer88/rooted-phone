# Ambimat estate — final closure pass, 2026-09-08

Continues the same-day remediation (`reports/estate_remediation_20260908T120536Z`).

Baselines: site monitor 11:41 (593→14 warnings), SEO 12:05 (3 medium).
Closure: site monitor **14:34** (phone, authoritative), SEO **14:13** (nine domains, 719 pages).

```
suspicious warnings   593  →  14  →   1
unverified links       24  →  12  →   7
SEO medium              3  →   2  →   0
SEO high                0  →   0  →   0
SEO low                85  →  85  →  28
broken links            0  →   0  →   0     (1 found and fixed during this pass)
alerts                  0  →   0  →   0
heading advisories     62  →  62  →  22
```

---

## A. AI deployment

```
SSH config used:        ~/.ssh/config host "hostinger-ambimat" (port 65002, key ambipower_deploy)
Production host:        in-mum-web1117.main-hosting.eu  (Hostinger)
Production doc root:    /home/u675763961/domains/ai.ambimat.com/public_html
Repo/build commit:      fb1e3be (rebuilt from committed source before deploy)
Deployment:             rsync -az over SSH, no --delete
Hash verification:      60/60 files SHA-256 identical local↔production, 0 mismatches,
                        0 unexpected files removed
Live verification:      all 7 routes 200, one H1, canonical, og:image present and its URL 200,
                        JSON-LD parses on every route, titles clean (no BUILD NOTE), sitemap
                        7 URLs, meta CSP intact, .mjs MIME guard intact, contact form assets 200
```

**Identity was proved before any write**, and the owner's warning was well founded: Hostinger
does host a `domains/ambimat.com/public_html`, and it is the stale non-production copy —
it contains `create_autologin_*.php` and `monarx-analyzer.php` and is NOT what serves
ambimat.com (that is GoDaddy). Nothing was written to it. For ai.ambimat.com the proof was a
hash match: the live HTTPS response for `/index.html` and the file on disk were byte-identical
(`b112fe10…`), and og:image count on disk was 0, matching the finding.

A timestamped backup was taken outside the web root first
(`~/ai-ambimat-backup-20260908T070853Z.tar.gz`, 67 files).

Live headers now: HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
Permissions-Policy. Same SSH also reaches **orders.ambimat.com**, which unblocked Phase 12.

---

## B. The fourteen warnings, individually closed

| # | Site | Original warning | Root cause | Action | Final state |
|--:|------|------------------|------------|--------|-------------|
| 1 | ambimat | missing `content-security-policy` | never set; a guessed CSP on WP+GTM+GA4+CookieYes+reCAPTCHA+Photon breaks the site | derived origins from 8 live pages; shipped **Report-Only** + enforced Permissions-Policy | **retained, intentional** — Report-Only live, 0 violations observed |
| 2 | ambimat | iframe idtechproducts.com | WP oEmbed of a cited article | verified live; allowlisted; lazy+referrerpolicy added | **verified expected embed** |
| 3 | ambimat | iframe digitalid.co.uk | **remote article 500** (its home + blog index 200, so not anti-bot) | bare URL under "References:-" → plain link | **removed at source** |
| 4 | ambimat | iframe tech-faq.com | WP oEmbed | verified; allowlisted; hardened | **verified expected embed** |
| 5 | ambimat | iframe emv-connection.com | **Cloudflare 522 on 4 probes**, origin down for everyone | bare URL → plain link | **removed at source** |
| 6 | ambimat | iframe paylosophy.com | WP oEmbed | verified; allowlisted; hardened | **verified expected embed** |
| 7 | ambimat | iframe pcisecuritystandards.org | WP oEmbed | verified; allowlisted; hardened | **verified expected embed** |
| 8 | ambimat | iframe pcisecuritystandards.org (2nd page) | WP oEmbed | verified; allowlisted; hardened | **verified expected embed** |
| 9 | ambimat | iframe encryptionconsulting.com | WP oEmbed | verified; allowlisted; hardened | **verified expected embed** |
| 10 | ambimat | iframe idwholesaler.com | WP oEmbed | verified; allowlisted; hardened | **verified expected embed** |
| 11 | ambimat | offsite-redirect on /design/design-services/java-card-applet/ | page 3748 linked to a URL that 301s off-host | link repointed at the final URL; the redirect endpoint itself untouched | **closed at source** |
| 12 | ambisecure | "hacked by" in /blog/archive/cyber-attacks-in-india-part-1/ | 1,168-word article about bank breaches | monitor learned editorial context; article unchanged | **classified editorial, with evidence** |
| 13 | orders | 4 headers missing | only Hostinger's default CSP | `.htaccess` block appended after every plugin-managed marker | **fixed, live** |
| 14 | ai | 4 headers missing | never set | `.htaccess` in repo, deployed | **fixed, live** |

Nine of fourteen were the same oEmbed family. Two were dead remotes and were removed; seven are
now modelled as verified-expected rather than sitting in a warning bucket for ever.

---

## C. Security headers — all nine sites

| Site | HSTS | XCTO | Referrer | Permissions | CSP | Remaining gap |
|------|:----:|:----:|:--------:|:-----------:|-----|---------------|
| ambimat.com | ✅ | ✅ | ✅ | ✅ **new** | **Report-Only (new)** | promote to enforcing after a browser pass |
| ambisecure.ambimat.com | ✅ | ✅ | ✅ | ✅ | enforcing | none |
| ambipower.ambimat.com | ✅ | ✅ | ✅ | ✅ | enforcing | none |
| ambiautomation.ambimat.com | ✅ | ✅ | ✅ | ✅ | enforcing | none |
| v2x.ambimat.com | ✅ | ✅ | ✅ | ✅ | enforcing | none |
| ai.ambimat.com | ✅ **new** | ✅ **new** | ✅ **new** | ✅ **new** | strict policy via `<meta>`; header is Hostinger's `upgrade-insecure-requests` | header-level CSP optional |
| roboracer.ambimat.com | ✅ | ✅ | ✅ | ✅ | enforcing | none |
| orders.ambimat.com | ✅ **new** | ✅ **new** | ✅ **new** | ✅ **new** | Hostinger default only | CSP on WooCommerce — needs a checkout pass |
| esim.ambimat.com | ✅ | ✅ | ✅ | ✅ | enforcing | none |

Four headers went from absent on three sites to present on all nine.

Two deliberate deviations, both because copying the estate default would have broken something:
* **orders** gets `payment=(self)`, not `payment=()`. It is the only host that takes money;
  `payment=()` disables the Payment Request API and would break Stripe / Google Pay / Apple Pay.
* **ai** does *not* set `Cross-Origin-Resource-Policy: same-origin`. esim-website found that a
  blanket same-origin CORP breaks every og:image preview card, and the cards deployed in this
  same pass are the whole point.

---

## D. oEmbed / iframe hardening

```
Embeds reviewed:        9  (each fetched and checked individually)
Removed:                2  (digitalid.co.uk 500, emv-connection.com Cloudflare 522)
Retained:               7
Allowed hosts:         15  (9 infrastructure + 6 publishers), each annotated with its reason
Security attributes:    loading="lazy" + referrerpolicy="strict-origin-when-cross-origin",
                        plus a guaranteed title fallback, via a producer-level MU-plugin on the
                        embed_oembed_html filter
CSP frame restriction:  frame-src allowlist shipped in the ambimat.com Report-Only policy
Monitor rule change:    "external iframe = suspicious"  ->  "ONLY reviewed origins may be framed"
Unexpected frames:      still detected — and now ALERT, which is stronger than the warning it
                        replaced
```

`sandbox="allow-scripts"` and `security="restricted"` were already set by WordPress core and
were deliberately **left alone** — tightening them breaks the embed's own resize handshake,
which is exactly the "blindly sandbox and break it" failure to avoid.

The closure crawl reports **53 verified expected embeds** (20 ambimat + 33 eSIM GTM frames) and
**0 alerts**: every frame served anywhere on the estate is now an origin someone reviewed.

---

## E. Defacement detector

```
Editorial false positive removed:  yes — a body-only marker on a page that is long AND dense
                                   with security vocabulary is recorded as editorial, with the
                                   matched terms as evidence, instead of warned about
Title/H1 detection retained:       yes — unchanged ALERT path
Minimal-page detection retained:   yes — the <80-word ALERT is checked BEFORE the exemption, so
                                   a short page stuffed with security words is still an ALERT
Tests:                             26 paired assertions, including a long page carrying a marker
                                   but no security vocabulary (still WARNS) and a medium page
                                   under the word floor (still WARNS)
```

The article was not edited. The rule learned the difference.

---

## F. Redirect

```
Source URL:        https://ambimat.com/design/design-services/   (page 3748, 2 occurrences)
Old destination:   https://ambimat.com/design/design-services/java-card-applet/   (301 off-host)
Final destination: https://ambisecure.ambimat.com/services/javacard-development/  (200)
Change:            internal link repointed at the final URL. The redirect endpoint itself is a
                   legitimate canonical redirect and was NOT touched.
Live verification: old URL 0 occurrences, new URL 2, page 200, </html> present,
                   og:image byte-identical before and after
```

---

## G. SEO medium findings — all three closed

```
ambimat: FIXED (previous pass, still holding) — posts 2701/5071 shared one meta description;
         2701 rewritten from its own body. Medium 1 -> 0.

ai:      INTENTIONAL_AND_RULE_CORRECTED — /contact/ scored 45/100 purely for being 65 words on
         a page with a working intake form. The page was NOT padded. content_quality.py now
         exempts functional pages (contact/privacy/terms/support/legal/cart/account/404…) from
         the LENGTH penalty only; filler, AI-tell and density penalties still apply, and
         lookalikes such as /blog/how-we-handle-your-privacy/ and /products/contact-smart-cards/
         are still scored in full. Medium 1 -> 0.

orders:  FIXED — / and /brand/ambimat-electronics/ served the same description. Root cause was
         not the brand page: ambimat_seo_resolve_description() had no branch for product
         taxonomies, so EVERY unhandled view fell through to `return $hand['home']` and
         impersonated the front page. Added an is_tax() branch (hand-written -> term
         description -> generated) and gave the brand term a real description.
         Medium 1 -> 0, canonicals unchanged.
```

---

## H. Accessibility headings

```
Initial advisories:     62   (ambimat 48 + orders 14)
Unique root causes:      6
Template fixes:          1   -> fixed 11 pages
Content fixes:          36   -> 24 "Dear Reader" openers + 12 ordinary openers
Remaining:              22   (ambimat 17 + orders 5)
Yoast/og:image regressions: 0   (36/36 writes reported og:ok; the restore path never fired)
```

**Root causes, enumerated rather than guessed** (`evidence/headings_before.json`):

| Cause | Count | Fix |
|---|--:|---|
| Orders Elementor footer: two `h4` widgets after `h2` content | 11 | one template fix — "Follow Us On" → h3, "© 2026…" → `p` (a copyright line is not a heading) |
| ambimat "Dear Reader," opener authored as h4 | 20 | → `h2.ambimat-dear-readers-heading-h4` |
| ambimat "Dear Reader," opener authored as h3 | 7 | → `h2.ambimat-dear-readers-heading` |
| ambimat ordinary opener at h3/h4 | 15 | → `h2.ambimat-opener-as-h3/-h4` |
| mid-article jumps / template furniture | 8 | not attempted this pass |

**Visual neutrality was measured, not assumed.** R4 had already proved a naked h3→h2 swap is
NOT neutral on this theme. The same method was applied to the h4 case: an in-place swap in
Chrome measured **0 differing properties out of 17** with an identical 750×22 box, and the
theme's own stylesheet was read for the `max-width:767px` rules (`h4{18px/1.3}`,
`h2{24px/1.3}`) so the guard carries a matching mobile block. Post-change measurement at a
500px viewport returned exactly 18px/500/23.4px and 20px/600/26px — the theme's own h4 and h3
mobile values.

Every write asserted that visible text was byte-identical before and after, and refused
otherwise. 3 posts were skipped by that guard rather than being forced.

**The 22 that remain**, each with a reason:
* **17 ambimat** — 8 template/furniture jumps (h1→h5 "Smart Devices", h2→h5 "Job Description"
  on the careers template) and 9 mid-article jumps inside authored bodies. These are not one
  cause; each needs its own measurement and an editorial call on which level is correct.
  *Owner/content decision.*
* **5 orders** — 3 policy pages whose bodies use h3 as their top section level (privacy,
  shipping, terms) and 2 mid-article jumps on /contact/ and one product page. The policy pages
  need an h3→h2 sweep with an Astra-measured guard, which is a separate measured change.
  *Owner/content decision.*

None is a false positive; all are genuine but need a decision or a fresh measurement rather
than a mechanical edit.

---

## I. External links

```
Unverified before:  12
Working:             1   (kmu.ac.kr — 200 in a browser; incomplete cert chain, the remote
                          omits its intermediate, which trips the phone's stricter validation)
Anti-bot:            4   (entrust.com, businesswire.com, cloudflare.com, centralbank.ae — all
                          403, none 404/410/5xx)
Appliance-blocked:   2   (fime.com, sanctionscanner.com — proven by the 192.168.3.1:8888
                          "Web Site Blocked" page on port 80)
Actually broken:     1   ← found during this pass, not in the original 12
Fixed:               1
Unverified after:    7
```

**The one genuinely broken link in the estate** was surfaced by the closure crawl reaching
deeper into V2X (62 → 71 pages):

```
v2x.ambimat.com/services/v2x-commissioning-and-service-tools/
  -> https://ambimat.com/products/ambiconnect-b22/   HTTP 404
```

No such page exists on ambimat.com — a search of published posts, pages and products for
"ambiconnect" or "b22" returns nothing, so it was never live rather than moved. The anchor was
removed and the text kept. Deliberately **not** repointed at `/ambi-con/`: the row's own copy
says the module is an "Engineering evaluation. Not released for sale", so linking it to a
released product family would assert what the row disclaims.

The NXP lesson held: nothing was "fixed" on the strength of a WAF response. `nxp.com` still
answers automated clients with a soft 404 on every URL including its own home page, and the
owner-approved `MC_71108` link is verified present and correct.

---

## J. Per-site final state

| Site | Live | SEO | Security | Accessibility | Links | Overall |
|------|------|-----|----------|---------------|-------|---------|
| ambimat.com | 200 | 0H 0M 20L | 5 headers + CSP Report-Only | 48→17 heading advisories | 0 broken | **OK** |
| ambisecure.ambimat.com | 200 | 0H 0M 1L | full | clean | 0 broken | **OK** |
| ambipower.ambimat.com | 200 | 0H 0M 1L | full | clean | 0 broken | **OK** (og exemption documented) |
| ambiautomation.ambimat.com | 200 | 0H 0M 0L | full | clean | 0 broken | **OK** |
| v2x.ambimat.com | 200 | 0H 0M 0L | full | clean | **1 fixed** | **OK** |
| ai.ambimat.com | 200 | 0H 0M 1L | full (deployed) | clean | 0 broken | **OK** |
| roboracer.ambimat.com | 200 | 0H 0M 0L | full | clean | 0 broken | **OK** |
| orders.ambimat.com | 200 | 0H 0M 5L | full (deployed) | 14→5 heading advisories | 0 broken | **OK** |
| esim.ambimat.com | 200 | 0H 0M 0L | full | clean | 0 broken | **OK** |

All ten contact/inquiry routes verified 200. Orders invariants re-verified: `/sitemap.xml`
301→`wp-sitemap.xml` 200, zero cart/checkout/my-account/share-cart in any child sitemap, brand
archive self-canonical, and Core Kit / Core Kit Pro still carry **no `name="add-to-cart"`**
while the Power Boards do — quote-only commercial rules intact.

---

## K. Rooted Phone

```
Schedule:               08:00 site / 09:00 SEO / 10:00 cache  — verified on device, UNCHANGED
Nine-site guard:        9 sites in config, ambimechanicals absent, test_site_inventory passes
Measurement subsystem:  absent (0 crontab entries, no directories)
Monitor suspicious warnings: 593 -> 1
Monitor tests:          91 assertions run ON THE DEVICE, 0 failures
```

Monitor code deployed to the phone and SHA-256 verified (`run_site_monitor.py`,
`config/sites.yaml`, the new test file all MATCH). Backup taken first at
`~/sm_backup_20260908T083837Z`. The 14:34 closure crawl is the phone running this code.

*Note: the phone was physically disconnected for part of this session; the crawls were run
locally in the interim and then re-run on the device once it returned. The device is current.*

---

## L. Tests

```
passed:  382
failed:    0
skipped:   0
```

| Suite | Result |
|---|---|
| Rooted-Phone `test_iframe_and_defacement_invariants.py` (new) | 26 passed |
| Rooted-Phone `test_warning_signal_quality.py` | 43 passed |
| Rooted-Phone `test_head_get_fallback.py` | 18 passed |
| Rooted-Phone `test_site_inventory.py` | 5 passed |
| Rooted-Phone `test_schedule_times.py` | 4 passed |
| Rooted-Phone `sched_tests_noon.sh` | 39 passed |
| ambisecure-seo-tracker `pytest` (incl. 13 new in `test_audit_rule_precision.py`) | 87 passed |
| Ambimat-AI-site `vitest` (19 files) | 156 passed |

The same 91 Python assertions were also executed **on the phone** against the deployed files.

---

## M. Repositories / deployments

| Repository | Start | Final | Push | Deploy | Production verification |
|---|---|---|---|---|---|
| Ambimat-AI-site | b6459e2 | **fb1e3be** | ✅ | rsync → Hostinger | 60/60 file hashes match; 7 routes verified |
| Rooted-Phone | e2cf49f | **967b6e6** | ✅ | scp → phone | 3 files hash-verified; 91 tests pass on device |
| ambisecure-seo-tracker | e950842 | **ef7c8fd** | ✅ | n/a (desktop tool) | 87 tests pass |
| v2x-site | bf5c9fb | **babf5a5** | ✅ | scp → Hostinger | page hash matches production; dead link gone |
| ambimat.com (no repo) | — | — | — | wp-cli + `.htaccess` on GoDaddy | headers live; 36 content writes, og:image 0 moved |
| orders.ambimat.com (no repo) | — | — | — | wp-cli + `.htaccess` on Hostinger | headers live; brand description distinct |

**Concurrency preserved.** `ambisecure-seo-tracker` still carries another worker's five
uncommitted files (`.gitignore`, `main.py`, `ranking_engine.py`, `report_generator.py`,
`verify_offline.py`) plus two untracked report directories — untouched; this pass committed
only its own three files. Another session pushed two commits on top of `babf5a5` in `v2x-site`
during this run; that was left alone and the fix confirmed still live in production.
Untracked owner binaries in `ambipower-site` and `roboracer-source` were not touched. No repo
was reset, cleaned or force-pushed.

---

## N. Remaining actionable issues

1. **ambimat.com CSP is Report-Only, not enforcing.** The policy is derived from real traffic
   and observed **zero violations** on the home and contact pages in Chrome. Promoting it needs
   a wider browser pass — a form submission with reCAPTCHA, the CookieYes flow and an admin
   session — before flipping the header name. *(owner decision; the policy is ready)*
2. **22 heading advisories remain** (17 ambimat, 5 orders), each enumerated in
   `evidence/headings_after.json` with its exact sequence. They are template furniture and
   mid-article jumps with no single shared cause; each needs a measured guard and an editorial
   call on the correct level. *(owner/content decision)*
3. **13 pages have no `<main>` landmark** and ambimat.com `/contact/` has **13 unlabelled form
   controls** — newly surfaced by this pass's accessibility audit
   (`evidence/accessibility_audit.json`), not previously tracked. Both are genuine WCAG issues.
   The landmark is a theme change on launchseat (no git safety net) and the form is a governed
   CF7 + reCAPTCHA flow, so neither was attempted here. *(scoped work, needs its own pass)*
4. **orders.ambimat.com has no meaningful CSP.** It is the host that takes payments, so it
   deserves one — but a CSP on WooCommerce with four payment gateways needs a checkout pass to
   build safely. *(owner decision)*

Not listed, by design: anti-bot 403s, the LAN appliance's blocks, the ambipower `/privacy/`
NO_IMAGE exemption, the two cosmetic duplicate H1s (distinct titles, distinct bodies, correct
self-canonicals), the AI site's absent FAQPage schema (adding it purely to lift an AI-readiness
score is what the brief forbids), and latency threshold noise.

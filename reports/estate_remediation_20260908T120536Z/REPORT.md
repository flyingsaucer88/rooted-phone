# Ambimat estate — remediation of the 2026-09-08 monitoring findings

Baselines: site monitor `report_20260908_082633.json` (08:00), SEO tracker
`report_20260908_092245.json` (09:00).
Post-fix: site monitor `report_20260908_114141` (11:41), SEO tracker
`report_20260908_120536.json` (12:05).

---

## A. Findings reviewed

```
Total raw findings:                 705   (593 warnings + 24 unverified links + 88 SEO findings)
Unique finding classes:              30
TRUE_SITE_DEFECT:                    11
PERFORMANCE_OPPORTUNITY:              0   (every latency finding disproved as reproducible)
CONTENT/SEO_QUALITY_OPPORTUNITY:     67
EXPECTED_EXTERNAL_BEHAVIOR:          15
MONITOR_FALSE_POSITIVE:             602
TRANSIENT_NETWORK_EVENT:              6
INTENTIONAL_SITE_BEHAVIOR:            2
OWNER_DECISION_REQUIRED:              2
```

The headline number: **602 of 705 findings (85%) were the monitor being wrong**, and
512 of those came from a single rule substring-matching CSS against raw HTML.

---

## B. Per-site remediation

### 1. ambimat.com — 374 warnings, 1 medium, 60 low
* Genuine defects: **1** — posts 2701 and 5071 shared one meta description.
  The shared text is 5071's own opening paragraph, so 2701 ("Cellular Network based
  Wide Area Networks", actually about NB-IoT and LTE-M) was the page carrying the
  wrong one. Rewrote 2701's description from its own body text.
* Verification: `wp post meta update` + og:image gate (unchanged before/after),
  targeted W3TC page flush, live confirmation. Control page 5071 untouched.
* Monitor false positives: 346 suspicious-pattern, 22 external-iframe, 2
  japanese-spam, 2 suspicious-external-link, 9 slow-response.
* Retained intentional: CSP absent (owner decision, see C); the documented offsite
  301 to ambisecure; 9 oEmbed iframes of external publishers; 48 skipped heading
  levels (authored content, see K).

### 2. ambisecure.ambimat.com — 96 warnings, 0 medium, 2 low
* Genuine defects: **0**.
* The 08:00 `ConnectionResetError(104)` on `/resources/tools/key-diversification/`
  is a TRANSIENT_NETWORK_EVENT: 6 consecutive fetches returned HTTP 200, identical
  21212-byte bodies, TTFB 76–555 ms. No shell access to this Hostinger host, so
  server logs are unavailable; no reproducible defect exists from the client side.
  The monitor now performs one bounded retry for connection-level failures.
* `/blog/archive/` "3889 ms" is not reproducible: median 142 ms over 7 samples.
  The post-fix run flags two *different* pages and clears this one.
* Duplicate H1 with `/products/onepass-platform/` retained: distinct titles,
  distinct bodies (974 vs 1377 words), correct self-canonicals.

### 3. ambipower.ambimat.com — 1 warning, 1 low
* Genuine defects: **0**. `/privacy/` has no og:image **by documented decision** —
  `src/data/routes.mjs` records a "NO_IMAGE exception for legal/utility pages".
  Classified INTENTIONAL_SITE_BEHAVIOR. No change.

### 4. ambiautomation.ambimat.com — 2 warnings, 0 findings
* Genuine defects: **0**. Both warnings were the "owned by" and CSS rules.
  **NO CHANGE REQUIRED.**

### 5. v2x.ambimat.com — 0 warnings, 0 findings
* Genuine defects: **0**. The only observation is 5gaa.org, blocked by the local
  network appliance and verified live off-LAN. **NO CHANGE REQUIRED.**

### 6. ai.ambimat.com — 1 warning, 1 medium, 8 low
* Genuine defects: **2 classes** — og:image absent on all 7 indexable routes, and
  four security headers absent on every response.
* Fixed in repo (commit `b6459e2`): per-route 1200x630 cards via `scripts/gen-og.mjs`,
  `twitter:card` → `summary_large_image`, and X-Frame-Options / X-Content-Type-Options /
  Referrer-Policy / Strict-Transport-Security in `public/.htaccess`.
* **NOT YET LIVE** — this host deploys by manual hPanel upload; see J.
* Refused: adding FAQPage schema and padding `/contact/` purely to lift the
  AI-ready score. A contact page is legitimately short and the page carries a
  working form with a real fallback address.
* Title contamination remains fixed: no BUILD NOTE, no comment leakage, on all routes.

### 7. roboracer.ambimat.com — 0 warnings, 0 findings
* Genuine defects: **0**. Slack signup 403 is anti-bot (200 in a browser);
  `kmu.ac.kr` serves an incomplete certificate chain — a third-party server issue
  that browsers resolve via AIA fetching. Pricing, quote flow and absence of
  WooCommerce checkout all untouched. **NO CHANGE REQUIRED.**

### 8. orders.ambimat.com — 50 warnings, 1 medium, 14 low
* Genuine defects: **2**, both blocked — no shell and no admin session on this
  Hostinger WooCommerce install.
  1. `/` and `/brand/ambimat-electronics/` share one meta description.
  2. All four security headers absent (matters more here than anywhere: this host
     takes orders).
* Verified healthy and unchanged: `/sitemap.xml` 301 → `wp-sitemap.xml` 200, four
  child sitemaps, **zero** occurrences of cart / checkout / my-account / share-cart,
  six products listed, brand archive self-canonical, Core Kit and Core Kit Pro still
  have no add-to-cart and no price (online purchasing NOT re-enabled).
* The 12 AddToAny "unverified" links are share-widget endpoints, not site content.

### 9. esim.ambimat.com — 69 warnings, 0 findings
* Genuine defects: **0**. 33 of 69 were Google Tag Manager's own `<noscript>`
  iframe on every page. **NO CHANGE REQUIRED.**

---

## C. The three medium findings, closed

**ambimat.com — CLOSED**
```
URL:          https://ambimat.com/cellular-network-based-wide-area-networks/  (post 2701)
Rule:         Duplicate meta description across 2 pages
Observed:     identical description on 2701 and 5071
Why:          two pages competing on one snippet; neither describes 2701's subject
Root cause:   the shared text is verbatim 5071's opening paragraph, copied onto 2701
Action:       rewrote 2701's _yoast_wpseo_metadesc from its own body (NB-IoT / LTE-M)
Verification: indexable updated, og:image byte-identical before/after, W3TC page
              flushed, live HTML confirms; 5071 unchanged; post-fix crawl medium 1 -> 0
```

**ai.ambimat.com — DIAGNOSED, remediation deliberately refused**
```
URL:          https://ai.ambimat.com/contact/
Rule:         Low content-quality score (45/100) — "very thin (65 words)"
Observed:     102 words in the prerendered fallback
Why:          thin pages rarely rank
Root cause:   it is a contact page. The heuristic measures the no-JS fallback of a
              React form; the page carries a working intake form with a
              data-fallback-email, breadcrumbs and sibling-site navigation.
Action:       NONE. Padding it would be exactly the score-chasing the brief forbids.
Verification: form present, route 200, contact path unchanged (Phase 16 intact).
```

**orders.ambimat.com — CONFIRMED, blocked on access**
```
URL:          https://orders.ambimat.com/  and  /brand/ambimat-electronics/
Rule:         Duplicate meta description across 2 pages
Observed:     both serve "Order Ambimat Electronics boards and kits online — ..."
Why:          the brand archive competes with the homepage on the same snippet
Root cause:   the brand taxonomy archive inherits the shop description
Action:       BLOCKED — no shell, no admin session on this host. Needs owner.
Verification: canonicals confirmed correct and self-referential on both.
```

---

## D. Suspicious-warning analysis

```
Warnings before:      593
Unique rule families:   8
True positives:         2   (ai + orders missing security headers)
Owner decision:         1   (ambimat.com CSP)
Intentional:            1   (documented offsite 301)
Transient:              1   (ConnectionReset, 200 on retry)
False positives:      588
Warnings after:        14
```

| Rule family | Before | After | Root cause |
|---|---:|---:|---|
| suspicious-pattern | 518 | 0 | CSS hiding tokens substring-matched against raw HTML |
| external-iframe | 55 | 9 | GTM/reCAPTCHA/Maps not allowlisted |
| defacement-marker-in-content | 10 | 1 | "owned by" is ordinary English |
| security-headers | 3 | 3 | genuine |
| japanese-spam | 3 | 0 | bare English "betting" in the romaji list |
| suspicious-external-link | 2 | 0 | "pharma"/"crypto" as free substrings |
| offsite-redirect | 1 | 1 | intentional |
| fetch-error | 1 | 0 | no retry on the page-fetch path |

**The 14 that remain are all intentional:** 3 genuine security-header gaps; 9 WordPress
oEmbed iframes of external publishers (pcisecuritystandards.org, idtechproducts.com…) —
real third-party frames that a security monitor *should* name; 1 documented 301; and 1
"hacked by" advisory on a cyber-attack article, which is a strong marker in editorial
content and is exactly what the advisory tier exists to surface for a human.

---

## E. External links

```
Unverified before:   24
Actually broken:      0
Fixed:                0
Expected anti-bot:   15
Temporary/blocked:    4   (local network appliance, all verified live off-LAN)
Monitor bug:          5   (www./subdomain forms of listed skip-hosts)
Unverified after:    12
```

**No link on any of the nine sites is broken.** Detail:
* 12 AddToAny share endpoints — `/add_to/email` 302s to a `mailto:` URL, which is the
  widget working, not a failure. Host added to the skip list.
* 5 social links — `www.facebook.com` and `in.linkedin.com` were listed as bot-hostile
  but the check used an exact netloc match. Fixed.
* 4 connect timeouts (fime.com, 5gaa.org, sanctionscanner.com, blog.erepublic.com) —
  the appliance at `192.168.3.1:8888` returns a "Web Site Blocked" page on port 80 for
  three of them. All four confirmed live from off-network. Not link rot.
* 3 HTTP 403 (iso.org, cisa.gov, robo-racer.slack.com) — cisa.gov and slack return 200
  to a browser UA. Correctly unverified, never "broken".

**Near-miss worth recording:** an NXP link on post 4905 returned 404 to `curl` and I was
one step from "fixing" it. `https://www.nxp.com/` *itself* returns the same 404 — it is
NXP's anti-bot page. Checked in a real browser, the URL 301s to the current NXP UWB page
and works. **No change made.** This is precisely why HEAD 403 + GET 404 needs a human
before it is treated as rot.

Two different Facebook pages are in use across the estate
(`/AmbimatElec` and `/Ambimat-Electronics-213415895353632`). Both are live. Consolidating
is an owner decision, not a defect.

---

## F. Performance observations

```
URLs flagged:      10  (9 ambimat.com + 1 ambisecure.ambimat.com)
Reproducible:       0
Root cause:         absolute threshold vs. a host baseline + sampling noise
Fixed:              0  (nothing to fix)
Remaining expected: yes — the flags will keep moving between runs
```

Controlled measurement (5–7 samples per URL, medians):

| Group | median TTFB |
|---|---|
| ambimat.com pages **flagged** slow | 1248 – 1370 ms |
| ambimat.com pages **not flagged** (controls) | 1366 – 1426 ms |

**The unflagged control pages are slower than the flagged ones.** There is no per-page
problem; ambimat.com has a host-wide ~1.4 s TTFB floor. `ambisecure /blog/archive/`
measured 142 ms median against a 44 ms site baseline — fast, and nowhere near 3889 ms.

The post-fix crawl settles it independently: **not one flagged URL repeats.** Ambimat
went from 9 flagged pages to 6 *entirely different* ones; AmbiSecure cleared
`/blog/archive/` and flagged two different pages instead. Site averages barely moved
(1735→1545 ms, 341→356 ms). Classification: **HOSTING_BASELINE + MONITOR_THRESHOLD_NOISE**.

Recommended follow-up (deliberately NOT implemented, see J): the SEO tracker should flag
a page slow relative to its own site's median rather than against a fixed 2500 ms.

---

## G. Nine-site final status

| Site | Live | SEO | Sitemap | Links | Metadata | Performance | Overall |
|---|---|---|---|---|---|---|---|
| ambimat.com | OK | 0H 0M 57L | OK | OK | fixed | host baseline | **OK** |
| ambisecure.ambimat.com | OK | 0H 0M 3L | OK | OK | OK | OK | **OK** |
| ambipower.ambimat.com | OK | 0H 0M 1L | OK | OK | documented exemption | OK | **OK** |
| ambiautomation.ambimat.com | OK | 0H 0M 0L | OK | OK | OK | OK | **OK** |
| v2x.ambimat.com | OK | 0H 0M 0L | OK | OK | OK | OK | **OK** |
| ai.ambimat.com | OK | 0H 1M 8L | OK | OK | fixed, awaiting upload | OK | **PENDING DEPLOY** |
| roboracer.ambimat.com | OK | 0H 0M 0L | OK | OK | OK | OK | **OK** |
| orders.ambimat.com | OK | 0H 1M 14L | OK | OK | 2 items blocked | OK | **OWNER ACTION** |
| esim.ambimat.com | OK | 0H 0M 0L | OK | OK | OK | OK | **OK** |

---

## H. Rooted Phone changes

```
Stale comments corrected:  12 in-repo + 6 on the live phone scheduler
Monitor logic changed:     7 rules narrowed at root cause (see D)
Tests added:               43 assertions (test_warning_signal_quality.py)
Schedule changed:          NO
Measurement subsystem:     NO
```

Schedule verified on device: `0 8` site, `0 9` SEO, `0 10` cache, watchdog every 30 min.
Nine-site inventory intact, `ambimechanicals` absent, no measurement job or directory.
The live `ensure_scheduler.sh` and its versioned repo snapshot are now byte-identical
(`e5b92d5c`), with executable scheduling lines proven byte-identical before and after,
`bash -n` clean and a dry-run at rc=0. Historical evidence names
(`noon-cache-inspection-*`, `measurement_queue_20260825`) deliberately untouched.

---

## I. Tests

```
passed:  269
failed:    0
skipped:   0
```

| Suite | Result |
|---|---|
| Rooted-Phone `test_warning_signal_quality.py` (new) | 43 passed |
| Rooted-Phone `test_head_get_fallback.py` | 18 passed |
| Rooted-Phone `test_site_inventory.py` | 5 passed |
| Rooted-Phone `test_schedule_times.py` | 4 passed |
| Rooted-Phone `test_redirect_base.py` | 4 passed |
| Rooted-Phone `sched_tests_noon.sh` | 39 passed |
| Ambimat-AI-site `vitest` (19 files, incl. new `og_image.test.ts`) | 156 passed |

The same three Python suites were re-run **on the phone** against the deployed files:
43 / 18 / 4, zero failures. Every monitor-rule change ships a paired test: the false
positive is gone AND the attack it was meant to catch still fires.

---

## J. Git / deployments

```
Repository:              Rooted-Phone
Commit:                  66ed70d
Push:                    74b23ec..66ed70d main -> main  (no intervening commits)
Deployment:              4 files copied to the phone, all SHA-256 verified;
                         ensure_scheduler.sh synced and dry-run verified
Production verification:  post-fix crawl 593 -> 14 warnings, 24 -> 12 unverified
```
```
Repository:              Ambimat-AI-site
Commit:                  b6459e2
Push:                    353f951..b6459e2 main -> main  (no intervening commits)
Deployment:              *** NOT DEPLOYED — REQUIRES OWNER ***
Production verification:  pending
```
```
Repository:              none (production WordPress)
Change:                  ambimat.com post 2701 meta description
Deployment:              wp post meta update + targeted W3TC page flush
Production verification:  live HTML confirms; og:image gate passed
```

**Untouched, deliberately:** `ambisecure-seo-tracker` has uncommitted work in progress
(GSC provenance across 5 files, plus two new report directories). The SEO tracker's
slow-page threshold is the one monitor change I did *not* make, because doing so would
have collided with that work. `ambipower-site` and `roboracer-source` untracked owner
files were left in place. No repo was reset, cleaned, or force-pushed.

**Owner action needed — ai.ambimat.com deploy.** This host has no SSH, no CI and no
stored credentials; `DEPLOYMENT_HOSTINGER.md` documents it as a manual hPanel upload.
The artifact is built and waiting:
`Ambimat-AI-site/hostinger-deploy/` (and `hostinger-deploy.zip`, 4.6 MB) — upload its
contents to the ai.ambimat.com document root. That single upload closes the AI site's
1 medium + 7 low findings and its 4 missing security headers.

---

## K. Remaining actionable defects

1. **orders.ambimat.com — duplicate meta description** on `/` and
   `/brand/ambimat-electronics/`. Needs admin access. *(owner)*
2. **orders.ambimat.com — four security headers absent** on a host that takes orders.
   Needs hosting/admin access. *(owner)*
3. **ai.ambimat.com — upload the built package.** Fix is committed and tested. *(owner)*
4. **ambimat.com — no Content-Security-Policy.** Genuine, but a CSP on a WordPress site
   running GTM, GA4, CookieYes, reCAPTCHA and Jetpack/Photon will break the site if
   guessed. Recommend a staged `Content-Security-Policy-Report-Only` rollout. HSTS,
   X-Frame-Options, X-Content-Type-Options and Referrer-Policy are already correct.
   *(owner decision)*
5. **62 skipped heading levels** (48 ambimat + 14 orders). Genuine WCAG 1.3.1 advisories,
   stable across both runs, but they are authored-content defects across 62 WordPress
   pages — a content campaign, not a remediation pass, and each edit risks the documented
   Yoast indexable/og:image rebuild. Not bulk-edited here by choice.
6. **SEO tracker slow-page rule** should become relative-to-site-median. Not implemented
   because that repo has concurrent uncommitted work.

Not listed as defects, by design: anti-bot 403s, the local network appliance's blocks,
oEmbed iframes of external publishers, the documented ambipower `/privacy/` NO_IMAGE
exemption, the two cosmetic duplicate H1s, and latency threshold noise.

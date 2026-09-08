# Ambimat estate — CSP enforcement, accessibility closure, link adjudication, latency model

Continues `reports/estate_closure_20260908T143443Z`.

```
                          previous pass   this pass
suspicious warnings             1      →      0
broken pages                    0      →      0
broken links                    0      →      0
unverified links                7      →      5   (every one classified; none broken)
SEO high                        0      →      0
SEO medium                      0      →      0
SEO low                        28      →     10
heading advisories             22      →      5   (on 4 pages)
pages missing <main>           13      →      0
unlabelled contact controls    13      →      0
untitled iframes                7      →      0
links with no accessible name   1      →      0
tests                         382      →    465
```

Final crawls: site monitor **17:20**, SEO **17:20**, accessibility **17:38** (all IST, 2026-09-08).
Both crawls were run from the Mac — **the phone was not connected over USB for any part of this
session**, so the monitor changes are committed and pushed but NOT yet deployed to the device.
See section H.

---

## A. CSP

```
Original mode:   Content-Security-Policy-Report-Only  (one producer, ~/public_html/.htaccess)
Final mode:      ENFORCING_AND_VERIFIED
```

### Functional flows tested

Every one exercised in real Chrome against the live site, before and after the flip:

| Flow | Result |
|---|---|
| Home page load, menus, 7 nav items, 51 images | 0 broken images, fonts (Roboto/Montserrat/Material Icons) loaded, 17 stylesheets |
| `/contact/` render, 4 CF7 forms, 5 iframes | all render; Google Map loads |
| CF7 client-side validation | 7 × "This field is required." on empty submit |
| CF7 SWV schema validation | "The telephone number is invalid." on a bad number |
| CF7 network path | all endpoints are `ambimat.com/wp-json/contact-form-7/v1/…` — same-origin, so identical to the schema/refill fetches that were observed succeeding under enforcement |
| reCAPTCHA v2 | 8 frames rendered, `grecaptcha.getResponse` functional, `www.google.com` frame allowed |
| CookieYes banner | preference modal opens from the revisit button; banner SVG icons load (36/10/78 px natural width) |
| Consent **reject** | all seven signals → `denied`; no third-party origin fires afterwards |
| Consent **accept** | all seven → `granted`; GA4 + Ads endpoints fire |
| Drift live chat | widget opens with a real greeting; `typeof window.drift === "function"` |
| oEmbed article (`/triple-des-or-3des/`) | `encryptionconsulting.com` frame renders 665×505 with its title |
| Product page, `/products/`, a CDN-image article | 0 broken images; the hotlinked Quora CDN image renders 300×146 |

**No production enquiry was sent.** The submit path was exercised with client-side validation
failures and with reCAPTCHA deliberately unsolved, both of which are rejected before mail.

### Violations found

The Report-Only policy had been derived from **static HTML**, which cannot see anything a script
injects at run time. Eight origins were missing. Each was found in a browser or in a 346-page
sweep of the live site; none is a guess.

| Resource | Directive | Classification |
|---|---|---|
| `js.driftt.com/include/…js` | script-src | LEGITIMATE_REQUIRED_RESOURCE — Drift live chat, an **active WordPress plugin** with its own `Drift_settings` option |
| `js.driftt.com/core`, `/core/chat` | frame-src | LEGITIMATE_REQUIRED_RESOURCE — the same widget's frames |
| `cdn-cookieyes.com/…/*.json` | connect-src | LEGITIMATE_REQUIRED_RESOURCE — banner config, translations, audit table |
| `cdn-cookieyes.com/assets/images/*.svg` | img-src | LEGITIMATE_REQUIRED_RESOURCE — banner icons |
| `analytics.google.com/g/collect` | connect-src | **POLICY_DEFECT** — the policy listed `https://*.analytics.google.com`; a `*.` prefix requires at least one label, so it never matched the bare host |
| `stats.g.doubleclick.net/g/collect` | connect-src | LEGITIMATE_REQUIRED_RESOURCE — GA4 with Google Signals; fires only **after consent is granted**, which earlier testing never did |
| `www.google.co.in/ads/ga-audiences` | img-src | LEGITIMATE_REQUIRED_RESOURCE — Ads remarketing pixel, consent-gated |
| `csp.withgoogle.com/csp/frame-ancestors/…` | connect-src | Google telemetry, intermittent; harmless if blocked, listed so enforcement does not log an error nobody can act on |
| `qph.cf2.quoracdn.net/main-qimg-…` | img-src | LEGITIMATE_REQUIRED_RESOURCE — a hotlinked body image, verified 200 and rendering |

Two more were found **only after enforcement went live**, by re-running the flows:

* **`data:` in `script-src`.** Chrome reported `script-src-elem <- data` four times on the home
  page and Drift never loaded. Root cause is `flying-scripts/html-rewrite.php:52`, which takes an
  **inline** script, base64s its body and parks it in `data-src="data:text/javascript;base64,…"`
  until the visitor interacts. `flying_scripts_include_list` is
  `driftt, js.driftt.com, adsbygoogle, googlesyndication, pagead2, maps.googleapis, recaptcha/api.js`
  — so blocking `data:` takes out the live chat, the ad tag, the Maps API and **the reCAPTCHA
  bootstrap the contact form depends on**. Allowed, because against a policy that already carries
  `'unsafe-inline'` it grants an attacker nothing new: it is the same inline script with a
  different transport. It is listed last so it is removed together with `'unsafe-inline'` if that
  ever happens — beside a nonce/hash policy it would be a real hole.
* **`'self'` in `frame-src`.** The allowlist was built from the nine publisher embeds and contained
  only third-party origins. A 346-page sweep found zero same-origin iframes on the public site —
  but this `.htaccess` also governs `/wp-admin/`, where the Customizer preview and the TinyMCE
  editor body are same-origin frames. Same-origin framing is already bounded by
  `frame-ancestors 'self'`.

Not allowed, deliberately:
* `upload.wikimedia.org` — its one hotlinked image on `/barcode/` **already returns 404 at
  source**. Allowing an origin to un-block an image that is broken anyway would only hide the
  real defect. Recorded in section K.
* Google ccTLDs beyond `.co.in` — the `/ads/ga-audiences` pixel hits the **visitor's local**
  Google domain, which cannot be enumerated. `.co.in` is the measured one and India is the
  primary market. Non-Indian visitors' remarketing pixel is blocked by design: an advertising
  signal, not site functionality, and no visitor sees a difference. Reversible by adding hosts —
  deliberately not a wildcard.

### Production header

```
content-security-policy: default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' data: https://www.googletagmanager.com
    https://cdn-cookieyes.com https://directory.cookieyes.com https://log.cookieyes.com
    https://www.google.com https://www.gstatic.com https://stats.wp.com
    https://pagead2.googlesyndication.com https://js.driftt.com;
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src 'self' data: https://fonts.gstatic.com;
  img-src 'self' data: https://i0.wp.com https://i1.wp.com https://i2.wp.com https://stats.wp.com
    https://pixel.wp.com https://www.googletagmanager.com https://www.google-analytics.com
    https://www.google.com https://www.google.co.in https://maps.gstatic.com
    https://cdn-cookieyes.com https://qph.cf2.quoracdn.net;
  connect-src 'self' https://www.google-analytics.com https://analytics.google.com
    https://*.analytics.google.com https://*.googletagmanager.com https://stats.g.doubleclick.net
    https://stats.wp.com https://log.cookieyes.com https://directory.cookieyes.com
    https://cdn-cookieyes.com https://csp.withgoogle.com;
  frame-src 'self' https://www.google.com https://maps.google.com https://www.youtube.com
    https://www.youtube-nocookie.com https://js.driftt.com https://paylosophy.com
    https://www.pcisecuritystandards.org https://www.encryptionconsulting.com
    https://www.tech-faq.com https://idtechproducts.com https://www.idwholesaler.com;
  frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none';
  upgrade-insecure-requests
```

`form-action 'self'` is safe: a sweep of every `<form action>` on all 346 pages returns only
`ambimat.com` (and one `http://` form that `upgrade-insecure-requests` rewrites).

### Post-enforcement verification

Exactly one CSP header on 200s, on a static asset and on a 404; **zero** `Content-Security-Policy-Report-Only`
headers anywhere. `securitypolicyviolation` listener reported **0 violations** on the home page,
`/contact/`, the oEmbed article, `/products/` and the Quora-image article, across consent reject
**and** accept, with Drift, GTM, reCAPTCHA and CF7 all functional.

---

## B. Main landmarks

```
Pages affected before: 13   (10 ambimat.com + 3 ai.ambimat.com)
Pages missing main after: 0
```

**Root causes — two, both shared, neither a per-page problem.**

*ambimat.com (launchseat theme).* `header.php` ended after `</nav>` and `footer.php` opened
straight into `<footer>`; no template between them opened a landmark. All 29 templates pair
`get_header()` with `get_footer()` exactly 1:1, so the fix belongs in that pair. `search.php` had
its own `<main>` and was demoted to a `div` so there is never a nested one.

*ai.ambimat.com.* `AppShell.tsx` has rendered `<main class="app-main">` since the app was written
— but `main.tsx` mounts with `createRoot()`, so the landmark only exists **after JS runs**. A
crawler, a no-JS visitor and the monitor all read the file as served, and that file had none.
`scripts/prerender.mjs` now routes all three body-expansion sites through one `intoRoot()` helper.
No nesting risk for the same reason: `createRoot()` replaces `#root`'s children.

**Files changed**

| File | Change |
|---|---|
| `launchseat/header.php` | `<main id="main" class="site-main">` after `<!--navbar -->` |
| `launchseat/footer.php` | `</main>` before `<footer id="contact">` |
| `launchseat/search.php` | its own `<main>` demoted to `<div class="site-main">` |
| `Ambimat-AI-site/scripts/prerender.mjs` | `intoRoot()` wraps every prerendered body |

Layout neutrality was measured, not assumed: no `body > X` selector, no flex/grid on `body`, no
`main` element rule in the theme CSS; live check gives `display:block`, 0 margin, 0 padding, full
width, no horizontal scroll, and nav/header/footer all outside. Verified `main=1 /main=1` on the
home page, `/contact/`, `/products/`, an article, `/careers/`, `/by-industry/` and a search
results page, and on all 16 built AI routes.

> **Trap worth recording.** The first deploy script guarded idempotency on
> `count("    <!--navbar -->\n")` — which is still 1 *after* the insertion, so a re-run produced a
> **second** `<main>`. Guard on the presence of `<main`, not on the anchor.

---

## C. Contact controls

```
Controls reported before: 13
Genuinely unlabelled:      0
```

All 13 were false positives, and the rule was wrong three separate ways.

| # | Controls | Producer | Truth |
|---|---|---|---|
| 5 | `input[type=radio][name=inlineRadioOptions]` (Vendor, New Client, Support Request, JobSeeker, Distributor Request) | theme (`page-contact.php`) | each is **wrapped in a `<label>`**, which the HTML spec accepts as an accessible name. The audit only looked for `label[for=]`. |
| 4 | `input[type=checkbox][name="PCB-Types[]"]` | Contact Form 7 | same — CF7 emits `<label><input …><span class="wpcf7-list-item-label">Flexible PCBs</span></label>` |
| 4 | `textarea[name=_wpcf7_ak_hp_textarea]` | Akismet via CF7 | inside `<p style="display: none !important;" class="akismet-fields-container">` — out of the accessibility tree entirely, and **must not** be labelled: naming a honeypot tells a spam bot which field to skip |

The 4 `g-recaptcha-response` textareas seen at runtime are injected by Google and were never part
of the 13 (they are not in the served HTML).

**Genuine defects found on the same page and fixed:**

* the Google Maps embed had **no accessible name** → `title="Ambimat Electronics office location
  on Google Maps"`
* `<a href="https://google-map-generator.com"></a>` — an empty anchor left behind by the embed
  generator: no accessible name, no text, and an uncontrolled outbound link nobody chose to
  endorse → **removed**

The 4 remaining untitled iframes on that page are Google's reCAPTCHA `<noscript>` fallback,
vendor markup that a JS-enabled visitor never renders. Correctly classified rather than edited.

```
Keyboard/validation test:  submit with empty fields -> 7 "This field is required."
                           bad phone -> CF7 SWV "The telephone number is invalid."
Submission test:           network path verified same-origin; no enquiry delivered
Metadata after the edit:   title, description, canonical, og:title, og:description, og:image,
                           robots and JSON-LD count all byte-identical
```

**Deliberately not done:** the five inquiry-type radios have no group name (no `fieldset`/
`legend`/`role="radiogroup"`). Adding one means wrapping the group or re-roling a container that
also holds the section's `h2` and helper text, on a governed contact form, to satisfy a
best-practice rather than a failure — the radios already announce their own names and the
preceding heading supplies context. Owner call.

---

## D. Heading advisories

```
Before: 22 pages
After:   4 pages (5 skips)
og:image regressions: 0
Yoast/metadata regressions: 0
Database writes: 0 for the eleven ambimat articles and pages, 0 for the three Orders policy pages
```

### Method

On both themes heading **level** and heading **type** are coupled through bare element selectors,
so every promotion needs a guard class restating the source level's type. All values measured in
Chrome, desktop **and** at each theme's own breakpoints — never guessed.

Where the content was the producer, the change is a `the_content` filter in a mu-plugin, **not**
a `wp_update_post`. A content write rebuilds the Yoast indexable and has moved `og:image` on this
site before; none of that risk buys anything when the change is only which tag wraps unchanged
text. Verified afterwards: `post_modified_gmt` and `wp_yoast_indexable.open_graph_image` unchanged
on all eleven.

### What was fixed

| Group | Pages | Root cause | Fix |
|---|--:|---|---|
| SHARED_TEMPLATE | 3 | `/products/`, `/by-industry/`, `/by-technologies/` render `<h1>` then a card grid with **no section heading between them** | added `<h2 class="screen-reader-text">` (the theme's own visually-hidden utility — measured 0×0 box, document height identical) |
| SHARED_TEMPLATE | 2 | the same card component emits `h5` on the two taxonomy grids and `h3` on `/products/` | `h5 → h3`; card box and image box measured **identical**, only the title block grows 4px inside a fixed-height card |
| WORDPRESS_CONTENT | 9 | three articles open below the `<h1>` at h3/h4; six run a block of h4/h5 subsections under an `<h2>` | `the_content` filter + four measured guard classes |
| SHARED_TEMPLATE | 2 | `/f1tenth/` and the M2M page render bodies from a custom template | same filter, keyed on the queried object |
| SHARED_TEMPLATE | 1 | front page blog cards at `h4` under an `h2` | `front-page.php` card → `h3` + guard class |
| WORDPRESS_CONTENT | 3 | the three Orders policy pages start their sections at `h3` under the `h1` | `the_content` filter + guard restating Astra's own h3 ladder |

**Visual neutrality, measured after each deploy**

```
33 guarded headings across 11 ambimat articles/pages   0 property mismatches (desktop)
12 of those re-measured at 375px, all four classes     0 property mismatches
3 front-page cards                                     0 mismatches; document height 6520 -> 6520
10 Orders policy headings                              0 mismatches; document height 3199 -> 3199
```

Three findings only a measurement could produce:

1. The 2026-08 R5 opener classes were **reused and were wrong here** — `ambimat-opener-as-h3`
   pins 24px/600/1.1, but in this CSS scope an `.entry-content h3` is 20px/600/27px. Own classes,
   own measurements.
2. `/f1tenth/` renders **outside** `.entry-content`, so a `.entry-content`-scoped guard silently
   did nothing there.
3. Even a bare `h3.ambi-outline-…` (0,1,1) **tied** with `.innerpages h3` in a stylesheet loaded
   later, and a tie is decided by source order — so it lost. The class is repeated in the selector
   to make it (0,2,1), and the outcome no longer depends on load order.

### The 5 that remain, each with its exact reason

| Page | Skip | Producer | Why not fixed |
|---|---|---|---|
| `ambimat.com/careers/` | h2→h5 "Job Description" | ACF repeater meta `current_openings_N_job_description`, ~30 entries, **mixed** `<h5>` and `<h4>` | needs an `acf/format_value` filter plus per-entry level normalisation; two producers on one page, and fixing only one leaves the page still reporting |
| `ambimat.com/careers/` | h2→h4 card | `page-careers.php` ×3 | same page — no value in half a fix |
| `ambimat.com/about/ambimat-history/` | h2→h5 "April, 1982" | `ang-timeline` plugin widget, one h5 among 40 h2s | the heading is inside a third-party widget's own render path, not `the_content` |
| `orders.ambimat.com/contact/` | h2→h5 "Works" | `page-contact.php`, `<h5 unselectable="on">` in `.contact-info .media-body` | these are 14px **uppercase grey captions** (h5 14px/600/16.8px uppercase vs h3 36px/600/46.8px). Six type properties would have to be restated across breakpoints to keep a caption looking like a caption. Reads as intentional caption markup, not a section heading. |
| `orders.ambimat.com/product/roboracer-power-board-multi-qty-non-rohs-compliant/` | h2→h4 | two `<h4 style="margin:20px auto">` in the product body | the theme sets the h4 margin with `!important` (measured: the inline `margin:20px auto` is overridden to 12px), so the guard would need `!important` to hold — a worse trade than leaving one advisory |

None is a false positive; each needs an owner/content decision or a change with a worse
cost/benefit than the advisory it clears.

---

## E. Seven external links

Every one re-verified from **three networks**: this LAN, the WebFetch egress, and the GoDaddy
production host. That third vantage point is what produced the true answers — the LAN appliance
at `192.168.3.1:8888` blocks two of these hosts outright and returns its own "Blocked" page.

| # | Source | Destination | Classification | Action | Final state |
|--:|---|---|---|---|---|
| 1 | ambimat `/hardware-security-module-hsm/` | `entrust.com/…/entrust-nshield-family-br.pdf` | EXPECTED_ANTIBOT | none | 403 from every network, and a real Chrome gets a page titled **"Access Restricted — Your request was blocked due to our security policies"**. The host says so in words. |
| 2 | ambimat `/worldnet-launches-gochipnow…/` | `businesswire.com/news/home/20180827005090/…` | EXPECTED_ANTIBOT | none | 403 to automated clients; a real Chrome is bounced to `/newsroom` twice. Search engines index the exact URL with the exact headline, so it resolves for ordinary clients. A verified mirror exists at `idtechproducts.com/press-release/worldnet-launches-gochipnow/` (same headline, same 2018 date, from a named party) — **recorded, not applied**: the NXP lesson says do not rewrite a link on the strength of a WAF response. |
| 3 | ambimat `/think-youre-ready-for-emv…/` | `fime.com/whitepaper/EMVmigration` | **ACTUALLY_BROKEN** | anchor removed, title kept | soft 404 |
| 3b | *same page* | `fime.com/america.html` | **ACTUALLY_BROKEN** (not in the original seven) | repointed to `https://www.fime.com/` | verified 200, "Home \| Fime" |
| 4 | ambisecure `/blog/archive/how-does-identity-verification-work…/` | `sanctionscanner.com/blog/6-identity-verification-methods-272` | **WORKING** | none | 200 from the production host, 301 → `www.`. The monitor's connect timeout was the LAN appliance and said nothing about the remote. |
| 5 | ambisecure `/blog/lava-lamps-and-cryptographic-entropy/` | `cloudflare.com/learning/ssl/lava-lamp-encryption/` | EXPECTED_ANTIBOT | none | 403 to a crawler; **200 with the real article in Chrome** ("How Do Lava Lamps Help with Internet Encryption?") |
| 6 | esim `/blogs/global-shift-away-from-sms-otp.html` | `centralbank.ae/en/` | EXPECTED_ANTIBOT | none | 403 to a crawler; **200 with the real site in Chrome** ("CBUAE \| Central Bank of the UAE") |
| 7 | roboracer `/our-clients.html` | `kmu.ac.kr/` | WORKING | none | the remote omits its intermediate certificate, so strict validators fail where a browser succeeds |

```
Unverified before:      7
Actually broken:        2   (one of them never in the seven, and invisible to every status check)
Fixed:                  2
Expected anti-bot:      4
Appliance-blocked only: 1   (sanctionscanner — proven working from a clean network)
Working with a TLS quirk: 1
Unverified after:       5   (a different sample — see below)
```

### The finding that mattered most

**`fime.com` serves its 404 page with HTTP 200.**

```
https://www.fime.com/whitepaper/EMVmigration  -> 200 -> https://www.fime.com/404   ("404 | Fime")
https://www.fime.com/america.html             -> 200 -> https://www.fime.com/404   ("404 | Fime")
https://www.fime.com/                         -> 200 -> https://www.fime.com/      ("Home | Fime")
```

Two genuinely dead references sat in a clean report for as long as they have existed, because
their status code was fine. The monitor now treats a 2xx whose **final** URL is the remote's own
not-found path as broken — anchored, so a real article at `/404-explained/` is not swept up.

The whitepaper has no live copy anywhere; every surviving reference points back at that same
fime.com URL. The anchor was removed and the title kept, so the sentence still reads
"…excerpted from the FIME white paper, *"EMV Chip Migration for U.S. Merchant Community…"*" —
the citation survives in full and only the dead hyperlink is gone. Metadata on post 17443 after
the write: title, description, canonical, og:image, og:title, og:description and robots all
unchanged; the Yoast indexable row is byte-identical.

### Modelling (Phase 16)

`classify_unverified()` now names the shape of every failure:

```
unverified-expected-antibot    401/403/429 — a permanent property of the remote
unverified-network-blocked     connect timeout / refused / DNS — OUR vantage point, not theirs
unverified-tls-chain           the remote omits its intermediate certificate
unverified-timeout             read timeout — usually transient
unverified-unknown             honestly unknown
```

Every value still **counts as unverified**. The point is only that an anti-bot 403 stops reading
as "this link may be dead".

**And nothing stays trusted for ever.** Correctly calling a 403 "not broken" today must not become
"never look again" — if that page is deleted tomorrow the 403 looks identical. Every unverified
URL now carries the date it first failed, in `unverified_ledger.json`, and at
`alerts.unverified_stale_days` (30) the monitor raises a warning asking for a human check.
Verifying on any later run **drops it from the ledger and restarts the clock**, so this is a
re-verification schedule, not an allowlist, and it cannot be satisfied by doing nothing. Tested:
day 0 silent, day 29 silent, day 30 warns, day 31/45/200 still warn, a link that verifies resets.

### The 5 unverified in the final crawl

The external check is capped at 20 links per site, so the sample rotates between runs — these are
not the same seven, and all five were re-verified by hand from the production host:

| Site | URL | Classification | Verified from a clean network |
|---|---|---|---|
| Ambimat | `http://www.revvx.com/` | unverified-network-blocked | **200, alive** — this LAN could not reach it |
| AmbiSecure | `iso.org/standard/77180.html` | unverified-expected-antibot | 403 from both networks — genuine anti-bot |
| AmbiSecure | `nytimes.com/2019/07/25/…` | unverified-expected-antibot | paywalled publisher, refuses automated clients |
| RoboRacer | `kmu.ac.kr/` | unverified-tls-chain | 200 in a browser |
| V2X | `itsinternational.com/ettifos-joins-arizona-v2x-deployment/` | unverified-expected-antibot | **200 from the production host** |

**None is broken.**

---

## F. AmbiSecure latency model

```
Concurrency state:  SAFE — the five files another worker holds (.gitignore, main.py,
                    ranking_engine.py, report_generator.py, verify_offline.py) are unchanged
                    since 2026-08-20, no process is touching them, and none was read, staged
                    or modified. This work touched technical_audit.py and its tests only.
```

**Old rule** (before the previous pass): a flat 2500 ms cutoff.
**Evidence it was noise:** ambimat's nine "slow" pages measured a median TTFB of 1248–1370 ms
while pages *not* flagged on the same host measured 1366–1426 ms — the unflagged controls were
slower than the flagged ones. Two crawls three hours apart flagged two completely
non-overlapping sets of URLs while the site average barely moved.

**Host-relative rule** (shipped in `ef7c8fd`, verified here): a page is slow at
`max(2500 ms, host median × 2.5)`. The ratio alone would flag a 130 ms page on a 40 ms static
host; the floor alone is the old rule.

**What this pass added — persistence, because a spike is not a regression.** The host-relative
cutoff fixed *which* pages are outliers, not *whether one sample means anything*: a single 9 s
reading clears the cutoff whether it is noise or not. So:

* a page over the cutoff is a **defect only on the run that confirms it**; a first sighting is
  counted in `slow_pages_first_sighting` and written to state, never silently dropped
* **whole-host degradation** is checked separately, because a per-page outlier rule is blind to
  it by construction — if every page slows the median moves with them and nobody is an outlier.
  This run's median vs the previous run's, at ≥1.5× **and** ≥1000 ms, reported once with no URL

State: `~/.ambisecure-seo-tracker/latency_state.json` (`AMBISECURE_SEO_STATE_DIR` to override),
one small entry per domain. Missing or corrupt degrades to "first sighting" rather than crashing.

**Tests (13 new):** normal host variance produces nothing on any run; a lone spike is not a
defect; a spike that does not repeat never becomes one; a sustained regression is flagged with
its evidence; a fast host with one slow page is flagged and the rest are not; whole-host
degradation appears as a host-level issue; ordinary host movement is not; a *fast* host getting
3× slower (90→280 ms) is not, because of the floor; a host getting faster never is; state round
trips per domain without one domain erasing another.

**Current findings — the model on real data, two consecutive runs:**

```
domain          median   cutoff  slow  1st-sighting  prev-median  host-regression
Ambimat           1129     2822     0        0           1148            0
AmbiSecure          76     2500     0        0             65            0
eSIM               109     2500     0        0             57            0     <- 1.9x, correctly ignored
AmbiPower           91     2500     0        0             62            0
AmbiAutomation      92     2500     0        0             59            0
RoboRacer           71     2500     0        0             60            0
V2X                 88     2500     0        0             63            0
AI Tools            79     2500     0        0             61            0
Orders              82     2500     0        0            492            0     <- got faster
```

eSIM nearly doubled between runs and the model stayed quiet — correctly, because 109 ms is
nowhere near materially slow. A ratio-only rule would have raised an alarm.

---

## G. Nine-site final state

| Site | Live | SEO (H/M/L) | Accessibility | Security | Links | Overall |
|---|---|---|---|---|---|---|
| ambimat.com | 200, 346 pages | 0 / 0 / 5 | `<main>` on every template; contact form clean; 1 page with advisories (careers) | 5 headers + **CSP enforcing** | 0 broken | **OK** |
| ambisecure.ambimat.com | 200, 338 pages | 0 / 0 / 1 | clean | full | 0 broken | **OK** |
| ambipower.ambimat.com | 200, 28 pages | 0 / 0 / 1 | clean | full | 0 broken | **OK** |
| ambiautomation.ambimat.com | 200, 28 pages | 0 / 0 / 0 | clean | full | 0 broken | **OK** |
| v2x.ambimat.com | 200, 71 pages | 0 / 0 / 0 | clean | full | 0 broken | **OK** |
| ai.ambimat.com | 200, 8 pages | 0 / 0 / 1 | **`<main>` now served, not just hydrated** | full | 0 broken | **OK** |
| roboracer.ambimat.com | 200, 8 pages | 0 / 0 / 0 | clean | full | 0 broken | **OK** |
| orders.ambimat.com | 200, 17 pages | 0 / 0 / 2 | 3 policy pages fixed; 2 pages with advisories | full | 0 broken | **OK** |
| esim.ambimat.com | 200, 33 pages | 0 / 0 / 0 | clean | full | 0 broken | **OK** |

Orders invariants re-verified after every change: `/sitemap.xml` 301 → `wp-sitemap.xml` 200; zero
`cart`/`checkout`/`my-account`/`share-cart` in any child sitemap; brand archive self-canonical;
Core Kit and Core Kit Pro still carry **no** `name="add-to-cart"` while the Power Boards do.
Ambimat invariants: `/products/` indexable, self-canonical, breadcrumb "Home / Products", exactly
**15** product slugs, and the owner-approved NXP `MC_71108` link present and correct.

---

## H. Rooted Phone

```
Schedule:               08:00 site / 09:00 SEO / 10:00 cache — UNCHANGED, not touched
                        (test_schedule_times.py 4/4, which asserts every source of truth and
                        that nothing operational still carries the retired 10:00/11:00/12:00)
Nine-site inventory:    9 in config, ambimechanicals absent (test_site_inventory.py 5/5)
Measurement subsystem:  absent — test_measurement_experiment_stays_retired passes
Monitor code deployed:  NO — see below
Phone hash verification: NOT PERFORMED — see below
```

> **The phone was not connected over USB at any point in this session.** `scripts/moto-ssh.sh`
> reports "No adb device" throughout, so the monitor changes could not be pushed to the device or
> hash-verified there. They are committed and pushed to `origin/main`; the next connected session
> should `scp` `site_monitor/run_site_monitor.py`, `site_monitor/config/sites.yaml`,
> `site_monitor/a11y_audit.py` and the two new test files, then re-run the suites on the device.
> Both crawls in this report were therefore run from the Mac against the same nine live sites,
> using the same code and config.

---

## I. Tests

```
passed:  465
failed:    0
skipped:   0
```

| Suite | Result |
|---|---|
| Rooted-Phone `site_monitor/tests/test_unverified_classification.py` **(new)** | 36 |
| Rooted-Phone `site_monitor/tests/test_a11y_rules.py` **(new)** | 34 |
| Rooted-Phone `site_monitor/tests/test_warning_signal_quality.py` | 43 |
| Rooted-Phone `site_monitor/tests/test_iframe_and_defacement_invariants.py` | 26 |
| Rooted-Phone `site_monitor/tests/test_head_get_fallback.py` (updated) | 18 |
| Rooted-Phone `site_monitor/tests/test_redirect_base.py` | 4 |
| Rooted-Phone `tests/test_site_inventory.py` | 5 |
| Rooted-Phone `tests/test_schedule_times.py` | 4 |
| Rooted-Phone `cache_monitor/tests/sched_tests_noon.sh` | 39 |
| ambisecure-seo-tracker `pytest` (incl. 13 new in `test_latency_persistence.py`) | 100 |
| Ambimat-AI-site `vitest`, 20 files (incl. 3 new in `landmark.test.ts`) | 159 |

`test_redirect_base.py` needs `requests`, which is not installed system-wide on this Mac; it was
run in a virtualenv and passes. It has always been in that position — it is not a new condition.

---

## J. Git / deployment

| Repository | Starting SHA | Final SHA | Push | Deployment | Live verification |
|---|---|---|---|---|---|
| Rooted-Phone | `3040dde` | **`dfbfe1e`** | ✅ | **not deployed to the phone** (device absent) | crawls run from the Mac with this code |
| ambisecure-seo-tracker | `ef7c8fd` | **`89b1bdf`** | ✅ | n/a (desktop tool) | 100 tests; live 9-domain run |
| Ambimat-AI-site | `fb1e3be` | **`fb8514c`** | ✅ | rsync → Hostinger | 60/60 file hashes identical; 7 routes 200 with `main=1 h1=1 og:image` and 5 security headers |
| ambimat.com (no repo) | — | — | — | `.htaccess` + 4 theme files + 1 mu-plugin on GoDaddy | see below |
| orders.ambimat.com (no repo) | — | — | — | 1 mu-plugin on Hostinger | see below |

**Production files changed, each backed up with a timestamped copy and sha256 verified before the
write, and `php -l` checked after:**

```
ambimat.com  .htaccess                      .pre-cspenforce- / .pre-cspdata- / .pre-cspframeself-
             themes/launchseat/header.php   .pre-mainlandmark-
             themes/launchseat/footer.php   .pre-mainlandmark-
             themes/launchseat/search.php   .pre-mainlandmark-
             themes/launchseat/page-contact.php              .pre-mainlandmark-
             themes/launchseat/page-products-landing.php     .pre-headingsection-
             themes/launchseat/taxonomy-product_categories-by-industries.php
                                                             .pre-headingsection- / .pre-cardlevel-
             themes/launchseat/taxonomy-product_categories-by-technologies.php
                                                             .pre-headingsection- / .pre-cardlevel-
             themes/launchseat/front-page.php                .pre-cardheading-
             mu-plugins/ambi-heading-outline.php             NEW (delete to revert)
             post 17443 post_content                         two dead fime.com references
orders       mu-plugins/ambimat-policy-heading-level.php     NEW (delete to revert)
```

**Concurrency preserved.** `ambisecure-seo-tracker` still carries another worker's five
uncommitted files plus two untracked report directories — untouched; this pass committed only its
own three. No repo was reset, cleaned or force-pushed.

> One incident worth recording: a `git stash push` used to probe whether a test failure predated
> this session **stashed the working tree**, including uncommitted monitor work. It was recovered
> immediately with `git stash pop` and re-verified (9 expected symbols present, all suites green).
> Nothing was lost. Do not use `git stash` to answer "was this broken before".

---

## K. Remaining actionable issues

1. **The monitor changes are not on the phone.** The device was never connected this session.
   Committed and pushed; needs one connected session to deploy and hash-verify. *(blocked on
   physical access, not on a decision)*
2. **5 heading advisories on 4 pages**, each enumerated in section D with its producer and the
   exact reason it was not attempted. *(owner/content decisions)*
3. **A broken hotlinked image on `/barcode/`.** `upload.wikimedia.org/.../250px-Barcodes_on_British_Railways…jpg`
   returns **404 at source**, with or without a referer. It is an `<img>`, not an `<a>`, so no
   link checker has ever seen it. Found while enumerating CSP origins. Needs an editorial call:
   replace the image or remove it. *(owner decision, one image on one page)*
4. **`orders.ambimat.com` still has no meaningful CSP.** Unchanged from the previous pass and
   deliberately so: it is the host that takes payments, and a policy there needs a checkout pass
   with four gateways. *(owner decision)*
5. **wp-cli on Orders cannot load plugins.** `wp` under the CLI's PHP 7.4 hits a fatal from
   `woocommerce-payglocal-3.0.0`, which requires PHP ≥ 8.1; `--skip-plugins --skip-themes` works.
   The **web** server runs a newer PHP and the site is healthy, so this is a CLI/web version
   mismatch, not a site defect — but it means `wp breeze purge` is unavailable and the page cache
   has to be cleared by removing `wp-content/cache/breeze`. *(hosting configuration, informational)*

Not listed, by design: expected vendor anti-bot behaviour, the LAN appliance's blocks, normal
Hostinger response-time baselines, intentionally concise functional pages, the reCAPTCHA
`<noscript>` fallback iframes, and score-only AI-readiness recommendations.

# Ambimat estate — device closure, heading closure, /barcode/, Orders CSP

Continues `reports/estate_closure2_20260908T173000Z`.

```
                              previous pass    this pass
heading advisories                  5      →      0 unexplained  (4 fixed, 1 waived at the rule)
pages missing <main>                0      →      0
accessibility issues (46 pages)     —      →      0   (46/46 fully clean)
broken Wikimedia image              1      →      0
Orders CSP                     none (UIR only) →  ENFORCING_AND_VERIFIED
Orders wp-cli plugin loading    --skip-plugins →  works, no flag needed
device verification              NOT DONE   →   DEVICE_VERIFIED
```

---

## A. Preflight / repository identity

| Repository | Starting HEAD | Ending HEAD | origin/main | ahead/behind | Worktree | Stashes |
|---|---|---|---|---|---|---|
| Rooted-Phone | `5b1372a` | **`0af1718`** (+report commit) | `5b1372a` at start | 0/0 at start | clean at start | 0 |
| ambisecure-seo-tracker | `89b1bdf` | `89b1bdf` (unchanged) | `89b1bdf` | 0/0 | **other worker's 5 files + 2 dirs** | 0 |
| Ambimat-AI-site | `fb8514c` | `fb8514c` (unchanged) | `fb8514c` | 0/0 | clean | 0 |
| ambimat-site | `ec2be4e` | `ec2be4e` (untouched) | `ec2be4e` | 0/0 | **23 modified + 2 untracked, newest mtime 17:48 today** | 0 |

No active git operation in any repo. **`git stash` was not used at any point.**

**Other-worker files preserved.** The five in `ambisecure-seo-tracker` called out by the previous
worker were re-checked by mtime *and* content hash and are byte-identical to how they were left:

```
.gitignore                       2026-08-20T16:02:11  f3a25d5be3259eb2
main.py                          2026-08-20T16:05:04  8d34125e46c60732
seo_tracker/ranking_engine.py    2026-08-20T16:03:47  dccdb7920ffb582e
seo_tracker/report_generator.py  2026-08-20T16:04:20  07fc11912d4d42cd
tools/verify_offline.py          2026-08-20T16:07:03  a79b36cf82c4c8aa
```

`ambimat-site` additionally carries 23 modified + 2 untracked central-intake backend files whose
newest mtime is **17:48 today** — that is live concurrent work. Nothing in this campaign needed
that repository and nothing in it was read, staged, edited or cleaned.

Processes: one `adb fork-server` (normal). No stale git, deploy, crawler or SSH process; nothing
was terminated.

**Commits created**

| SHA | Repo | Scope |
|---|---|---|
| `0af1718` | Rooted-Phone | heading-audit rule: inert headings |
| *(report commit)* | Rooted-Phone | this report + evidence |

---

## B. Phone / device verification — `DEVICE_VERIFIED`

### Identity (not assumed — exactly one device, addressed explicitly with `-s`)

```
adb devices -l   ZY22382BFL  device usb:2-1 product:athene_f model:Moto_G__4_ transport_id:3
ro.serialno              ZY22382BFL      (matches the adb transport serial)
ro.product.model         Moto G (4)
ro.product.device        athene_f
ro.product.manufacturer  motorola
ro.build.version.release 7.0   (SDK 24)
ro.build.fingerprint     motorola/athene_f/athene_f:7.0/NPJS25.93-14-18/3:user/release-keys
Termux user              u0_a122     deployment root ~/site_monitor
```

### Deployment method

The project's established path: `scripts/moto-ssh.sh` (adb port-forward 8022 → Termux sshd,
key `~/.ssh/id_moto_playground`). No new mechanism was invented.

**State found on arrival:** `run_site_monitor.py` and `config/sites.yaml` were the *previous*
pass's versions, `a11y_audit.py` and two test files were absent — the committed work had indeed
never reached the device. `render_report.py` and `merge_reports.py` already matched and were not
touched.

Backup taken first (`~/sm_backup_20260908T121934Z`, hash-verified), then **six files** copied —
only the ones that differed. Nothing else on the phone was written.

### Hashes — every monitor file, including the ones deliberately left alone

| File | Result | Status |
|---|---|---|
| `run_site_monitor.py` | MATCH `a25a029db0214f6d…` | synced |
| `a11y_audit.py` | MATCH (final, after the Phase-2 rule change) | synced |
| `config/sites.yaml` | MATCH `1635222015703977…` | synced |
| `tests/test_head_get_fallback.py` | MATCH `1a0ea45e60d5ed4c…` | synced |
| `tests/test_a11y_rules.py` | MATCH | synced |
| `tests/test_unverified_classification.py` | MATCH `eec6dd630b78d0d3…` | synced |
| `render_report.py` | MATCH `5a4191eda2cc28a1…` | untouched |
| `merge_reports.py` | MATCH `144aeb2c888f3710…` | untouched |
| `tests/test_iframe_and_defacement_invariants.py` | MATCH | untouched |
| `tests/test_redirect_base.py` | MATCH | untouched |
| `tests/test_warning_signal_quality.py` | MATCH | untouched |

**11 match, 0 mismatch**, verified twice — once after the initial sync and again after the
Phase-2 audit-rule change was pushed to the device. `__pycache__` and `reports/` are
runtime-generated and were excluded from comparison rather than counted as mismatches.

### Device-side execution — run **on** the phone, not against it

```
env      Python 3.13.13, requests 2.34.2, Termux on Android 7.0 / armv7l
network  wlan0 192.168.5.197/24   ← a DIFFERENT subnet from the Mac
suites   6 files, 170 assertions, 0 failures
a11y     instrument imported and exercised on-device: headings 2, headings_inert 1, issues []
schedule crontab on device: 08:00 site monitor / 09:00 SEO / 10:00 cache  — UNCHANGED
config   9 sites, ambimechanicals absent, unverified_stale_days: 30 present
         (proving the new config is the one the device is running)
measurement subsystem   measurement_queue/ ABSENT, 0 crontab entries
```

**Full nine-site crawl executed on the phone** (`phoneclosure_20260908T122106Z`):

```
sites_total 9   sites_reported 9   sites_unreachable 0   sites_ok 9
pages_crawled       913
broken_pages          0
broken_links          0
alerts                0
suspicious_warnings   0
unverified_links     13   (every one classified)
partial           false
```

### Phone vs Mac — kept separate, and the differences are real

| | Phone (192.168.5.x) | Mac (LAN with the 192.168.3.1 appliance) |
|---|---|---|
| pages crawled | **913** | 877 |
| Orders pages | **49** | 17 |
| AmbiSecure pages | 342 | 338 |
| unverified links | 13 | 8 |
| broken pages / links / alerts / warnings | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

The phone reaches **more** of the estate, most visibly on Orders (49 vs 17 pages), and it
produces a different unverified set because it is not behind the LAN appliance — no
`fime.com`/`sanctionscanner.com`-style `unverified-network-blocked` results appear from the
phone at all. That is the point of running it there. Functional parity is proven; the timing and
sample differences are environmental and are reported as such rather than blended together.

One pre-existing device oddity, **not** introduced here: `~/test_site_inventory.py` is a stale
standalone copy at the phone's home directory that computes a wrong config path
(`…/files/site_monitor/config/sites.yaml`, missing the `home/` segment) and errors. It is not
part of `~/site_monitor/`, nothing schedules it, and the real inventory guard was verified
directly against the deployed config instead. Left alone rather than edited.

---

## C. Remaining headings — 5 advisories, 0 unexplained

| URL | Heading / context | Classification | Action | Evidence |
|---|---|---|---|---|
| `ambimat.com/careers/` | 29 × `<h5>` job field labels ("Job Description", "Skill Required", "Job Type", "Minimum Qualifications", "Minimum Experience") inside `.panel-body`, under `h2 "JOIN US"` | **GENUINE_SEMANTIC_DEFECT** | `h5 → h3` via an `acf/format_value/name=job_description` filter + measured guard class | Uniformly h5 (29 of 29 in the ACF fields, no mixed levels). Nothing occupies h3 or h4; the tab panels are named by `aria-labelledby`, an ARIA relationship, not a heading level. Hidden by `.tab-pane` — a **CSS class JS reveals**, so real readers meet them. |
| `ambimat.com/careers/` | 3 × `<h4 class="pmd-card-title-text">` developer-resource cards under `h2 "Our Developer resources"` | **GENUINE_SEMANTIC_DEFECT** | `h4 → h3` in `page-careers.php` + guard | Visible (312×44 / 312×22 boxes). Same component as the front page, but measured separately — here h4 is 20px/600 at both widths and differs from h3 only in line-height, so the front page's class would have been wrong. |
| `ambimat.com/about/ambimat-history/` | `<h5>April, 1982</h5>` inside one `<li>` | **GENUINE_SEMANTIC_DEFECT** | demoted **out of the hierarchy** to `<p class="ambi-timeline-date">` + guard | It is the only heading in **any** of the 27 timeline entries, its two sibling `<li>` in the same list are plain text, and it renders 18px/500/uppercase — a date label, not a section. Renumbering it to h3 would have kept a heading describing nothing. |
| `orders.ambimat.com/contact/` | 4 × `<h5>` — "Works", "Local Inquiry", "Global Inquiry", "Email Address" | **INTENTIONAL_AND_JUSTIFIED** | production **not** touched; the audit rule corrected | They live inside `<div class="col-sm-5 col-xs-12 form-section" style="display:none">`. Measured: `offsetParent` null, 0×0 box, document height identical with and without them. They render at **no** viewport. |
| `orders.ambimat.com/product/roboracer-power-board-multi-qty-non-rohs-compliant/` | 2 × `<h4 style="margin:20px auto">` manual-download labels under `h2 "Related RoboRacer products"` | **GENUINE_SEMANTIC_DEFECT** | `h4 → h3` via a `the_content` filter scoped to product 15 + guard | Visible (30px tall). Product 15 is the only published post carrying that block. |

```
Genuinely fixed:              4
Explicitly waived:            1
Remaining unexplained:        0
```

### The waiver

Not a URL suppression and not a per-page exemption — a **rule correction**, so it cannot hide
future defects:

> A heading inside a subtree hidden by an **inline** `style="display:none"` / `visibility:hidden`,
> `hidden`, or `aria-hidden="true"` is not counted, because the browser never paints it. The rule
> already refused to count *form controls* in exactly those subtrees, and refused to count
> anything inside `<noscript>`; this is the same principle, third application.

Deterministic and narrow:
* keyed on **inline** hiding only, never on a CSS class — so `careers/`'s 29 `.tab-pane` headings
  are still counted, and their skip was found and fixed by this same audit afterwards
* inert headings are **reported** (`headings_inert`), not silently discarded
* a test asserts an inert block cannot mask a genuine skip on visible content beside it

### Visual neutrality — measured, at 1400px and 375px

| Guard | Elements | Result |
|---|---|---|
| `h3.ambi-outline-careers-card` vs `h4` | 3 | **CLEAN** at both widths |
| `h3.ambi-outline-job-label` vs `h5` | 29 | **CLEAN** at both widths |
| `p.ambi-timeline-date` vs `h5` | 1 | **CLEAN** at both widths |
| `h3.ambi-download-label` vs `h4` (Orders) | 2 | **CLEAN**, document height 7135 → 7135 |

Two findings worth keeping:

* the timeline guard first lost a specificity contest to
  `.feed-timeline-vertical li .entry .panel-body p` (0,3,2) and the label silently gained 15px of
  bottom margin. Fixed with `!important` on that one declaration — the same weapon the site's own
  download component already uses, and for the same reason.
* Orders' Breeze cache sends `Vary: User-Agent` and served a near-empty page to a headless UA, so
  headless measurements of Orders were verified against the real browser rather than trusted.

**Zero Yoast/OG movement.** The nine earlier articles plus careers used filters and wrote nothing.
The two content writes (timeline post 1823, barcode post 16871) both reported
`INDEXABLE UNCHANGED` against a captured before/after row.

---

## D. `/barcode/` image

```
Removed source:  https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/
                 Barcodes_on_British_Railways_rolling_stock_in_1962_%28Modern_Railways_Dec_1962%29
                 _000130.jpg/250px-….jpg     (+ its 330px and 500px srcset variants)
Verified dead:   404 from the GoDaddy production host — a clean network, not this LAN — for BOTH
                 the thumbnail AND the original commons file, with and without a Referer.
                 Not replaced, and no substitute image was sourced.
File changed:    wp_posts post_content, post 16871 (/barcode/)
                 sha 382e245bf4d04cd7 -> b2ced8e54d86d3f2   (9275 -> 7902 bytes)
```

**What was removed, and why it was genuinely orphaned.** The block was pasted from Wikipedia and
everything in it existed only to present that one image:

```html
<div class="thumb tright"><div class="thumbinner">
  <a class="image" href="…/wiki/File:Barcodes_on_British_Railways…"><img class="thumbimage" …></a>
  <div class="thumbcaption"><div class="magnify"></div>
    Barcoded rolling stock in the UK, 1962
  </div>
</div></div>
```

It was the **only** `.thumb` block on the page and the **only** `upload.wikimedia.org` image
(both checked). The `<a>` wrapped nothing but the image and pointed only at the Wikimedia File:
page; the caption captions nothing once the image is gone; `.magnify` was already empty.

**What was deliberately kept.** All prose, and **39 of 40** `en.wikipedia.org` citations — the
script asserts that the only link removed is the dead `File:` one, and aborts otherwise.

Checked and found *not* to reference the image, so nothing else needed touching: `og:image`
(a local Ambimat card), `twitter:image`, JSON-LD, preload/prefetch, CSS `url()` backgrounds,
lazy-load `data-*src` attributes, `<picture>`/`<source>`.

### Result (1400px and 375px)

```
requests to the dead URL     0
"wikimedia" anywhere in DOM  0
.thumb/.thumbinner/.thumbcaption/.magnify/.thumbimage left   0
empty anchors                0
images 11, broken images     0        images missing alt 0
zero-size empty containers   0        horizontal scroll  no
h1 1, <main> present, heading sequence  h1 h2 h3 h2 h2 h2   (no skips)
en.wikipedia.org citations   39
og:image  unchanged (i0.wp.com/…/ambimat-barcode-1200x630-1.png)
Yoast indexable  UNCHANGED
```

The block was floated right, so the body text reflows into the space — no hole, no empty box, no
CLS from a reserved area.

**Separately found, not in scope, no action:** post 25727 also contains a dead Wikimedia hotlink,
but it is a `flamingo_inbound` record — a stored contact-form submission. Its permalink 404s, it
is not indexed and not in any sitemap. It is not site content.

---

## E. Orders CSP — `ENFORCING_AND_VERIFIED`

**Initial state:** `content-security-policy: upgrade-insecure-requests` only — Hostinger's
default, with no CSP of the site's own anywhere in `.htaccess` or the mu-plugins.

### Dependencies discovered — independently, from Orders' own runtime

Discovery was a 53-page static sweep **plus** a real browser walk of: home, a purchasable
product, `/cart/`, `/checkout/` with a real cart and **all three payment gateways selected**,
`/contact/`, `/my-account/`, search, and a quote-only product. Nothing was carried over from
ambimat.com's policy.

Orders turned out to be a genuinely different application: Astra 4.13.10 + Elementor +
WooCommerce, **three enabled gateways** (Juspay "Smart Gateway", PayGlocal "International Cards
and Apple Pay", PayPal), AddToAny, and **no consent tooling of any kind**.

| Origin | Directives | Where it was observed |
|---|---|---|
| `'self'` | all | everywhere |
| `fonts.googleapis.com` | style-src | the Google Fonts stylesheet, 53/53 pages |
| `fonts.gstatic.com` | font-src | the faces it pulls |
| `static.addtoany.com` | script, frame, img | the share widget — script **and** iframe |
| `www.googletagmanager.com` | script, connect | GA4 gtag (`G-03T01GG8K1`) |
| `www.google-analytics.com` | script, connect | GA4, seen on `/contact/` |
| `analytics.google.com` | connect | `/g/collect` — listed as the **bare** host, because `*.analytics.google.com` does not match it |
| `stats.g.doubleclick.net` | connect | GA4 with Google Signals |
| `www.google.co.in` | img | the Ads remarketing pixel |
| `ambimat.com` | script, style, font, img | `/contact/` embeds the Central Intake section, which brings ambimat.com's jQuery, CF7, the CF7 validation and conditional-field plugins, an accordion menu and its Font Awesome faces |
| `www.paypal.com` | script, connect, form-action | PayPal Commerce SDK + XHR |
| `c.paypal.com` | script, frame | PayPal's own frame |
| `c6.paypal.com` | img | PayPal imagery |
| `s.w.org`, `i0.wp.com` | img | WordPress emoji/SVG, Photon |
| `blob:` | img, **worker-src** | `wp-emoji-loader.min.js` builds its detection worker from a blob |

**No consent gate exists on Orders.** Checked both ways: no consent plugin in the 26 active
plugins, and zero `consent` entries in `dataLayer` at runtime. GA4 therefore fires
unconditionally and there is no accept/reject path to exercise on this host. That is a
pre-existing property of Orders, not something this policy changed, and it is reported rather
than glossed over.

### An obsolete dependency removed rather than whitelisted

The Central Intake embed also drags Site Kit's **Google AdSense loader**
(`ca-pub-9631847965894046`) onto `/contact/`. The page carries **zero `ins.adsbygoogle` units** —
the tag loads, phones home and renders no advertisement at all. Permitting it meant opening five
further third-party surfaces on the host that takes payments:
`googleads.g.doubleclick.net` frames, `ep1`/`ep2.adtrafficquality.google` (script + connect +
frame) and `www.google.com` frames.

It is **not in the policy**. Declining the loader closes all five at the root instead of
whitelisting a dead integration, and Central Intake itself is untouched — the CSP simply does not
permit something this host never needed.

Also deliberately absent: **`'unsafe-eval'`** (nothing asked for it across eight pages including
checkout with three gateways selected) and `paypalobjects.com` / `t.paypal.com` (plausible for
PayPal, never observed — guessing them in would defeat the pass).

### Report-Only pass

| Round | Result |
|---|---|
| RO rev 1 | home: `worker-src blob:` ×1. `/contact/`: 16 × `http://ambimat.com`, 3 × Font Awesome `font-src`, AdSense chain (pagead2 script, sodar script+connect, doubleclick/ep2/google.com frames). Product page: 0. |
| Action | **added** `worker-src 'self' blob:` and `ambimat.com` to `font-src`; **removed** `pagead2.googlesyndication.com` |
| RO rev 2 | 7 of 8 pages **0 violations** — including `/cart/`, `/checkout/` and `/my-account/`. `/contact/`: 24, all either the `http://` artefact or the deliberately-blocked AdSense chain. |

The 16 `http://ambimat.com` reports were **not** a missing origin: `upgrade-insecure-requests` is
enforced-only by spec, so a Report-Only policy evaluates the pre-upgrade URL. Predicted to
disappear under enforcement — and they did.

One defect I introduced and fixed inside the same pass: `Header onsuccess unset` is not supported
by this host's `mod_headers` emulation and emitted a literal malformed `ss: unset …` response
header. Removed; `Header always unset` alone does the job here. Verified 0 malformed headers.

### Final production header

```
content-security-policy: default-src 'self';
  script-src 'self' 'unsafe-inline' https://www.googletagmanager.com
    https://www.google-analytics.com https://static.addtoany.com https://www.paypal.com
    https://c.paypal.com https://ambimat.com;
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://ambimat.com;
  font-src 'self' data: https://fonts.gstatic.com https://ambimat.com;
  img-src 'self' data: blob: https://www.google-analytics.com https://www.googletagmanager.com
    https://www.google.co.in https://c6.paypal.com https://static.addtoany.com https://s.w.org
    https://ambimat.com https://i0.wp.com;
  connect-src 'self' https://www.google-analytics.com https://analytics.google.com
    https://*.analytics.google.com https://*.googletagmanager.com https://stats.g.doubleclick.net
    https://www.paypal.com;
  frame-src 'self' https://static.addtoany.com https://www.paypal.com https://c.paypal.com;
  worker-src 'self' blob:;
  frame-ancestors 'self'; base-uri 'self'; object-src 'none';
  form-action 'self' https://www.paypal.com https://juspay.in https://*.juspay.in
    https://payglocal.in https://*.payglocal.in;
  upgrade-insecure-requests
```

`upgrade-insecure-requests` is carried deliberately: it was this host's only CSP, and
`Header always set` **replaces** that header rather than adding to it.

`form-action` keeps `'self'` plus the hosts the gateway plugins name in their own source. Both
Juspay and PayGlocal hand off with `wp_redirect()` — a 302, which CSP does not govern — so
`'self'` alone should be sufficient. They are listed anyway because completing a payment is the
one step this campaign is forbidden to exercise, and a wrong `form-action` there breaks revenue.

### Post-enforcement verification

```
                                     1400px          375px
/                                    0 violations    0 violations
/product/…power-board-1-qty-rohs/    0               0
/cart/                               0               0
/checkout/                           0               0
/my-account/                         0               —
/?s=power+board                      0               —
/product/roboracer-core-kit-pro/     0               —
/contact/                            1               1     ← the AdSense loader, blocked by design
```

**Zero unexplained violations.** The only violation at either width is the advertising loader
that is intentionally not permitted, and it renders nothing.

Flows exercised **after** enforcement:

| Flow | Result |
|---|---|
| Header hygiene | 1 enforcing CSP, 0 report-only, 0 malformed, on 200s, a product page, `/contact/`, `/cart/` and a 404 |
| Home / product / brand / policy pages | all 200, `</html>` present, one `h1` |
| `/contact/` form | CF7, jQuery, jvcf7 validation and Font Awesome all load from ambimat.com; 75 stylesheets; 0 broken images |
| Contact form validation | empty submit → "Some details need correcting", 3 invalid fields, focus moved to `name` — **0 network calls, 0 CSP violations, no enquiry sent** |
| Cart | item added, cart renders 1 item @ $165.00 |
| Checkout | renders with **all three gateways** (International Cards and Apple Pay / Smart Gateway / PayPal), shipping option, total $243.80, place-order button, 1 PayPal iframe, 0 broken images, **0 violations** — no order placed, no payment triggered |
| Analytics | `gtag/js` loads, `analytics.google.com/g/collect` fires, remarketing pixel fires, config `G-03T01GG8K1` |
| Commercial governance | Core Kit **0** `add-to-cart`, Core Kit Pro **0**, Power Board **1** — quote-only rules intact |
| Sitemap | `/sitemap.xml` 301 → `wp-sitemap.xml` |
| Cleanup | test cart item removed; cart confirmed empty |

Note: `/contact/` returns two `</html>` because it embeds an entire ambimat.com page. That is the
pre-existing Central Intake architecture and was not altered.

---

## F. Orders wp-cli / PHP

```
Web PHP:   8.2.33          (X-Powered-By, and functionally proven — PayGlocal renders at checkout)
CLI PHP:   7.4.33          (/opt/alt/php74/usr/bin/php, whatever `env php` resolves to on PATH)
WP-CLI:    /usr/local/bin/wp — a raw phar with shebang `#!/usr/bin/env php`
```

**Root cause.** The phar's `env php` shebang picks up the PATH interpreter, which is alt-php 7.4.
`woocommerce-payglocal-3.0.0/vendor/composer/platform_check.php` fatals on anything below 8.1:

```php
if (!(PHP_VERSION_ID >= 80100)) { $issues[] = 'Your Composer dependencies require ">= 8.1.0"…'; }
```

So every plugin-loading wp-cli command died. `--skip-plugins` "worked" only because it never
loaded PayGlocal — it was hiding the mismatch, not solving it.

**Action taken — outcome (1), invoke WP-CLI with the correct interpreter. No configuration was
changed at all:**

```
/opt/alt/php82/usr/bin/php /usr/local/bin/wp <command>
```

php82 chosen deliberately to match the web runtime exactly (8.2.33). Verified with plugins
loaded, no `--skip-plugins`:

```
wp --info      PHP binary /opt/alt/php82/usr/bin/php, PHP version 8.2.33
wp plugin list --status=active --format=count      26
wp breeze purge --cache=all                        Success: Breeze all cache has been purged.
wp wc --help                                       available
```

`WP_CLI_PHP` is **ignored** on this host — that variable is honoured by wp-cli's shell wrapper,
and this installation is the bare phar. Documented so nobody loses time on it.

```
--skip-plugins still required?   NO — plugin-loading commands work under php82.
Public web PHP changed?          NO. Not touched, not requested, not needed.
Plugins/themes/WordPress changed? NO.
Plugin code modified?            NO.
```

Not done, and flagged rather than hidden: making php82 the account default (a PATH change or a
shell-profile edit) would affect every other domain on this shared account, including
ai.ambimat.com. That is a hosting-configuration decision for the owner, not a CLI fix. The
explicit invocation above needs no such change.

---

## G. Regression results

### Site monitor — Mac and phone reported separately

| | **Phone** (authoritative device) | Mac (final run) |
|---|---|---|
| sites total / reported / unreachable | 9 / 9 / 0 | 9 / 9 / 0 |
| pages crawled | **913** | 877 |
| broken pages | **0** | **0** |
| broken links | **0** | **0** |
| alerts | **0** | **0** |
| suspicious warnings | **0** | **0** |
| unverified links | 13 (all classified) | 8 (all classified) |
| partial | false | false |

Every unverified link on both runs carries an explicit classification
(`unverified-expected-antibot`, `-network-blocked`, `-tls-chain`, `-timeout`), a
`first_unverified` date and a `days_unverified` age.

**None is broken.** All eight from the final Mac run were re-verified by hand from the GoDaddy
production host, on a network without this LAN's appliance:

| URL | Monitor said | Truth from a clean network |
|---|---|---|
| `openscdp.org/scsh3/card.html` | expected-antibot | **200** (upgrades to https) |
| `wvu.edu` | expected-antibot | **200** |
| `iso.org/standard/77180.html` | expected-antibot | 403 to every automated client |
| `weforum.org/agenda/2022/12/…` | expected-antibot | 403 to every automated client |
| `nytimes.com/2018/…`, `/2019/…` | expected-antibot | paywalled publisher, refuses bots |
| `sanctionscanner.com/blog/…` | network-blocked | **200** — the LAN appliance, not the remote |
| `maximintegrated.com/…/5949.html` | timeout | **522** — Cloudflare origin down at the remote end. A transient remote outage, not a dead link and not a 404; the ageing ledger will surface it if it persists. |

### Accessibility — 46 pages

```
pages audited            46
fully clean              46
missing <main>            0
unlabelled controls       0
untitled iframes          0
links with no name        0
images missing alt        0
heading advisories        0 unexplained   (4 fixed this pass, 1 waived at the rule)
```

### SEO — nine sites, 718 pages

```
High     0
Medium   0
Low      8      (Ambimat 4, AmbiSecure 1, AmbiPower 1, AI Tools 1, Orders 1 — 10 -> 8)
```

| domain | pages | H | M | L | median ms | slow | 1st-sighting | prev median | host regression |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Ambimat | 228 | 0 | 0 | 4 | 1160 | 0 | 0 | 1129 | 0 |
| AmbiSecure | 308 | 0 | 0 | 1 | 62 | 0 | 0 | 76 | 0 |
| eSIM | 33 | 0 | 0 | 0 | 62 | 0 | 0 | 109 | 0 |
| AmbiPower | 26 | 0 | 0 | 1 | 60 | 0 | 0 | 91 | 0 |
| AmbiAutomation | 22 | 0 | 0 | 0 | 62 | 0 | 0 | 92 | 0 |
| RoboRacer | 8 | 0 | 0 | 0 | 62 | 0 | 0 | 71 | 0 |
| V2X | 71 | 0 | 0 | 0 | 63 | 0 | 0 | 88 | 0 |
| AI Tools | 7 | 0 | 0 | 1 | 62 | 0 | 0 | 79 | 0 |
| Orders | 15 | 0 | 0 | 1 | 82 | 0 | 0 | 82 | 0 |

### Latency model

Third consecutive run with a stored baseline. `slow_pages 0`, `slow_pages_first_sighting 0`, and
no site-wide regression finding on any of the nine — including eSIM (109 → 62 ms) and AmbiPower
(91 → 60 ms), whose medians moved by a third or more between runs. A ratio-only rule would have
had something to say about movement that size; the floor and the persistence requirement mean
this one correctly stayed silent.

### CSP violations

```
ambimat.com    enforcing (previous pass) — unchanged
orders         enforcing — 0 unexplained at 1400px and 375px
               1 explained: the AdSense loader, blocked by design, renders nothing
```

### Tests

| Suite | Passed | Failed |
|---|---|---|
| Rooted-Phone `test_a11y_rules.py` | **43** (34 → 43) | 0 |
| Rooted-Phone `test_unverified_classification.py` | 36 | 0 |
| Rooted-Phone `test_warning_signal_quality.py` | 43 | 0 |
| Rooted-Phone `test_iframe_and_defacement_invariants.py` | 26 | 0 |
| Rooted-Phone `test_head_get_fallback.py` | 18 | 0 |
| Rooted-Phone `test_redirect_base.py` | 4 | 0 |
| Rooted-Phone `test_site_inventory.py` | 5 | 0 |
| Rooted-Phone `test_schedule_times.py` | 4 | 0 |
| ambisecure-seo-tracker `pytest` | 100 | 0 |
| Ambimat-AI-site `vitest` (20 files) | 159 | 0 |
| **Mac total** | **438** | **0** |
| **Phone total** (6 monitor suites, run on the device) | **170** | **0** |

Nothing was excluded or skipped to reach these numbers.

---

## H. Deployment identity

| Target | Commit / artefact | Deployment | Live evidence | Rollback point |
|---|---|---|---|---|
| Rooted-Phone → **device** | `0af1718` | `scp` over adb port-forward, 6 files then 2 more | 11/11 sha256 MATCH; 170 assertions pass on-device; 913-page crawl from the phone | `~/sm_backup_20260908T121934Z` |
| ambimat.com `page-careers.php` | n/a (no repo) | wp-cli / ssh | `8ec9524814a4 → 75fd07bbee9c`, `php -l` OK | `page-careers.php.pre-cardheading-20260908T124212Z` |
| ambimat.com `ambi-heading-outline.php` | n/a | scp + `php -l` | careers + history CSS served; guards measured CLEAN | delete the file |
| ambimat.com post 1823 | n/a | `wp_update_post` + `wp_slash` | `8e0fe1419143 → 1817873ab681`; visible text byte-identical; **INDEXABLE UNCHANGED** | `/tmp/1823_after.html` + the captured row |
| ambimat.com post 16871 | n/a | `wp_update_post` + `wp_slash` | `382e245bf4d0 → b2ced8e54d86`; 0 wikimedia refs; **INDEXABLE UNCHANGED** | as above |
| orders `.htaccess` | n/a | ssh | enforcing CSP live, 1 header, 0 malformed | `.pre-cspenforce-20260908T132739Z` (plus `.pre-cspro-`, `.pre-cspro2-`, `.pre-onsuccessfix-`) |
| orders `ambimat-product-heading-outline.php` | n/a | scp + `php -l`, sha `39d52da7d801ebab` | product headings `h1 h2 h2 h2 h3 h3 h2 …`, guard CLEAN | delete the file |

No deployment bundled an intervening commit: the two repos that were **not** changed
(`ambisecure-seo-tracker`, `Ambimat-AI-site`) were confirmed at their existing origin/main SHAs
and nothing was pushed from them. The device sync copied only the six/eight named files, never a
whole tree, so no unrelated held work could ride along.

---

## I. Anything still requiring owner decision

`NO FURTHER OWNER DECISIONS REQUIRED`

Two items are recorded for awareness, neither of which needs a decision to close this campaign:

* **Orders has no consent management.** GA4 and the Ads remarketing pixel fire unconditionally
  because no consent plugin exists on that host. Pre-existing, unchanged by this work, and
  already tracked in the estate's own notes.
* **Making php82 the default CLI interpreter on the Hostinger account** would remove the need for
  the explicit invocation in section F, but it is a shared account serving other domains, so it
  is a hosting-configuration change rather than a fix. The documented invocation needs nothing.

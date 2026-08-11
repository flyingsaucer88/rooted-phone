# Prompt — orders.ambimat.com remediation over SSH (evidence 2026-08-11)

Supersedes the Orders section of `site_remediation_prompts_20260804.md`, which was written from the
degraded 08-04 run. Paste everything below the line into a fresh Claude Code session.

---

You are remediating **`https://orders.ambimat.com`** — a live WooCommerce store that takes payments.
Be conservative, evidence-led, reversible, transactional. Anything that could affect the cart,
checkout, accounts or payment flow is out of bounds unless explicitly listed below.

## Access

```
ssh ambimat-godaddy-production          # 166.62.28.103, user xemtd1m9scay,
                                        # key ~/.ssh/ambimat_production_preflight
```

Confirm which docroot serves `orders.ambimat.com` before anything else — this host also serves other
Ambimat sites. WordPress + WooCommerce. Establish whether `wp` (WP-CLI) is on PATH; do not install it.

## Scope boundary — absolute

`orders.ambimat.com` only. Do not touch `ambimat.com`, `ambisecure.`, `ambiautomation.`, `ambipower.`,
`esim.`, `roboracer.`, `businesscard.`, `erp.`, any staging host, DNS, CDN, or the monitoring phone.

## Baseline (2026-08-11, from the phone's 10:23 site-monitor and 11:21 SEO runs)

36 pages crawled, **all HTTP 200**. Certificate valid 37 days (`Sep 17 22:18:48 2026 GMT`).
0 broken pages, 0 broken internal links, 0 redirect chains, avg response 394 ms.
Schema coverage **1.0** — Product on all 5 products, FAQPage on 7, BreadcrumbList, Organization.
Alt-text coverage 1.0. Content quality avg 68.1. AI-readiness 31.2 (13 of 18 pages below 40).

### CLOSED — do not re-investigate the 2026-08-04 TLS failure

The 08-04 run reported `CERTIFICATE_VERIFY_FAILED: EE certificate key too weak` and 22/36 coverage.
Eleven consecutive runs now bracket it:

| Runs | pages | Certificate |
| --- | ---: | --- |
| 08-01 → 08-03 | 36 | valid, 45–47d, `Sep 17 22:18:48 2026 GMT` |
| **08-04** | **22** | **`CERTIFICATE_VERIFY_FAILED`** |
| 08-05 → 08-11 | 36 | valid, 37–43d, `Sep 17 22:18:48 2026 GMT` |

`openssl s_client` confirms the live leaf is ECDSA P-256, `NotBefore Jun 19 2026`, chaining to ISRG
Root X2 with `Verify return code: 0`. The certificate never changed and is not weak. The 08-04 run
coincided with a phone-side network outage (the 11:00 SEO job logged `network unavailable`, and the
same run failed SSL against `ambimat.com`, whose own certificate verified fine). Environmental, not a
site defect. **No TLS, certificate or hosting change is in scope.**

## Work in this order

### Gate 0 — state before touching anything

Record date/time (IST+UTC), the resolved docroot, `wp option get siteurl` / `home` (must be exactly
`https://orders.ambimat.com`), WooCommerce + WordPress + PHP versions, active theme, SEO plugin and
version, and hashes of every file you may edit. If identity is ambiguous or points at staging, STOP
with `PRODUCTION_IDENTITY_GATE_FAILED_NO_MUTATION`.

Take a full checkout smoke-test baseline **before** any change: load `/`, a product page, add an item
to the cart, load `/cart/`, load `/checkout/` to the payment step. Record status codes and any PHP
notices. You will repeat this after every batch. **If you cannot establish this baseline, stop — do
not make changes you cannot prove safe.**

### P1 — Security headers (four of five missing, on the payment host)

Present: `content-security-policy`. **Missing: `x-frame-options`, `x-content-type-options`,
`referrer-policy`, `strict-transport-security`.** This is the only site in the estate missing any.

Add the four. Suggested starting values — verify each against the live store before committing:
- `X-Frame-Options: SAMEORIGIN` — check first that no payment gateway or 3-D Secure step frames the
  site from another origin. If one does, use CSP `frame-ancestors` instead and skip this header.
- `X-Content-Type-Options: nosniff` — safe.
- `Referrer-Policy: strict-origin-when-cross-origin` — confirm no analytics or affiliate attribution
  depends on a full referrer.
- `Strict-Transport-Security: max-age=86400` to start. **No `includeSubDomains`, no `preload`** — this
  is a subdomain of a shared parent, and preload is effectively irreversible. Raise `max-age` in a
  later, separate change only after a week of clean runs.

Apply via the same mechanism that already emits the CSP so the config stays in one place. Add them
one at a time, re-running the checkout smoke test after each. A header that breaks checkout gets
reverted immediately, not debugged in production.

### P2 — Meta descriptions: 35 of 36 pages, and 4 missing canonicals

**Missing meta description** on effectively everything: `/`, all five products, both product
categories, and all five policy pages (`/privacy-policy/`, `/refund-and-cancellation-policy/`,
`/shipping-policy/`, `/terms-and-conditions/`, `/electronic-manufacturing/`).

**Missing canonical** on four URLs: `/`, `/product-category/fido/`, `/product-category/pcb-board/`,
and the bare `https://orders.ambimat.com` form.

Both point at SEO-plugin configuration rather than 35 hand-written pages:
- Determine which SEO plugin is active and whether description templates are set for `product`,
  `product_cat` and `page`. Configure templates for the post types; WooCommerce product descriptions
  can derive from the short description.
- The **homepage having no canonical is the highest-value single fix here** — do that one first and
  independently, then verify the rendered `<head>`.
- Hand-write descriptions only for `/` and the two product categories, where a template will produce
  something useless.

Also verify: `/shipping-policy` and `/shipping-policy/` are both being crawled as distinct URLs.
Confirm whether the site canonicalises trailing slashes; if not, that is a one-line rewrite fix, but
check it does not disturb WooCommerce's own endpoint routing.

### P3 — 20 crawlable `?add-to-cart=` URLs

Twenty of the 36 crawled URLs are `?add-to-cart=<id>` variants — on `/`, on four product pages, and on
both product categories. Every one renders the cart page under the title "cart – ambimat electronics".

They are correctly `noindex`, so this is **not** an indexing defect — but they consume 56% of crawl
budget and produce a 20-page duplicate-title cluster. Fix at the source, not with `noindex`:
- Add `rel="nofollow"` to add-to-cart links (WooCommerce has a filter for this), and/or
- `Disallow: /*?add-to-cart=` in `robots.txt`.

Verify afterwards that adding to the cart still works from a product page, a category page and the
homepage — that is the whole point of those links.

### P4 — Report only, do not apply

- **Orphans:** `/my-account/`, `/share-cart/`, `/shipping-policy/`. The first two are expected.
  `/shipping-policy/` should probably be footer-linked — propose it.
- **Catalog modelling:** `/product/f1tenth-power-board-1-qty-rohs-compliant/` and
  `/product/f1tenth-power-board-rohs-com-multipliant/` are single-quantity and multi-quantity variants
  of one board sold as two products; the second slug also looks mangled ("rohs-com-multipliant").
  These are WooCommerce variations, not separate products. **Do not change slugs or merge products** —
  that breaks order history and existing links. Report it as a catalog decision for the owner.
- Duplicate title "shipping policy – ambimat electronics" across 2 pages.
- 6 pages scoring below 55 on content quality.

## Findings you must NOT act on — reject these explicitly in your report

- **The 4 high-severity `Page is noindex` findings** on `/cart/`, `/checkout/`, `/my-account/`,
  `/share-cart/`. All four are correct. Transactional endpoints must not be indexed. Do not remove
  `noindex` to clear an audit line.
- **"`/cart/` duplicate intent vs `/checkout/` — merge into one cornerstone and 301-redirect the
  thinner URL."** Following this would break the store. Reject in writing.
- **Thin-content findings** on `/cart/` (104 words), `/checkout/` (104), `/my-account/` (60),
  `/share-cart/` (46). Normal and correct for transactional pages. Do not pad them.
- **"Missing primary cluster: Ordering / ecommerce portal — publish a cornerstone page."** A store
  does not need a marketing cornerstone page about being a store. Owner's call, not a defect.
- **16 broken external links, all `www.addtoany.com`** — the share-button widget returning 403 to
  HEAD-only requests the crawler never retried with GET. Not a defect. Optionally confirm one with a
  single GET.
- **35 "broken outbound" internal links** — the estate-wide trailing-slash inventory artifact. The
  10:23 run, which actually issues HTTP requests, found zero broken internal links.
- **36 `suspicious-pattern` warnings** — `display:none`-class CSS matches, one per page.

## Mutation rules

Smallest change, one at a time. Record before-state → apply → check exit status → verify the URL →
**re-run the full checkout smoke test** → compare canaries against baseline → stop and roll back that
batch on any regression.

Before the first write: targeted timestamped backup of every file and DB row you will change, plus a
validated rollback script. If validation fails, STOP with `ROLLBACK_GATE_FAILED_NO_MUTATION`. Prefer
WP-CLI/WordPress APIs over direct SQL; if direct SQL looks unavoidable, stop and ask.

Never: bulk redirects · redirect-to-homepage · merging or deleting products · changing product slugs ·
editing order data · touching payment gateway config · broad SEO-plugin reindex or cache flush ·
permalink resave · plugin/theme updates · disabling security controls · touching another host.

**Canaries after every batch:** `/` · one product page · one product category · `/cart/` ·
`/checkout/` to the payment step · `/robots.txt` · the sitemap index · one untouched policy page.
Acceptance = every intended change passes, checkout completes to the payment step, no new 4xx/5xx, no
redirect loop, no accidental `noindex` on an indexable page, no `noindex` removed from a transactional
page, no PHP warnings.

## Stop conditions

Identity uncertain · the checkout smoke test cannot be established or fails · a fix would reach another
hostname · backup or rollback unvalidated · unexpected file/DB drift · a payment-path change would be
required · plugin or theme update required · compromise suspected · any canary fails.
Do not improvise past one.

## Deliverables

Timestamped report directory with `FINAL_REPORT.md`, `baseline.json`, `proposed_action_matrix.csv`
(`ID | problem | evidence | root cause | exact change | files/rows affected | risk | rollback |
verification`), `changes_applied.csv`, `verification_before.json`, `verification_after.json`,
`verification_diff.md`, `rollback/README.md`, a secrets-redacted command log, and a checksums manifest.

**Finish with exactly one:**
`ORDERS_SEO_REMEDIATION_VERIFIED` · `ORDERS_SEO_REVIEW_COMPLETE_NO_MUTATION` ·
`ORDERS_SEO_REMEDIATION_ROLLED_BACK` · `ORDERS_SEO_REVIEW_BLOCKED_NO_MUTATION`

Never describe a partial or failed verification as successful.

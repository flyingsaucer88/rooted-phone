# SEO remediation prompts — evidence 2026-08-14

Built from today's phone runs: site-monitor 10:00–10:29 (835 pages, 7 sites) and SEO 11:00–11:45
(824 pages), plus 42 SEO reports and 304 site-monitor reports going back to 2026-07-01.

**Supersedes** `site_remediation_prompts_20260804.md`, `ambimat_seo_remediation_prompt_20260811.md`
and `orders_seo_remediation_prompt_20260811.md`.

Priority: **P0 ambimat.com performance** · P1 ambimat.com FAQ regression · P2 Orders security headers
· P3 the rest.

---

## Learnings from 6 weeks of history — read before using any section

These are the traps this estate has actually produced. They are why several "findings" below are
marked closed rather than actionable.

**1. A truncated crawl looks exactly like an improvement.** Today's 10:00 site-monitor run hit its
1200 s per-site budget on ambimat.com and stopped at 384 of ~461 pages. Its counts fell —
`no_desc` 136→71, `noindex` 10→1, `no_canon` 10→1, `dup_titles` 17→10 — and **none of that is a
fix**. The run also logged `internal link check stopped early (0/65 checked)` and
`external link check stopped early (0/20 checked)`, so its "0 broken links" means the check never
ran. Always read `timed_out`, `partial` and `skipped[]` before comparing counts to a previous day.

**2. Use the sibling sites in the same run as controls.** On 2026-08-04 the Orders crawl reported
`CERTIFICATE_VERIFY_FAILED: EE certificate key too weak` and it looked like a server-side cert
swap. It was not: `openssl s_client` showed an unchanged ECDSA P-256 leaf valid since 19 June,
verifying with return code 0, and eleven runs bracket the single bad day. The tell was that the
*same run* also failed SSL against `ambimat.com`, whose own cert was fine — i.e. the whole client
path was sick, not the host. Conversely today's ambimat slowness **is** real, because AmbiSecure
(232 ms) and eSIM (327 ms) were healthy in the same minute. One anomalous run with unhealthy
controls = environmental. One anomalous run with healthy controls = the site.

**3. Most findings here are 17 days old, not new.** ambimat.com has been frozen at
`ai 41.1 / faq 6 / og_incomplete 127 / heading_issues 327` every single run from 2026-07-28 to
2026-08-11. Nothing from the earlier prompts was actioned. Do not assume a finding is fresh, and do
not assume a previous session fixed anything — verify live first.

**4. Work does land, so verify before redoing it.** Between 2026-08-11 and 2026-08-14 someone
remediated Orders properly: all 15 real pages gained a canonical and a meta description,
`og_incomplete` went 6 → **0**, AI-readiness 31.2 → 42.5, and the mangled product slug
`f1tenth-power-board-rohs-com-multipliant` became proper `roboracer-power-board-*` slugs. The
2026-08-11 Orders prompt's P2 is **done**. Re-check before touching anything.

**5. A deploy can trade one metric for another.** On 2026-08-12 ambimat.com's `og_incomplete`
improved 127 → 120 while `FAQPage` collapsed **6 → 1**, with total pages moving only 437 → 436. Not
crawl variance — an actual removal. Whatever shipped that day bought 7 OG completions at the cost of
5 FAQ schemas, on the site that had almost no FAQ coverage to begin with.

**6. Per-page counts scale with the catalog.** Orders' crawlable `?add-to-cart=` URLs grew 20 → 30
between 08-11 and 08-14 purely because products were added. Fixing the symptom page-by-page does not
hold; fix it at the source.

---

## Common Rules — applies to every section below

You are working on LIVE production. Conservative, evidence-led, reversible, transactional. Template
and configuration fixes strongly preferred over bulk per-page edits.

**Access:** `ssh ambimat-godaddy-production` (166.62.28.103, user `xemtd1m9scay`, key
`~/.ssh/ambimat_production_preflight`). Confirm which docroot serves your target host before
anything — this server carries several Ambimat sites. Establish whether `wp` is on PATH; do not
install anything.

**Scope:** the single hostname named in your section. Never touch a sibling host, `ambimat.com` from
an Orders session or vice versa, DNS, CDN, or the monitoring phone.

**Reproduce before you act.** Every finding below is what the phone recorded at 10:00–11:45 IST on
2026-08-14. Reproduce each one now with a small, bounded, clearly-identified request budget. Anything
you cannot reproduce closes as `NOT_REPRODUCIBLE` — not "fixed".

**Gates.** (0) Record time (IST+UTC), docroot, `wp option get siteurl`/`home`, versions, and hashes
of every file you may touch; if identity is ambiguous or points at staging, STOP with
`PRODUCTION_IDENTITY_GATE_FAILED_NO_MUTATION`. (1) Check for work in flight —
`ambimat-featured-image-remediation`, `ambi-p3-ss-og.php` or quarantined variants, MU-plugins,
`.htaccess`, recent `wp-content` mtimes — and stop if your fix collides with it; never reactivate
quarantined code. (2) Read-only baseline of every candidate plus canaries. (3) Action matrix, one row
per mutation: `ID | problem | evidence | root cause | exact change | files/rows affected | risk |
rollback | verification` — a row missing any column is not actionable. **"No change required" is a
complete result.** (4) Targeted timestamped backup + a rollback script you have validated; if
validation fails, STOP with `ROLLBACK_GATE_FAILED_NO_MUTATION`.

**Mutation:** smallest change, one at a time. Before-state → apply → check exit status → verify the
URL → re-test canaries → compare to baseline → stop and roll back the batch on any regression.
Never: bulk redirects · redirect-to-homepage · editing content to force reindexing · changing publish
dates · changing slugs without proven need · broad Yoast reindex / cache flush / permalink resave /
rewrite flush · plugin or theme updates · deleting anything · disabling security controls.

**Prefer** WP-CLI and WordPress APIs over direct SQL. If direct SQL looks unavoidable, stop and ask.

**Stop conditions:** identity uncertain · evidence contradicts live behaviour · a fix reaches another
hostname · backup/rollback unvalidated · unexpected drift · a broad operation would be required · a
plugin/theme update would be required · compromise suspected · any canary fails.

**Deliverables:** timestamped report directory with `FINAL_REPORT.md`, `baseline.json`,
`proposed_action_matrix.csv`, `changes_applied.csv`, `verification_before.json`,
`verification_after.json`, `verification_diff.md`, `rollback/README.md`, a secrets-redacted command
log, and a checksums manifest. Do not claim Google has reindexed anything.

---

# `ambimat.com`

Target host: **`https://ambimat.com`** only. Canaries: homepage · `/about/` · one blog post · one
`/design/*` page · `/robots.txt` · sitemap index · one untouched `/tag/*` · one untouched paginated
blog index.

## P0 — Performance regression that began today. Do this before any SEO work.

| | Aug 12 | Aug 13 | **Aug 14** |
| --- | ---: | ---: | ---: |
| ambimat.com avg response | 626 ms | 595 ms | **2370 ms** |
| ambimat.com slow pages | 0 | 0 | **145 / 435** |
| AmbiSecure (control, same run) | 284 ms | 327 ms | 232 ms |
| eSIM (control, same run) | 341 ms | 256 ms | 327 ms |

Four independent signals, all on 2026-08-14:
1. The 10:00 site-monitor crawl **hit its 1200 s per-site budget for the first time** (10:00:05 →
   10:20:14), stopping at 384 pages. Duration trend over the preceding week: 13:47, 13:21, 19:56,
   14:17, 16:36, 15:35, **20:14**.
2. Three pages returned `('Connection aborted.', RemoteDisconnected('Remote end closed connection
   without response'))` — `/cyberchef/`,
   `/mobile-payments-what-is-nfc-card-emulation-mode/`, and
   `/choosing-the-right-surface-finish-for-your-pcb-project-based-on-cost-and-availability/`.
3. The 11:00 SEO run took **45 minutes** against a 22-minute norm.
4. 145 of 435 pages flagged slow, against 0 the previous two days.

The sibling sites were healthy in the same runs, so this is ambimat.com, not the phone or the network.

**Investigate server-side, read-only first:** load average and memory, PHP-FPM / worker pool
saturation and any `max_children` warnings, slow-query log, error logs around 10:00–11:45 IST today,
whether a backup / cron / indexer job overlaps that window, disk and inode usage, and whether
`RemoteDisconnected` corresponds to a worker being killed. Compare against the same window on 08-12
and 08-13.

**Do not** change cache policy, W3TC front-page cache lifetime, or PHP limits as a first move.
Diagnose, report, and propose. If the cause is a resource limit that needs raising, that is a hosting
change — surface it with evidence rather than applying it silently.

Until this is resolved, treat today's ambimat SEO numbers as an unreliable baseline.

## P1 — Restore the 5 lost FAQPage schemas

`FAQPage` went **6 → 1** on 2026-08-12 and has stayed at 1 through today, while total pages moved only
437 → 436. This is a removal, not variance. It is also the single largest AI-readiness lever on this
site (FAQ is worth 20 of 100 points, and ambimat scores 41.1 against 83–97 across the estate).

The report does not name which pages lost the markup. Recover it:
- Diff the deploy / theme / plugin changes around 2026-08-11 → 2026-08-12 (git log on the docroot if
  versioned, else file mtimes under `wp-content`).
- The same change improved `og_incomplete` 127 → 120, so look for whatever touched head output or
  schema emission — a Yoast setting, a schema filter, or an OG/social plugin.
- Identify the 5 pages, confirm the Q/A content is still visible on them, and restore the markup.

**Do not** author new FAQ content to make the number go up. Restoring removed markup for questions
that are genuinely on the page is the task; inventing questions is not.

## P2 — Three site-wide internal link targets flagged broken

Of 1359 reported "broken outbound" internal links, **1305 are just three targets, each linked from
all 435 pages** — i.e. site navigation:

| Target | Occurrences | Note |
| --- | ---: | --- |
| `https://ambimat.com` | 435 | bare domain, no trailing slash — the known inventory artifact |
| `https://ambimat.com/about/` | 435 | known to redirect to `/about/company-overview/` |
| `https://ambimat.com/design/ambi-iot/security/` | 435 | **new — not previously flagged** |

The bare-domain entry is a crawler normalisation artifact and closes with a single direct fetch. The
other two are real navigation links worth checking: fetch each directly and record status, redirect
chain and final URL. If `/about/` still 301s, point the nav and sitemap at the final URL. If
`/design/ambi-iot/security/` 404s or redirects, that is a broken link in the site header/footer on
every page — fix the nav target.

Note the 10:00 crawl's internal link check never ran today (0/65), so this is the only internal-link
evidence available and it is inferred from the SEO crawler's page inventory rather than live fetches.
Verify with real requests before changing anything.

## P3 — The long-standing gaps (unchanged for 17 runs)

Frozen at these values from 2026-07-28 through today. Confirm each still reproduces before acting.

- **AI-readiness 41.1** — 0 pages above 70, 209 below 40. Estate: eSIM 97.1, AmbiPower 85.9,
  AmbiSecure 83.0, AmbiAutomation 57.2. Sub-scores on a typical weak page:
  `structured_data 17/25 · faq 0/20 · headings 8/15 · content_depth 0/15 · entity_coverage 0/15 ·
  answer_shape 3/10`. Structured data is already healthy (schema coverage 1.0); the deficit is FAQ
  (P1) and headings (below).
- **326 pages with a skipped heading level.** 75% of pages with a uniform shape is a **template**,
  not 326 authoring errors — and ambimat is the only site in the estate with any heading issues
  (every other host is 0, except Orders at 17). Sample 5–8 structurally different pages, identify the
  exact jump, fix it in the child theme, re-sample, and confirm no CSS regression.
- **120 pages with incomplete Open Graph** and a comparable count missing meta descriptions. Same
  likely root cause: no description for Yoast to render into either tag. Fix via Yoast description
  templates per post type, not by hand-writing 120 descriptions. Note most affected URLs are `/tag/*`
  and `/category/*` archives — decide deliberately whether those should carry descriptions at all.
- **9 duplicate-title groups and 3 duplicate-description groups** — editorial. Report with URLs.
- **12 orphans:** `/ambi-space/`, `/ambi-sense/`, `/ambi-pay/`, `/ambi-secure/`, `/ambi-power/`,
  `/ambi-con/`, `/by-industry/`, `/by-technologies/`, `/f1tenth/`, `/terms-conditions/`,
  `/refund-cancellation-policy/`, `/event/ambimat-history/`. Several are legal pages legitimately
  reached only from the footer — check the rendered footer before treating any as a defect.
- **`content-security-policy` missing** (the only absent security header; the other four are present).
  Propose `Content-Security-Policy-Report-Only` first and observe. **Do not enforce a CSP this run.**
- Sitemap lists `/about/`, which redirects. Point it at the final URL.

## ambimat.com — do NOT act on these

- **The 29 high-severity "weak page" findings advising "merge into one cornerstone and 301-redirect
  the thinner URL."** Roughly half are `/tag/<topic>/` versus the article that tag points at. Following
  that advice dismantles the taxonomy. A tag archive and an article do not compete for one query.
- **`Page is noindex` on `/category/general/`** — the single high-severity audit finding. On a full
  crawl this page and its 9 paginated children are all `noindex, follow` and all missing canonicals, a
  consistent pattern that reads as a deliberate Yoast archive setting. Verify in `wpseo_titles`; if
  intentional, close it as correct. Today's run shows only 1 such page because the crawl truncated —
  do not read that as a fix.
- **`suspicious-pattern` (381), `external-iframe` (18), `defacement-marker-in-content` (2),
  `japanese-spam` (2), `seo-spam` (1).** Respectively: `display:none`-class CSS; reCAPTCHA / Maps /
  WordPress `/embed/` cards; "hacked by" and "owned by" inside security articles the tool itself
  annotates "likely editorial"; the word "betting" on the Application Identifier pages; the substring
  "xxx" on `/section-5-basic-organizations/`. None is a defect.
- The 54 non-sitewide `broken_outbound` entries beyond the three targets in P2 — trailing-slash
  variants, same artifact.

---

# `orders.ambimat.com` (WooCommerce, takes payments)

Target host: **`https://orders.ambimat.com`** only.

**Before anything: establish a checkout smoke test** — load `/`, a product page, add to cart, load
`/cart/`, load `/checkout/` to the payment step. Record status codes and any PHP notices. Re-run it
after every batch. If you cannot establish this baseline, **stop** — do not make changes you cannot
prove safe. This is a gate, not a verification step.

## Already fixed between 08-11 and 08-14 — verify, do not redo

All 15 real pages now carry both a canonical and a meta description (was 4 missing canonicals
including the homepage, 35 missing descriptions). `og_incomplete` is **0**. AI-readiness 31.2 → 42.5.
Product slugs cleaned up. A `/contact/` page was added. Confirm live, record as closed, move on.

## P1 — Four of five security headers still missing

Present: `content-security-policy`. **Missing: `x-frame-options`, `x-content-type-options`,
`referrer-policy`, `strict-transport-security`.** Unchanged since 07-28. This is the only site in the
estate missing any, and it is the one taking payments.

Add them one at a time, re-running the checkout smoke test after each:
- `X-Content-Type-Options: nosniff` — safe, do this first.
- `Referrer-Policy: strict-origin-when-cross-origin` — confirm no analytics or affiliate attribution
  needs a full referrer.
- `X-Frame-Options: SAMEORIGIN` — **first** confirm no payment gateway or 3-D Secure step frames the
  site from another origin. If one does, use CSP `frame-ancestors` instead and skip this header.
- `Strict-Transport-Security: max-age=86400` — **no `includeSubDomains`, no `preload`.** This is a
  subdomain of a shared parent and preload is effectively irreversible. Raise `max-age` later, as a
  separate change, after a week of clean runs.

A header that breaks checkout gets reverted immediately, not debugged in production.

## P2 — 30 crawlable `?add-to-cart=` URLs (67% of the crawl)

30 of 45 crawled URLs are `?add-to-cart=<id>` variants, all rendering the cart page under the single
title "cart – ambimat electronics". They grew 20 → 30 since 08-11 purely because products were added,
so this scales with the catalog.

They are correctly `noindex`, so this is **not** an indexing defect — but it wastes two-thirds of
crawl budget and creates a 30-page duplicate-title cluster. Fix at source: `rel="nofollow"` on
add-to-cart links (WooCommerce provides a filter) and/or `Disallow: /*?add-to-cart=` in `robots.txt`.

Afterwards verify adding to cart still works from a product page, a category page and the homepage.

## P3 — Smaller items

- **`heading_issues` on 17 of 17 pages** — 100%, including a `h2 → h4` jump on the homepage. Same
  template-level fix as ambimat's P3. Small site, so verify each page after.
- `/shipping-policy` and `/shipping-policy/` are both crawled as distinct URLs, as are the bare domain
  and `/`. Check trailing-slash canonicalisation, but confirm any rewrite does not disturb WooCommerce
  endpoint routing.
- Sitemap lists `/checkout/`, which redirects — and `/checkout/` is `noindex`. It probably should not
  be in the sitemap at all.
- 3 orphans: `/my-account/`, `/share-cart/`, `/shipping-policy/`. First two expected; propose a footer
  link for the third.
- 4 pages below 55 on content quality — all transactional.

## orders.ambimat.com — do NOT act on these

- **The 4 high-severity `Page is noindex` findings** on `/cart/`, `/checkout/`, `/my-account/`,
  `/share-cart/`. All correct. Transactional endpoints must not be indexed.
- **"`/cart/` duplicate intent vs `/checkout/` — merge and 301-redirect the thinner URL."** This would
  break the store. Reject in writing.
- **Thin-content findings** on `/cart/`, `/checkout/`, `/my-account/`, `/share-cart/` (46–104 words).
  Normal and correct. Do not pad them.
- **"Missing primary cluster: Ordering / ecommerce portal — publish a cornerstone page."** A store does
  not need a marketing cornerstone about being a store. Owner's call, not a defect.
- **16 broken external links, all `www.addtoany.com`** — share-button widget, 403 to HEAD-only requests
  the crawler never retries with GET. Not a defect.
- **The 2026-08-04 TLS failure.** Closed — see Learning 2. No TLS, certificate or hosting change is in
  scope.

---

# The other five sites

All five are healthy. Expect `SITE_REVIEW_COMPLETE_NO_MUTATION` for most. Apply the Common Rules;
target one host per session.

| Host | pages | AI | State |
| --- | ---: | ---: | --- |
| `esim.ambimat.com` | 33 | **97.1** | Best in estate. FAQ 33/33, all headers, 0 audit findings, cert 53 d. Confirm and close: 33 `external-iframe` + 33 `suspicious-pattern` warnings are one-per-page template noise; 3 external 403s are citation links; 1 "owned by" is editorial. |
| `ambipower.ambimat.com` | 25 | 85.9 | FAQ 25/25, all headers, cert 89 d. One item: `/privacy/` has incomplete Open Graph. `/resources/downloads/` is `noindex` — verify it is deliberate. |
| `ambisecure.ambimat.com` | 285 | 83.0 | FAQ 182/285, all headers, cert 89 d, 0 orphans, 0 audit high/medium. The one question worth work: 29 `/tags/*` archives are `noindex` while 62 "broken outbound" links point from `/blog/` at those same URLs — the two facts are the same fact. If the tags are deliberately unindexed, both close. Do not flip 29 pages' indexability on your own judgement. 6 `defacement-marker` and 1 `japanese-spam` warning are editorial. |
| `ambiautomation.ambimat.com` | 22 | 57.2 | All headers, 0 audit findings, **cert 35 d** (nearest expiry — monitor warns at 21 d). One real item: `/contact` plus 6 `?purpose=` query variants share one title and description. Fix is a self-referencing canonical on `/contact`, not 7 distinct titles and not `noindex`. Verify the current canonical first. |
| `roboracer.ambimat.com` | 7 | 55.0 | Cleanest report in the estate — 7 pages, zero warnings, all headers, cert 55 d. Two editorial notes only: `/` vs `/autonomous-racing-robotics-kit.html` flagged duplicate intent (**do not** apply the suggested 301 — it would redirect the homepage or the primary product page); `/getting-started.html` has no FAQPage schema. One external 403 to `robo-racer.slack.com/signup` is a link-rot check for the owner, not a site fix. |

Certificate expiry across the estate today: ambimat 188 d · AmbiSecure 89 d · AmbiPower 89 d ·
RoboRacer 55 d · eSIM 53 d · AmbiAutomation 35 d · Orders 34 d. All clear of the 21-day warn.

---

## Final integrity statement — exactly one

`SITE_REVIEW_COMPLETE_NO_MUTATION` · `SITE_TARGETED_REMEDIATION_VERIFIED` ·
`SITE_TARGETED_REMEDIATION_ROLLED_BACK` · `SITE_REVIEW_BLOCKED_NO_MUTATION`

Never describe a partial or failed verification as successful.

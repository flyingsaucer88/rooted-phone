# Prompt — ambimat.com SEO remediation over SSH (evidence 2026-08-11)

> **SUPERSEDED by `seo_remediation_prompts_20260814.md`** — built on fresher evidence and on
> 6 weeks of trend history. Kept for the audit trail.

Paste everything below the line into a fresh Claude Code session. Evidence came from the rooted
phone's scheduled runs; the session itself works over SSH against production.

---

You are remediating SEO defects on the LIVE production website **`https://ambimat.com`** over SSH.
Be conservative, evidence-led, reversible, transactional. Template and configuration fixes are
strongly preferred over bulk per-page edits.

## Access

```
ssh ambimat-godaddy-production          # 166.62.28.103, user xemtd1m9scay,
                                        # key ~/.ssh/ambimat_production_preflight
```

WordPress, Yoast SEO, W3 Total Cache, theme `launchseat`. Establish early whether `wp` (WP-CLI) is on
PATH; if it is not, find it or fall back to reading files directly — do **not** install anything.

## Scope boundary — absolute

`ambimat.com` only. Do not touch `ambisecure.` / `ambiautomation.` / `ambipower.` / `orders.` /
`esim.` / `businesscard.` / `erp.` / `roboracer.ambimat.com`, any staging host, DNS, CDN, or the
monitoring phone. Classify out-of-scope findings; never change them.

## Evidence baseline (2026-08-11, from the phone's own runs)

Site-monitor 10:00 (461 pages) · SEO run 11:00 (437 pages crawled).

- **All 461 crawled URLs return HTTP 200.** 0 broken pages, 0 broken internal links.
- TLS valid 191 days. Security headers present: `x-frame-options`, `x-content-type-options`,
  `referrer-policy`, `strict-transport-security`. **Missing: `content-security-policy` only.**
- Schema coverage **1.0** (437/437) — BreadcrumbList, WebSite, Organization on every page; Article 186.
- Content quality avg 92.4, none below 55. Alt-text coverage 1.0 across 3893 images.
- `redirect_chains` 0 · `canonical_off` 0 · `missing_viewport` 0 · `missing_lang` 0.

**AI-readiness 41.1/100** — 0 pages above 70, 209 below 40. Estate comparison:

| | pages | AI-ready | FAQPage | og incomplete | heading issues | avg ms |
|---|---:|---:|---:|---:|---:|---:|
| eSIM | 33 | 97.1 | 33/33 | 0 | 0 | 231 |
| AmbiPower | 25 | 85.9 | 25/25 | 1 | 0 | 246 |
| AmbiSecure | 285 | 83.0 | 182/285 | 0 | 0 | 313 |
| **ambimat.com** | **437** | **41.1** | **6/437** | **127** | **327** | **712** |

Sub-scores on a representative weak page (`/tag/automotive-security/`, 28/100):
`structured_data 17/25 · faq 0/20 · headings 8/15 · content_depth 0/15 · entity_coverage 0/15 ·
answer_shape 3/10`. The deficit is concentrated in **FAQ schema** and **heading hierarchy** — not in
structured data, which is already healthy.

## Work in this order. Stop and report if any gate fails.

### Gate 0 — establish state before touching anything

Record: date/time (IST+UTC), `wp option get siteurl` and `home` (both must be exactly
`https://ambimat.com`), resolved WordPress root, active theme + child theme, Yoast version, W3TC
state, PHP/WP versions, and a hash of every file you may edit. If identity is ambiguous or points at
staging, STOP with `PRODUCTION_IDENTITY_GATE_FAILED_NO_MUTATION`.

Check for work in flight before writing anything: `ambimat-featured-image-remediation`,
`ambi-p3-ss-og.php` or quarantined variants, MU-plugins, `.htaccess`, recent `wp-content` mtimes.
**Do not reactivate quarantined code or disturb ongoing featured-image/OG migration work.** If your
fix collides with it, stop and report the collision.

### P1 — Heading hierarchy: 326 pages, one template (highest leverage, lowest risk)

326 of 437 pages report a skipped heading level; 1 page (`/pa-dss-payment-application-data-security-
standard/`) has multiple H1s; 7 pages share a duplicate H1.

A defect on 75% of pages with a uniform shape is a **template**, not 326 authoring mistakes. Before
editing anything: fetch 5–8 structurally different pages (home, a blog post, a `/design/*` page, a
`/tag/*` archive, a `/category/*` archive, a paginated blog index) and record the actual heading
sequence of each. Identify the exact jump (e.g. `h1 → h3`) and locate the emitting template part in
`launchseat` (or its child theme — **prefer the child theme; never edit the parent if a child exists**).

Fix the template so levels are sequential. Do not renumber headings inside post content to chase this.
Re-fetch the same sample and confirm the sequence. Then confirm no visual regression: heading levels
carry CSS, so verify the styling did not shift — if it did, adjust CSS rather than reverting to
skipped levels.

Duplicate/multiple H1s are content fixes on 8 named URLs — propose them, apply only with approval.

### P2 — Open Graph descriptions: 127 pages, one root cause

127 pages have incomplete Open Graph, the reported gap being `og:description`. Separately, 136 pages
have no meta description. These are almost certainly the same root cause: Yoast has no description to
render, so both the meta tag and the OG tag come out empty.

Confirm the causal link first — cross-reference the two lists. If they overlap heavily:
- Determine whether Yoast is configured with a template fallback for the affected post types /
  taxonomies (`wp option get wpseo_titles` and inspect the relevant `metadesc-*` keys).
- The correct fix is a **Yoast description template for the affected archive/post types**, not 127
  hand-written descriptions and not a plugin.
- Most of the affected URLs are `/tag/*` and `/category/*` archives. Decide deliberately whether those
  archives should carry generated descriptions at all — for many sites the honest answer is that the
  archives are low-value and the templates should target the content post types instead.

Apply to one post type first, verify the rendered `<head>` on 3 URLs, then extend.

### P3 — FAQPage schema: 6/437 (the actual AI-readiness lever, but content work)

Worth 20 of the 100 points and the single largest gap versus the sister sites. **This is content
authoring, not a technical fix. Do not auto-generate FAQ content, and do not fabricate questions or
answers.**

Deliver a scoped plan, not bulk output:
- Identify the cornerstone pages where FAQ genuinely helps — the SEO run names two clusters explicitly:
  `IoT identity / OEM` and `Identity Management`.
- For each, propose 3–5 real questions drawn from existing page content, and show the JSON-LD you
  would emit.
- Apply only to pages the owner approves, and only where the Q/A is genuinely on the page — FAQPage
  markup describing content that isn't visible is a structured-data violation.

Do not add FAQ schema to `/tag/*` or `/category/*` archives.

### P4 — Small, well-defined items

- **`content-security-policy` missing.** The only absent security header. CSP on an established
  WordPress site breaks things easily. Propose it `Content-Security-Policy-Report-Only` first,
  observe, and only then enforce. Do not enforce a CSP in this session.
- **Sitemap URL redirects:** `/about/` → `/about/company-overview/` appears in the sitemap as a
  redirecting URL. Point the sitemap and internal links at the final URL. Narrow, safe.
- **4 slow pages** (site avg 712 ms vs 231–313 ms across sister sites): `/for-developer/blogs/`,
  `/tag/automatic-fare-collection/`, `/tag/iotsecurity/`, +1. Investigate TTFB only. Do **not** change
  W3TC cache policy or front-page cache lifetime.
- **12 orphan pages:** `/ambi-space/`, `/ambi-sense/`, `/ambi-pay/`, `/ambi-secure/`, `/ambi-power/`,
  `/ambi-con/`, `/by-industry/`, `/by-technologies/`, `/f1tenth/`, `/terms-conditions/`,
  `/refund-cancellation-policy/`, `/event/ambimat-history/`. Several are legal pages that are
  legitimately reached only from the footer — verify against the rendered footer before treating any
  as a defect. Propose internal links only where genuinely useful.
- 17 duplicate-title groups and 13 duplicate-description groups — editorial. Report the groups with
  URLs; apply nothing without approval.

## Findings you must NOT act on — reject these explicitly in your report

- **The 30 "high-severity weak pages" advising "merge into one cornerstone and 301-redirect the
  thinner URL."** Fourteen are `/tag/<topic>/` versus the article that tag points at
  (`/tag/authentication/`, `/tag/automation/`, `/tag/automotive-security/`,
  `/tag/cold-chain-logistics/`, `/tag/fast-identity-online-fido/`, `/tag/general/`,
  `/tag/iot-security/`, …). Following that advice would dismantle the taxonomy. A tag archive and an
  article are not competing for the same query.
- **`Page is noindex` on `/category/general/` (the single high-severity audit finding).** That
  category and its 10 paginated children are all `noindex, follow` and all missing canonicals —
  a consistent pattern that reads as a deliberate Yoast archive setting. Verify it in
  `wpseo_titles` and, if intentional, close it as correct. Do not flip 10 pages' indexability to
  clear one audit line.
- **"492 broken outbound internal links."** 437 of them target the bare `https://ambimat.com` with no
  trailing slash, against an inventory keyed on `https://ambimat.com/`. It is a crawler normalisation
  artifact. The 10:00 run, which actually issues HTTP requests for internal links, found **zero**
  broken. Verify one directly and close all 492.
- **`suspicious-pattern` (460), `external-iframe` (23), `defacement-marker-in-content` (2),
  `japanese-spam` (2), `seo-spam` (1).** Respectively: `display:none`-class CSS matches; reCAPTCHA /
  Google Maps / WordPress `/embed/` cards; the phrases "hacked by" / "owned by" inside security
  articles the tool itself annotates "likely editorial"; the word "betting" on the Application
  Identifier list pages; the substring "xxx" on `/section-5-basic-organizations/`. None is a defect.
- **External 403s** (4 broken, 1 unverified). HEAD-only responses from third-party hosts the crawler
  never retried with GET. Never a defect on this host.

## Mutation rules

Smallest change, one at a time. For each: record before-state → apply → check exit status → purge only
the exact affected cache entry if genuinely required → verify the URL → re-test canaries → compare
against baseline → stop and roll back that batch on any regression.

Before the first write: targeted timestamped backup of every file and DB row you will change, plus a
rollback script you have validated as readable and complete. If it fails, STOP with
`ROLLBACK_GATE_FAILED_NO_MUTATION`. Prefer WP-CLI/WordPress APIs over direct SQL; if direct SQL looks
unavoidable, stop and ask.

Never: bulk redirects · redirect-to-homepage · editing post content to trigger reindexing · changing
publish dates · changing slugs · broad Yoast reindex, cache flush, permalink resave or rewrite flush ·
plugin/theme updates · deleting anything · disabling security controls · touching another host.

**Canaries, re-tested after every batch:** homepage · `/about/` · one blog post · one `/design/*` page
· `/robots.txt` · the sitemap index · one untouched `/tag/*` archive · one untouched paginated blog
index. Acceptance = every intended change passes, no new 4xx/5xx, no redirect loop, no accidental
`noindex`, no canonical-host drift, no sitemap corruption, no PHP warnings, no change to unrelated
featured/OG images.

## Stop conditions

Identity uncertain · evidence contradicts live behaviour · a fix would reach another hostname · backup
or rollback unvalidated · unexpected file/DB drift · a broad Yoast/cache/permalink operation would be
required · a plugin or theme update would be required · compromise suspected · any canary fails.
Do not improvise past one.

## Deliverables

A new timestamped report directory: `FINAL_REPORT.md`, `baseline.json`, `proposed_action_matrix.csv`
(one row per mutation: `ID | problem | evidence | root cause | exact change | files/rows affected |
risk | rollback | verification` — a row missing any column is not actionable), `changes_applied.csv`,
`verification_before.json`, `verification_after.json`, `verification_diff.md`, `rollback/README.md`,
a secrets-redacted command log, and a checksums manifest.

Do not claim Google has reindexed anything. For each item state whether it is corrected, expected, or
awaiting a recrawl.

**Finish with exactly one:**
`AMBIMAT_SEO_REMEDIATION_VERIFIED` · `AMBIMAT_SEO_REVIEW_COMPLETE_NO_MUTATION` ·
`AMBIMAT_SEO_REMEDIATION_ROLLED_BACK` · `AMBIMAT_SEO_REVIEW_BLOCKED_NO_MUTATION`

Never describe a partial or failed verification as successful.

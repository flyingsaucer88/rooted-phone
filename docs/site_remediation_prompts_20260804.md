# Per-site remediation prompts — evidence date 2026-08-04

Built from the phone's own 10:00 site-monitor run (`report_20260804_102806`) and 11:00 SEO run
(`report_20260804_115321`). `ambimat.com` is deliberately **not** covered here — it is handled separately.

Paste **Common Rules** + one site section into a session. One site per session; never two.

Priority: **P1 AmbiSecure** · P2 Orders · P3 the rest.

> **Correction (2026-08-04, post-verification).** An earlier draft ranked Orders P1 on a suspected TLS
> regression. `openssl s_client` against the live host disproved it: the certificate is unchanged since
> Jun 19 and is not weak. See the Orders section for the closed finding and the evidence.

---

## Common Rules — applies to every prompt below

You are working on a LIVE production website. Be conservative, evidence-led, reversible, transactional.

**Scope boundary.** The single hostname named in your site section is the only permitted mutation
target. Do not touch any other `*.ambimat.com` host, `ambimat.com` itself, DNS, CDN, the connected
phone, or its scripts/schedules/reports. Classify out-of-scope findings, never change them.

**Evidence first.** The findings in your site section are what the phone recorded at ~10:00–11:53 IST
on 2026-08-04. They are a starting point, not a verdict. Before any write, reproduce each one now with
a small, bounded, clearly-identified request budget. Anything you cannot reproduce is closed as
`NOT_REPRODUCIBLE`, not "fixed".

**Do not treat a monitor warning as a defect.** In particular:
- `suspicious-pattern` = a match on `display:none` / `visibility:hidden` / `opacity:0`. Ordinary theme
  CSS. Assume false positive unless you find actual injected content.
- `defacement-marker-in-content` = the literal phrase "hacked by" / "owned by" in page text. On security
  blogs this is editorial prose. The tool itself annotates these "likely editorial — verify manually".
  Read the page before acting.
- `japanese-spam` / `seo-spam` = substring hits (`betting`, `xxx`). Read the sentence they appear in.
- `external-iframe` = WordPress `/embed/` cards, reCAPTCHA, Google Maps. Expected.
- A 403 on an **external** link came from a HEAD request the crawler never retried with GET. It is not
  a broken link and never a defect on your host.
- `noindex` on carts, checkouts, accounts, tag/taxonomy archives and parameterised URLs is usually
  correct. Do not remove it to reduce a count.

**Gates, in order.**
1. Record date/time (IST+UTC), host, resolved web root or repo path, git branch/HEAD, and the
   versions/hashes of anything you might change. Keep raw evidence separate from interpretation.
2. Prove production identity for the exact hostname in your section. If it is ambiguous or points at
   staging, STOP with `PRODUCTION_IDENTITY_GATE_FAILED_NO_MUTATION`.
3. Read-only baseline: status, redirect chain, canonical, robots meta/header, robots.txt, sitemap
   membership, title/H1, cache headers, TLS chain, for every candidate plus canaries.
4. Produce a proposed action matrix — one row per mutation: `ID | problem | evidence | root cause |
   exact change | files/rows affected | risk | rollback | verification`. A row without all nine is not
   actionable. **"No change required" is a valid, complete result.**
5. Targeted timestamped backup of every file/row that will change, plus a rollback script you have
   validated as readable and complete. If it fails, STOP with `ROLLBACK_GATE_FAILED_NO_MUTATION`.

**Mutation rules.** Smallest change, one at a time. Record before-state → apply → check exit status →
verify the URL → recheck canaries → compare against baseline → stop on any regression and roll that
batch back. Never: bulk redirects, redirect-to-homepage, editing content to trigger reindexing,
changing publish dates, changing slugs without proven need, broad Yoast/cache/permalink/rewrite
operations, plugin or theme updates, directory listings, disabling security controls, deleting
anything, or touching another host.

**Canaries** (re-test after every batch): homepage, one normal page, one deep content page,
`/robots.txt`, the sitemap index, and one URL you did not touch. Acceptance = every intended change
passes, no new 4xx/5xx, no redirect loop, no accidental `noindex`, no canonical-host drift, no sitemap
corruption, no PHP warnings.

**Stop conditions.** Identity uncertain · evidence conflicts with live behaviour · a fix would reach
another hostname · the replacement URL is uncertain · backup/rollback unvalidated · unexpected drift ·
a broad operation would be required · compromise suspected · a canary fails. Do not improvise past one.

**Artifacts.** A new timestamped report directory containing `FINAL_REPORT.md`, `baseline.json`,
`proposed_action_matrix.csv`, `changes_applied.csv`, `verification_before.json`,
`verification_after.json`, `verification_diff.md`, `rollback/README.md`, a secrets-redacted command
log, and a checksums manifest. Preserve unrelated work; commit only task-owned changes.

**Final integrity statement** — exactly one:
`SITE_REVIEW_COMPLETE_NO_MUTATION` · `SITE_TARGETED_REMEDIATION_VERIFIED` ·
`SITE_TARGETED_REMEDIATION_ROLLED_BACK` · `SITE_REVIEW_BLOCKED_NO_MUTATION`

Never describe a partial or failed verification as successful.

---

## P2 — `orders.ambimat.com` (WooCommerce)

> **SUPERSEDED by `orders_seo_remediation_prompt_20260811.md`.** That file is built on current
> evidence and a healthy run; this section was written from the degraded 08-04 run. Use it instead.
> Kept here for the audit trail.

Apply the Common Rules. Target host: **`https://orders.ambimat.com`** only.

### CLOSED — the 2026-08-04 TLS failure was not a server problem. Do not re-investigate.

The 10:00 run on 08-04 reported
`[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: EE certificate key too weak`, after three
clean days. `openssl s_client` against the live host the same afternoon disproved a server-side cause:

| Evidence | Value |
| --- | --- |
| Leaf validity | `NotBefore Jun 19 22:18:49 2026` → `NotAfter Sep 17 22:18:48 2026` |
| Phone's own reading, 08-01 / 08-02 / 08-03 | `Sep 17 22:18:48 2026 GMT` — byte-identical |
| Leaf key | ECDSA **P-256** (~128-bit security), `ecdsa-with-SHA384` |
| Chain | LE `YE2` (P-384) → ISRG `Root YE` (P-384) → `ISRG Root X2` → `ISRG Root X1` |
| Result | `Verification: OK`, `Verify return code: 0` |

The certificate has been served unchanged since 19 June — it was never reissued around 08-03/04. P-256
clears OpenSSL SECLEVEL 2 **and** 3; "EE certificate key too weak" is the signature of a 1024-bit RSA
leaf, which this is not. The phone was therefore not completing a handshake with this server.

Consistent with a broken network path, not a site defect — all from that same run: 14 `fetch-error`
warnings (`Connection reset by peer`, `Max retries exceeded`); the Orders link-check *also* failed SSL
against `ambimat.com`, whose own certificate verified fine in the same report; coverage fell 36 → 22
pages; the 11:00 SEO job logged `network unavailable at start; deferred`; and the 11:53 SEO run reached
the host normally at 18 pages. Most likely a captive portal or carrier middlebox presenting its own
weak leaf during the outage window.

**Consequences for this prompt:**
- Treat the 08-04 10:00 Orders data as **unreliable** — 22/36 pages, 20 link checks unverified. Use the
  08-03 run as the last trustworthy snapshot, and re-baseline live before proposing anything.
- Certificate expiry is 2026-09-17 (44 days as of 08-04). The monitor warns at 21 days. Nothing due.
- Do not attempt any TLS, certificate or hosting change. If a future run reproduces this **while
  `openssl s_client` from a different network verifies OK**, it is a phone-network finding, not a site
  finding, and belongs to the monitoring workstream.

### Actual findings

- **Missing security headers, all four:** `x-frame-options`, `x-content-type-options`,
  `referrer-policy`, `strict-transport-security`. This is the only site in the estate missing any, and
  it is the site that takes payments — so this is now the highest-value item here. Propose the four as
  one narrow, reversible change. HSTS is safe to include: the certificate is confirmed valid and the
  host already serves HTTPS. Start with a short `max-age`, no `preload`, no `includeSubDomains`.
- **`noindex` on 7 `?add-to-cart=` URLs** and on `/cart/`, `/checkout/`, `/my-account/`,
  `/share-cart/`. **All correct. Leave them.** Do not "fix" the SEO audit's 4 high-severity
  "Page is noindex" findings — they are transactional endpoints.
- **3 pages missing a canonical:** `/`, `/product-category/fido/`, `/product-category/pcb-board/`.
  The homepage having no canonical is worth a look; the two category archives may be intentional.
  Verify each against the live head before proposing anything.
- **Duplicate titles:** "shipping policy – ambimat electronics" and "cart – ambimat electronics"
  each on 2 pages. Editorial; propose, do not apply unilaterally.
- **21 pages missing a meta description.**
- **Orphans:** `/my-account/`, `/share-cart/`, `/shipping-policy/`. Expected for the first two.
- **Thin content:** `/cart/` and `/checkout/` at 104 words, quality 45/100. **This is normal for
  transactional pages. Do not expand them. Do not merge cart into checkout** — the SEO tool's
  "duplicate intent, 301-redirect the thinner URL" recommendation would break the store. Explicitly
  reject it in your report.
- Site AI-readiness 31.2 and avg response 760 ms — the weakest in the estate. Record; do not act.

---

## P1 — `ambisecure.ambimat.com`

Apply the Common Rules. Target host: **`https://ambisecure.ambimat.com`** only.

State is good: 285–314 pages, all HTTP 200, 0 broken pages, 0 broken internal links, all security
headers present, cert 39 days, AI-readiness 83.0, schema coverage 1.0, 182 FAQ pages, 0 orphans,
audit 0 high / 0 medium. **A "no change required" outcome is likely and acceptable.**

**Resolved since 2026-07-31 — confirm and close:** 4 `title-drift` warnings present on 07-31 are gone
on 08-04. Verify the titles are now stable and record the closure. Do not reopen.

**The one question worth real work — 29 `noindex` tag archives.**
All of `/tags/*` (`desfire`, `passkeys`, `pki`, `smart-cards`, `webauthn`, `transit`, `fido`,
`javacard`, `cyber-resilience-act`, `secure-element`, `iot-security`, `ambisec`, …) carry `noindex`,
while the SEO run separately reports **62 "broken outbound" internal links from `/blog/` to those same
`/tags/*` URLs**. The two facts are related: the blog index links to tag pages that are excluded.
Determine which is intended:
- If tag archives are deliberately out of the index → the `noindex` is correct and the 62 "broken
  outbound" records are a crawler artifact (excluded URLs missing from its page inventory). Document
  and close both. **This is the most likely answer.**
- If they are meant to be indexable → that is a content-strategy decision, not a technical defect.
  Escalate; do not flip 29 pages' indexability on your own judgement.
Either way, confirm the links themselves resolve (200) when fetched directly.

**Do not act on these:**
- 6 `defacement-marker-in-content` warnings on `/blog/archive/cyber-attacks-in-india-part-1/`,
  `/blog/javacard-applet-development-enterprise-identity/`,
  `/blog/pki-credential-issuance-workforce-government/`, `/blog/why-software-only-device-trust-fails/`,
  `/brochures/javacard/`, `/case-studies/passwordless-workforce/`. These are the phrases "hacked by"
  and "owned by" in 543–3863-word security articles. Read one to confirm the pattern, then close all
  six as editorial.
- 1 `japanese-spam` hit: the word "betting" in `/blog/why-sams-matter-in-closed-loop-transit/`.
- 2 external 403s (`cloudflare.com`, `iso.org`) and 2 unverified (Facebook, LinkedIn) — HEAD-only
  third-party responses. Not defects.

**Minor, optional:** `/references/webauthn-cose/` responded in 2631 ms (site avg 335 ms); duplicate H1
across 2 pages starting `/brochures/onepass/`. Propose only if trivially reversible.

---

## P3 — `esim.ambimat.com`

Apply the Common Rules. Target host: **`https://esim.ambimat.com`** only.

**The healthiest site in the estate. Expect `SITE_REVIEW_COMPLETE_NO_MUTATION`.**
33 pages all 200, 0 broken pages/internal links, all security headers present, cert 63 days,
AI-readiness **97.1**, schema coverage 1.0, FAQPage on all 33, 0 orphans, audit 0/0/0, 0 weak pages.
Nothing changed vs 2026-07-31.

Your job is to confirm that and close the noise, not to find work:
- 33 `external-iframe` + 33 `suspicious-pattern` warnings — one per page. Systematic, template-driven,
  expected.
- 1 `defacement-marker-in-content`: "owned by" in a 1334-word article at
  `/blogs/euicc-applet-development.html`. Editorial.
- 4 external 403s: `business-standard.com` (×2), `cisa.gov`, and one more — all HEAD-only third-party
  refusals from citation links in `/blogs/sms-otp-fraud-india-secure-authentication.html` and
  `/blogs/global-shift-away-from-sms-otp.html`. Not defects.
- The SEO run lists 33 "broken outbound" internal links — one per page, i.e. every page's link to the
  site root. Same trailing-slash inventory artifact seen estate-wide. Verify one directly and close.

If a live check contradicts any of the above, stop and report rather than remediating.

---

## P3 — `ambipower.ambimat.com`

Apply the Common Rules. Target host: **`https://ambipower.ambimat.com`** only.

25–27 pages all 200, 0 broken pages/internal/external links, all security headers present, cert 39
days, AI-readiness 85.9, schema coverage 1.0, 0 orphans, audit 0 high / 0 medium / 1 low. Unchanged
since 2026-07-31.

Only two things are even candidates:
1. **`/privacy/` has incomplete Open Graph tags.** The only audit finding on the site. Verify live,
   then propose the minimal missing-property fix with a rollback. Low risk, low value — a "defer"
   decision is defensible.
2. **`/resources/downloads/` carries `noindex`.** Determine whether that is deliberate (gated or
   thin-index resource listing) before touching it. Most likely correct as-is.

Not defects: 1 `suspicious-pattern` warning; 1 unverified external link (Facebook); 26 "broken
outbound" internal records (the estate-wide root-link inventory artifact).

---

## P3 — `ambiautomation.ambimat.com`

Apply the Common Rules. Target host: **`https://ambiautomation.ambimat.com`** only.

22–28 pages all 200, 0 broken pages/internal/external links, all security headers present, cert 45
days, schema coverage 1.0, 0 orphans, 0 broken outbound, audit 0/0/0. Unchanged since 2026-07-31.
AI-readiness 57.2 — the second-lowest in the estate, worth noting but not a defect.

**The one real finding: seven URLs share one title.**
`/contact` plus `/contact?purpose=deployment|engineering|datasheet|savings|integration|rfp` all render
"contact — request a demo or savings model | ambiautomation", with a matching duplicate description.

These are query-parameter variants of one page, not seven pages. The correct fix is almost certainly a
**self-referencing canonical on `/contact` for every variant** — not seven distinct titles, and not
`noindex`. Before proposing:
- Check what canonical each variant currently emits.
- Check whether the `?purpose=` parameter changes rendered content (e.g. preselects a form field). If
  it does, that is still one canonical page with UI state.
- Confirm none of the variants appear in the sitemap.
If the canonical is already correct, this is a reporting artifact — close it with evidence.

Not a defect: 1 `defacement-marker-in-content` ("owned by" in a 1174-word `/about` page); 1
`suspicious-pattern`; 2 unverified external links.

---

## P3 — `roboracer.ambimat.com`

Apply the Common Rules. Target host: **`https://roboracer.ambimat.com`** only.

**The cleanest report in the estate: 7 pages all 200, zero warnings of any type, zero alerts, all
security headers present, cert 65 days, 0 orphans, audit 0/0/0.** Unchanged since 2026-07-31.

Nothing here is a technical defect. Two editorial observations only:
1. **`/` vs `/autonomous-racing-robotics-kit.html` flagged as duplicate intent (high).** With only 7
   pages, this is plausibly real overlap. But the tool's suggested action — "merge and 301-redirect the
   thinner URL" — would redirect the homepage or the primary product page. **Do not apply it.**
   Report it as an editorial/IA decision for the owner, with the two pages' titles, H1s and word
   counts side by side so they can judge.
2. `/getting-started.html` has no FAQPage schema (medium). Adding 3–5 genuine Q/A entries is a content
   task, not a technical remediation. Propose; do not author FAQ content unilaterally.
3. One external 403: `https://robo-racer.slack.com/signup`, HEAD-only from the homepage. Not a defect.
   Optionally confirm with a single GET that the invite link still works — that is a link-rot check for
   the owner, not a site fix.

Expected outcome: `SITE_REVIEW_COMPLETE_NO_MUTATION`.

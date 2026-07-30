# Baseline — 2026-07-30 (mid-flight snapshot)

**Not a clean daily.** The two cron reports here were taken *before* two same-day deploys, so
they do not represent the estate's end-of-day state. Use them for the site-monitor picture and
for the pre-deploy SEO baseline only. The `verification/` directory holds the post-deploy
measurements, which are the accurate end-of-day numbers.

Tomorrow's 10:00/11:00 run will be the first clean snapshot of the post-deploy estate.

| Job | Cron | Finished | Coverage | Relative to deploys |
|---|---|---|---|---|
| Site monitor | 10:00 IST | 10:24 | 7/7 sites, 924 pages | **pre**-deploy |
| SEO tracker | 11:00 IST | 11:22 | 7/7 domains, 856 pages | **pre**-deploy |

Both markers read `2026-07-30`. Device at capture: uptime 2d 23h, 147 MB free RAM, battery 90%
charging, both daemons up, watchdog logging `before due time` correctly ahead of the 11:00 job.

## Files

| Path | Contents |
|---|---|
| `site_monitor_20260730.{json,md,html}` | merged 7-site crawl (phone `report_20260730_102443.*`) |
| `seo_tracker_20260730.{json,md,html}` | 7-domain SEO run (phone `report_20260730_112204.*`) |
| `per_site/*.json` | seven pre-merge per-site crawler reports |
| `summary_history.json` | SEO tracker rolling run history |
| `verification/*.json` | on-demand single-domain runs measuring the day's deploys |

Committed with `git add -f`; `.gitignore` excludes raw report dumps.

## Site monitor (pre-deploy, 10:24)

```
sites_total 7   sites_unreachable 0   sites_timed_out 0   sites_with_alerts 0
pages_crawled 924   broken_pages 0   broken_links 22   unverified_links 9
suspicious_warnings 694   partial false
```

Second consecutive day at **zero alerts across all seven sites**. The 13 title-drift warnings
from 07-29 aged out as expected.

| Site | Pages | Alerts | TLS days | Security headers |
|---|---|---|---|---|
| ambimat.com | 461 | 0 | **36** | missing CSP, XFO, XCTO |
| ambisecure.ambimat.com | 314 | 0 | 44 | all present |
| ambiautomation.ambimat.com | 28 | 0 | 50 | all present |
| esim.ambimat.com | 33 | 0 | 68 | all present |
| ambipower.ambimat.com | 27 | 0 | 44 | all present |
| orders.ambimat.com | 54 | 0 | 49 | **regressed — see below** |
| roboracer.ambimat.com | 7 | 0 | 70 | all present |

### orders.ambimat.com regressed

The 07-29 fixes did not stick. Verified live three times, no caching involved:

| | 07-29 | 07-30 |
|---|---|---|
| Security headers | 5 of 5 | **1 of 5** |
| Missing H1s | 0 | **4** (incl. homepage) |

`strict-transport-security`, `x-frame-options`, `x-content-type-options` and `referrer-policy`
are all gone again; only `content-security-policy: upgrade-insecure-requests` remains. Server is
LiteSpeed. Root cause unresolved — most likely a plugin or LiteSpeed/`.htaccess` config reverted
by a deploy. **This is the one open item on the estate with real risk attached**: a storefront
handling cart, checkout and accounts, with no HSTS. A header fix that silently rolls back is
worse than one never applied, because the monitor showed green in between.

`orders` and `ambimat.com` are both owner-flagged as pending; neither was worked on this day.

## The day's deploys — measured, not predicted

Two domains were re-worked after both cron jobs ran. Measured with on-demand single-domain
tracker runs (isolated output dirs; the tracker's own baseline and history were not touched).

### esim.ambimat.com — 64.4 → **97.1**

| | pre | post |
|---|---|---|
| Average AI readiness | 64.4 | **97.1** |
| Pages ≥70 | 5 of 33 | **33 of 33** |
| Weakest page | 49 | **95** (homepage 100) |
| Weak findings (high/med/low) | 0 / 0 / 31 | **0 / 0 / 0** |

Three deploys, in order: a prose/structure pass (64.4 → 64.4 on three pages — see below), a
scorer-driven pass (→ 97.0), and a closeout fixing structured-data hygiene (→ 97.1).

### ambisecure.ambimat.com — 41.3 → **75.5**

| | pre | post |
|---|---|---|
| Average AI readiness | 41.3 | **75.5** |
| Pages ≥70 | 28 of 314 | **164 of 285** |
| Pages under 40 | 187 | **0** |
| Weakest page | 20 | **54** |
| HIGH weak findings | 2 | **0** |
| Orphans / under-linked | 0 / 24 | 0 / **3** |
| `Organization` nodes | 1 of 314 | **285 of 285** |

Sitemap 314 → 285: 29 tag archives set `noindex,follow` and removed. Roughly **+2.2 of the
average lift is those 20-scoring pages leaving the denominator**, not pages improving — the
remaining ~+29 is real page improvement. The implementer split this honestly in their own report
and it is recorded here for the same reason.

## What was learned about the scorer

`ai_readiness.py` is a six-component composite, caps summing to 100: `structured_data` 25,
`faq` 20, `headings` 15, `content_depth` 15, `entity_coverage` 15, `answer_shape` 10.

**`content_depth` is a step function on word count** — 0 / 6 / 10 / 15 at the 400 / 800 / 1500
boundaries. This is why eSIM's first pass added several hundred words to `/resources.html`,
`/telecom-integration.html` and `/architecture.html` for a measured gain of exactly **zero**:
all three were already inside their band and none reached 1500. Prose is capped at 15 of 100.
Schema is worth 60.

**`entity_coverage` is `len(Organization.knowsAbout) + len(page-level JSON-LD keywords)`** —
a structured-data field, not prose. Thresholds 4 / 10 / 20 entries → 6 / 10 / 15 points. It was
reporting 0 across all seven domains because those fields did not exist anywhere. This was
initially and wrongly diagnosed here as a broken extractor; it works correctly.

**`duplicate_intent` is `jaccard(tokens(title + " " + h1)) >= 0.80`** — title and H1 only, no
stopword removal. Body text is never examined, so body-level differentiation cannot clear it.
AmbiSecure's two HIGH findings were at 0.875 and 0.833, differing by a single token
(`gmail` vs `facebook`); retitling cleared both to a worst pair of 0.667.

**`answer_shape` and `headings` need a question-shaped H2**, matching
`^(what|how|why|when|where|who|which|can|does|do|is|are|should)\b`. Only `h2_list` is read —
H3s are invisible to it. One heading rename is worth +7 (+4 headings, +3 answer_shape).

**The H1/title divergence check** (`jaccard(h1, title) < 0.2`) lives in `weak_pages.py`, produces
a `medium` finding, and has **no effect on `ai_readiness`**. It is a lint, not a ranking signal.

### A prediction recorded here because it was wrong

Ahead of measuring AmbiSecure, this repo's analysis predicted 70–72 on the theory that leaving
"Frequently asked questions" unrenamed on 46 pages would cost `answer_shape` and `headings`
points. Measured result was **75.5**. Those pages already carried other question-shaped H2s
(the four index pages have 2, 1, 1 and 4). The implementer's own estimate of 72.2 was the better
one, and conservative only in the two columns they had explicitly flagged as modelled.

## Known false positives — verified live, do not treat as findings

- **`broken_outbound` over-reports.** It flags internal links whose target is outside the crawled
  HTML page set, so PDFs, `sitemap.xml`, ZIPs, `noindex` pages and trailing-slash redirects appear
  broken while returning 200. Bug is in the phone-resident SEO tracker, not this repo.
- **External 403/401s are bot blocks**: iso.org, cisa.gov, gsma.com, eftlab (this one is a *real*
  404), addtoany (×16 on orders), robo-racer.slack.com.
- **`suspicious-pattern`** remains dominated by generic `display:none` / `opacity:0` template CSS.
- **A CDN caveat learned today**: for several minutes after a deploy the edge served mixed-vintage
  pages. An early spot-check of `/videos/setup-ambisecure-card-gmail/` showed no FAQPage and no
  `knowsAbout`; a second fetch showed both. Re-fetch before concluding a deploy missed a page.

## Compliance finding worth carrying forward

On AmbiSecure, **46 pages carried FAQPage schema whose Q&A appeared nowhere in the rendered
page**. That is a Google FAQPage policy violation, not merely a scoring gap, and can cost rich
results or draw a manual action. Fixed by rendering the existing schema answers visibly — no new
claims authored. Worth a standing check on the other domains.

## SEO metrics (pre-deploy cron run, 11:22)

```
total_pages 856   avg_ai_readiness 47.2   total_orphans 15
weak_pages_high 43   audit_high 5   audit_medium 28
```

| Domain | Pages | AI readiness (cron) | Post-deploy |
|---|---|---|---|
| Ambimat | 437 | 41.1 | unchanged — pending |
| AmbiSecure | 314 | 41.3 | **75.5** (285 pages) |
| eSIM | 33 | 63.9 | **97.1** |
| AmbiPower | 25 | 57.0 | not re-run |
| AmbiAutomation | 22 | 57.2 | not re-run |
| Orders | 18 | 14.4 | unchanged — pending |
| RoboRacer | 7 | 55.7 | not re-run |

Estate average post-deploy is **roughly 60**, up from 47.2 — an estimate derived from the two
re-measured domains, not a measured figure. Tomorrow's full run supersedes it.

## Largest remaining headroom

- **ambimat.com** — 437 pages, **0 above 70**, 6 FAQPages, sparse `Organization`. Same three
  levers that moved AmbiSecure, over the largest surface on the estate. Owner-flagged pending.
- **AmbiSecure's 170 pages with no FAQPage** — worth ~+11.9 domain average, but ~850 genuine
  questions. Deliberately not attempted; recommended selectively (`/references/*`,
  `/resources/tools/*`) rather than in bulk.
- **~145 AmbiSecure pages capped at `structured_data` 17/25** because they are correctly typed
  `Product` / `Service` / `CollectionPage`. This is a **permanent ceiling, not debt** — the scorer
  only rewards Organization / BreadcrumbList / Article / ≥3-distinct-types. Do not "fix" it by
  mistyping product pages as Articles.

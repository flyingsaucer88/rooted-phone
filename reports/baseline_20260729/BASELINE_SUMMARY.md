# Baseline — 2026-07-29

**Current reference baseline.** Supersedes `reports/baseline_20260728/`, which is retained
because it is the last snapshot taken *before* the crawler fix in c8e0af2 and therefore the
only record of what the false positives looked like.

This is the first run where the site monitor produced **zero alerts across all seven sites**.

| Job | Cron | Finished | Coverage |
|---|---|---|---|
| Site monitor | 10:00 IST | 10:26 | 7/7 sites, 923 pages |
| SEO tracker | 11:00 IST | 11:21 | 7/7 domains, 861 pages |

Both success markers read `2026-07-29`. No missed runs, no watchdog catch-up.
Device at capture: uptime 2d 5h, 133 MB free RAM, 20 GB free storage, battery 83% charging.

## Files

| File | Contents |
|---|---|
| `site_monitor_20260729.{json,md,html}` | merged 7-site crawl (phone `report_20260729_102606.*`) |
| `seo_tracker_20260729.{json,md,html}` | 7-domain SEO run (phone `report_20260729_112135.*`) |
| `per_site/*.json` | the seven per-site crawler reports, pre-merge |
| `summary_history.json` | SEO tracker's rolling run history |

Committed with `git add -f`; `.gitignore` excludes raw report dumps. Same deliberate exception
as the 07-28 baseline — daily runs still stay out of git.

## The crawler fix landed

First run using the fixed `urljoin` base (c8e0af2):

| | 07-28 | 07-29 |
|---|---|---|
| `sites_with_alerts` | 1 | **0** |
| `broken_pages` | 22 | **0** |
| `broken_links` | 29 | 21 |
| `offsite-redirect` warnings | n/a | 1 |

The single `offsite-redirect` warning correctly identifies
`ambimat.com/design/design-services/java-card-applet/` → `ambisecure.ambimat.com/services/javacard-development/`,
which is the redirect that caused the 22 phantom 404s in the previous baseline. All 22 are gone
and none returned as real findings — confirming they were entirely an artifact of the bug.

## Site monitor totals

```
sites_total 7   sites_reported 7   sites_unreachable 0   sites_timed_out 0
pages_crawled 923   broken_pages 0   broken_links 21   unverified_links 6
suspicious_warnings 702   partial false
```

## Per-site state

| Site | Pages | Alerts | TLS days | Security headers |
|---|---|---|---|---|
| ambimat.com | 461 | 0 | **37** | missing CSP, XFO, XCTO |
| ambisecure.ambimat.com | 317 | 0 | 45 | all present |
| ambiautomation.ambimat.com | 28 | 0 | 51 | all present |
| esim.ambimat.com | 33 | 0 | 69 | all present |
| ambipower.ambimat.com | 27 | 0 | 45 | all present |
| orders.ambimat.com | 54 | 0 | 50 | all present |
| roboracer.ambimat.com | 3 | 0 | 71 | all present |

ambimat.com's certificate expires 2026-09-05 — the shortest window on the estate.

## Remediation confirmed live this day

Fixes made after the 07-28 review, verified present in this run:

- **orders** — all five security headers now present, up from one; **HSTS added** to the
  storefront; 9 missing H1s → 0; author slug no longer derived from a work email address
- **ambipower** — `x-frame-options` added; `/presentation/deck/` title restored; the dead
  `com.ambimat.meterapp` Play Store link removed from `/products/udr-app/`
- **ambisecure** — 8 blog titles rewritten to differentiate the multi-part series; last orphan
  linked; heading issues 89 → 0; HIGH weak pages 14 → 6
- **ambiautomation** — duplicate titles resolved; FAQ schema added (19 pages)
- **esim** — `/sim-based-authentication.html` retitled away from the homepage; HIGH 1 → 0

**ambimat.com and roboracer.ambimat.com were not worked on** — both unchanged from 07-28.

## SEO metrics

```
total_pages 861   avg_ai_readiness 42.4   total_orphans 21
weak_pages_high 51   audit_high 4   audit_medium 31
```

| Domain | Pages | AI readiness | Quality | Schema cov | Orphans | Weak HIGH |
|---|---|---|---|---|---|---|
| Ambimat | 437 | 41.1 → unchanged | 92.4 | 1.00 | 12 | 30 |
| AmbiSecure | 317 | 37.1 → **39.6** | 97.9 | 1.00 | **0** | 14 → **6** |
| eSIM | 33 | 59.9 → **63.9** | 100.0 | 1.00 | 0 | 1 → **0** |
| AmbiPower | 25 | 50.6 → **52.7** | 100.0 | 1.00 | 0 | 0 |
| AmbiAutomation | 22 | 52.1 → **55.8** | 100.0 | 1.00 | 0 | 0 |
| Orders | 24 | 12.5 → **16.1** | 64.8 | 0.54 | 9 | 24 → **15** |
| RoboRacer | 3 | 27.3 → unchanged | 88.3 | 1.00 | 0 | 0 |

## New findings first seen in this run

**orders.ambimat.com — hidden spam backlink on `/contact/`.** An empty, invisible anchor sits
beside the Google Maps iframe:
`<a href="https://yt2.org/es/youtube-to-mp3-ALeKk00qEW0sxByTDSpzaRvl8WxdMAeMytQ..."></a>`.
Verified present in the live HTML. This is the signature of a free "embed Google Map" generator
shipping a piggybacked SEO backlink — not a compromise, but a real invisible outbound link to a
YouTube-ripping domain from a commerce contact page. Note the crawler's `hidden-link` heuristic
did **not** fire, because the anchor carries no hiding CSS — it is empty rather than styled
hidden. Worth extending the heuristic to cover zero-content anchors.

**orders.ambimat.com — 30 crawlable `?add-to-cart=` URLs.** `robots.txt` is bare (`Allow: /`),
so every add-to-cart permutation is walked and indexed: `/?add-to-cart=15`,
`/cart/?add-to-cart=2210`, `/product/roboracer-core-kit/?add-to-cart=2040`, and 27 more. These
are state-changing GET URLs — crawling them mutates a session cart — and they are large-scale
duplicate content. Not in the sitemap; discovered through links.

**ambimat.com — genuinely dead external link.** `www.eftlab.co.uk/index.php/site-map/knowledge-base/145-emv-nfc-tags`
returns 404 to a browser UA, linked from `/how-to-parse-tlvs-in-javascript/`. This is a real
dead link, unlike the 403s below.

## Known false positives in this snapshot

Verified live on this date — do not treat as findings:

- **`broken_outbound` in the SEO report** still over-reports: it flags internal links whose
  target is outside the crawled HTML page set, so PDFs, `sitemap.xml`, ZIPs, `noindex` pages and
  trailing-slash redirects appear broken while returning 200. Bug is in the phone-resident SEO
  tracker (`~/seo_tracker/phone/`), not this repo.
- **External 403/401s are bot blocks**, not breakage: iso.org, cisa.gov, gsma.com,
  addtoany (×16 on orders), robo-racer.slack.com.
- **`title-drift` warnings (13 total)** across ambisecure (8), ambiautomation (4) and esim (1)
  are the intentional retitling listed above, not unexplained drift.
- **ambiautomation `/about` "owned by"** defacement-marker and suspicious-pattern warnings: the
  phrase is inside the FAQPage JSON-LD added that day — "all owned by one engineering
  organisation". Correct as written.
- **ambimat.com `suspicious-pattern` (460)** remains dominated by generic
  `display:none` / `opacity:0` CSS.

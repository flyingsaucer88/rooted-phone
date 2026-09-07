# Live site probe — 2026-09-07 ~15:00 IST (from the Mac; read-only, GET/HEAD only)

| Host | HTTP | Redirects | Final URL | robots.txt | sitemap.xml |
|---|---|---|---|---|---|
| ambimat.com | 200 | 0 | https://ambimat.com/ | 200 | 200 (8 urls) |
| ambisecure.ambimat.com | 200 | 0 | https://ambisecure.ambimat.com/ | 200 | 200 (308 urls) |
| ambipower.ambimat.com | 200 | 0 | https://ambipower.ambimat.com/ | 200 | 200 (26 urls) |
| ambiautomation.ambimat.com | 200 | 0 | https://ambiautomation.ambimat.com/ | 200 | 200 (22 urls) |
| v2x.ambimat.com | 200 | 0 | https://v2x.ambimat.com/ | 200 | 200 (62 urls) |
| ai.ambimat.com | 200 | 0 | https://ai.ambimat.com/ | 200 | 200 (7 urls) |
| roboracer.ambimat.com | 200 | 0 | https://roboracer.ambimat.com/ | 200 | 200 (8 urls) |
| orders.ambimat.com | 200 | 0 | https://orders.ambimat.com/ | 200 | 404 (1 urls) |
| esim.ambimat.com | 200 | 0 | https://esim.ambimat.com/ | 200 | 200 (33 urls) |

`ambimat.com/sitemap.xml` is a sitemap **index** (8 child sitemaps), which is why the
crawler discovers ~340 pages rather than 8.

## Stale phone state vs live reality

### A. Local entries that no longer exist live — OBSERVED
* `https://ambimat.com/products/` → **HTTP 404**, still linked from live pages and still
  crawled. Independently re-verified live at 2026-09-07 15:1x IST. This is a real site
  finding for the owner; the monitor is reporting it correctly and the phone is not at
  fault. **Not repaired here — modifying production websites is out of scope.**

### B. Live sites the phone did not know about — CHANGED
* `v2x.ambimat.com` (62 sitemap URLs) and `ai.ambimat.com` (7 sitemap URLs) were live and
  monitored by neither job. Both added to both inventories and now crawled.

### C. Stale SEO assumptions — CHANGED
* The SEO tracker's domain list carried no keyword clusters for V2X or AI Tools because
  the domains were absent entirely. Seed keywords and primary clusters were authored from
  the live pages (V2X: C-V2X/OBU/RSU/V2V/V2I; AI Tools: PDF/Markdown conversion, prompt
  library) rather than guessed.

### D. Stale cached page inventories — OBSERVED, self-correcting
* Per-site page inventories under `~/site_monitor_reports/per_site/<slug>/` are rewritten
  in full on every run; they were 2026-09-05 stale during the offline day and were
  refreshed by the 12:56 catch-up. No manual intervention needed. The `per_site/`
  directory retains stale slug folders only for sites still configured, so no orphans.

### E. Stale sitemap information — OBSERVED
* `orders.ambimat.com/sitemap.xml` returns **404**. The crawler falls back to link
  discovery and still reached 49 pages, so coverage is not lost, but Orders has no
  sitemap for search engines. Pre-existing, unrelated to the outage. Owner-side site
  issue, not a phone defect.
* `ai.ambimat.com` serves a valid sitemap but its homepage `<title>` leaks an HTML
  comment from the prerender template ("…and description below are the dev-server
  defaults…"). Reported for the owner; **not fixed** — production sites were not modified.

### F. Stale success/failure state — OBSERVED / CHANGED
* Daily job markers were **not** stale: all three read `2026-09-07` and are backed by real
  artefacts.
* Measurement-queue state **was** misleading: three runs carried an authentication verdict,
  two of them wrongly. Corrected — see `authentication_error_root_cause.md`.

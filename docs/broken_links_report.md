# Broken Links Report — Ambimat sites

**Generated:** 2026-07-01 18:01 IST
**Source:** `site_monitor` crawler reports (no new crawl was run — existing reports from 2026-07-01 were sufficient).

## Source report files inspected

| Report | File | Coverage |
|---|---|---|
| Bounded crawl (latest) | `reports/site_monitor/report_20260701_173508.json` (= `report_latest.json`) | 10 pages/site, **internal links only** (`--no-external-links`) |
| Recovery crawl | `reports/site_monitor_recovery/report_20260701_172216.json` | 20 pages/site, **internal + external links** (only run that checked external links) |
| Smoke test | `reports/site_monitor/report_20260701_173152.json` | 3 pages/site, internal only (subset — no unique links) |
| Recovery narrative | `docs/site_monitor_recovery_report.md` | context on external-link false positives |
| Config | `site_monitor/config/sites.yaml` | 4 monitored sites |

Internal broken links below are the **union** of the bounded + recovery runs. External broken links
come **only** from the recovery run (the bounded/latest runs used `--no-external-links`).

> **Accuracy note.** Broken-link detection uses a bounded HEAD/GET check. External hosts that reject
> bots (return `None`/`403` to HEAD) can appear "broken" while being live in a browser — these are
> flagged as **noisy / verify manually**, not confirmed dead. Internal `404`s are high-confidence.

---

## Summary — count by site

| Site | Internal broken | External broken | Total |
|---|---|---|---|
| ambimat.com | **7** | 15 (3 real 404, 1× 403, 11 noisy/None) | 22 |
| ambisecure.ambimat.com | 0 | 2 (both noisy social) | 2 |
| ambiautomation.ambimat.com | 0 | 2 (both noisy social) | 2 |
| esim.ambimat.com | 0 | 0 | 0 |
| **Total** | **7** | **19** | **26** |

## Summary — count by status / error

| Status/Error | Count | Meaning |
|---|---|---|
| `404` internal | 7 | Confirmed missing page on our own site — **priority fixes** |
| `404` external | ~7 | Third-party page moved/removed — update or remove link |
| `403` external | 1 | Third-party blocks bots — likely alive; verify manually |
| `None` external | ~11 | Connection failed / bot-hostile host (incl. Twitter/Facebook) — mostly false positives |

---

## ambimat.com

### Internal broken links (7 × HTTP 404) — high confidence

| Source page | Broken target | Status | Type | Suggested fix |
|---|---|---|---|---|
| `/` | `/categories/ambi-power/` | 404 | internal | Create missing page **or** update/remove nav link (category page absent) |
| `/fast-identity-online-fido/` | `/categories/ambi-con/` | 404 | internal | Create missing page **or** update/remove link |
| `/` | `/design/ambi-iot/medicals/` | 404 | internal | Update URL / create page / remove link |
| `/` | `/design/ambi-iot/pubs-and-brewery` | 404 | internal | Update URL (also see trailing-slash variant below) / create page / redirect |
| `/fast-identity-online-fido/` | `/design/ambi-iot/pubs-and-brewery/` | 404 | internal | Same target as above with trailing slash — fix once, both resolve |
| `/fast-identity-online-fido/` | `/design/ambi-iot/retail/` | 404 | internal | Update URL / create page / remove link |
| `/` | `/design/ambi-iot/smart-watches` | 404 | internal | Update URL / create page / remove link |

Pattern: the `/design/ambi-iot/*` and `/categories/*` sections are linked from the homepage and the
FIDO article but return 404 — likely renamed/removed category pages. Fix at the source (menu /
template) so all variants are corrected together; add redirects if these URLs were previously live
and indexed.

### External broken links (15) — from the recovery run

| Source page | Broken target | Status | Suggested fix |
|---|---|---|---|
| `/what-is-lpwan-and-types-of-lpwan-network/` | `rutronik.com/article/.../narrow-band-iot-an/` | 404 | Update to current article URL or remove |
| `/fast-identity-online-fido/` | `blog.identityautomation.com/two-factor-authentication-2fa-explained-fido-u2f` | 404 | Update URL or remove |
| `/cellular-network-based-wide-area-networks/` | `sierrawireless.com/iot-blog/.../lte-m-vs-nb-iot/` | 404 | Update URL or remove (Sierra Wireless is now Semtech) |
| `/challenges-to-iot-security-2/` | `enterprisedigi.com/iot/articles/iot-security-challenges` | 404 | Update URL or remove |
| `/the-transformation-of-city-street-lighting/` | `northeast-group.com/data.html` | 404 | Update URL or remove |
| `/uvc-based-sanitization-devices-really-effective-against-covid-19/` | `drdo.gov.in/counter-covid-19-technologies` | 404 | Update URL or remove |
| `/an-introduction-to-java-card-technology/` | `informatik.uni-augsburg.de/.../JCADG.pdf` | 404 | Update URL or remove (old course PDF) |
| `/challenges-to-iot-security-2/` | `readwrite.com/2019/09/05/9-main-security-challenges...` | 403 | **Verify manually** — likely live but blocks bots; probably keep |
| `/securing-your-iiot-infrastructure/` | `maximintegrated.com/.../5522.html` | None | Verify — Maxim merged into analog.com; likely update URL |
| `/non-cellular-network-based-wide-area-networks-1/` | `engineering.eckovation.com/sigfox-vs-lora-one-prefer-iot-device/` | None | Verify manually; update or remove if dead |
| `/the .../` (homepage) | `ivycamp.in/` | None | Verify — domain may be dead; update or remove |
| `/securing-your-iiot-infrastructure/` | `blog.nettitude.com/uk/programmable-logic-controller-security` | None | Verify manually; update or remove |
| `/what-is-lpwan-and-types-of-lpwan-network/` | `blog.mxc.org/benefits-limitations-lpwan/` | None | Verify manually; update or remove |
| `/` | `twitter.com/ambimat` | None | **Ignore** — bot-hostile host (false positive); verify the profile in a browser |
| `/` | `facebook.com/Ambimat-Electronics-...` | None | **Ignore** — bot-hostile host (false positive); verify in a browser |

## ambisecure.ambimat.com

Internal broken: **none**.

| Source page | Broken target | Status | Type | Suggested fix |
|---|---|---|---|---|
| `/` | `twitter.com/ambimat` | None | external | **Ignore** — bot-hostile (false positive) |
| `/` | `facebook.com/Ambimat-Electronics-...` | None | external | **Ignore** — bot-hostile (false positive) |

## ambiautomation.ambimat.com

Internal broken: **none**.

| Source page | Broken target | Status | Type | Suggested fix |
|---|---|---|---|---|
| `/` | `twitter.com/ambimat` | None | external | **Ignore** — bot-hostile (false positive) |
| `/` | `facebook.com/Ambimat-Electronics-...` | None | external | **Ignore** — bot-hostile (false positive) |

## esim.ambimat.com

No broken links found (internal or external — external not checked in the internal-only runs; the
recovery run did not crawl this site).

---

## Priority fixes (internal 404s — fix these first)

All on **ambimat.com**, all HTTP 404, all high confidence. Fixing the source links (homepage menu /
FIDO article / templates) resolves them:

1. `/design/ambi-iot/pubs-and-brewery` **and** `/design/ambi-iot/pubs-and-brewery/` (same page, two link variants)
2. `/design/ambi-iot/medicals/`
3. `/design/ambi-iot/retail/`
4. `/design/ambi-iot/smart-watches`
5. `/categories/ambi-con/`
6. `/categories/ambi-power/`

Recommended approach: decide per URL whether the target should **exist** (→ create the page or
restore it) or is **obsolete** (→ remove the link from the menu/article and add a 301 redirect if the
URL was previously indexed).

## External / noisy links (external links were checked in the recovery run)

External links **were** checked once (recovery run, 2026-07-01 17:22). Findings split into:

- **Likely real dead links (update or remove):** rutronik, identityautomation blog, sierrawireless,
  enterprisedigi, northeast-group, drdo.gov.in, uni-augsburg PDF (all 404); maximintegrated (Maxim →
  analog.com).
- **Verify manually (may be live but block bots):** readwrite.com (403); eckovation, ivycamp.in,
  nettitude, mxc.org (None).
- **Ignore — false positives (bot-hostile hosts):** `twitter.com/ambimat`,
  `facebook.com/Ambimat-Electronics-...` (appear on all three main sites; confirmed alive in a
  browser — the monitor's `external_check_skip_hosts` list now skips these on future runs).

> The **latest bounded crawl used `--no-external-links`**, so external links are NOT continuously
> monitored; the data above is a one-time snapshot from the recovery run. Re-check external links
> only on demand with a capped external run.

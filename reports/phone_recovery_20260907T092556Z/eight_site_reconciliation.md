# Eight-site reconciliation

## Every site list found in the implementation — OBSERVED

Only **two** live, authoritative site inventories exist. Everything else that names a
site is frozen historical evidence and was correctly left untouched.

| # | Location | Consumed by | Status |
| --- | --- | --- | --- |
| 1 | `site_monitor/config/sites.yaml` (repo → deployed to `~/site_monitor/config/sites.yaml`) | 10:00 site monitor | **AUTHORITATIVE — updated** |
| 2 | `~/seo_tracker/phone/config.yaml` (device-only before this audit) | 11:00 SEO tracker | **AUTHORITATIVE — updated + now versioned** as `phone/seo_tracker_config.yaml` |
| — | `reports/scheduler_verification/phone_scripts_snapshot/seo_config.yaml` | nothing | frozen snapshot — NOT edited |
| — | `reports/ambimat_phone_extraction/2026-07-31…/raw/**` | nothing | frozen evidence — NOT edited |
| — | `reports/baseline_2026072[89]`, `reports/baseline_20260730` | nothing | frozen evidence — NOT edited |
| — | `docs/*remediation_prompt*.md`, `docs/scheduler_verification_20260727.md` | nothing | historical prose — NOT edited |

The **12:00 cache monitor** is single-target by design (it inspects only the
`https://ambimat.com/` front page) and is not a site-list consumer.
The **measurement queue** is keyed by `run_id`, not by site list.

## The drift — OBSERVED

Both inventories were edited by hand, independently, and had silently drifted from live
reality: `v2x.ambimat.com` and `ai.ambimat.com` were **live, returning HTTP 200, serving
robots.txt and sitemap.xml — and monitored by neither job**. Nothing failed, because
nothing checked.

## Reconciliation table — after repair

| Site | Live monitor (10:00) | SEO monitor (11:00) | Local state | Scheduler | Reporting | Status |
| --- | --- | --- | --- | --- | --- | --- |
| ambimat.com | YES | YES | present | 10:00/11:00 + catch-up | merged report + notification | already configured |
| ambisecure.ambimat.com | YES | YES | present | 10:00/11:00 + catch-up | merged report + notification | already configured |
| ambipower.ambimat.com | YES | YES | present | 10:00/11:00 + catch-up | merged report + notification | already configured |
| ambiautomation.ambimat.com | YES | YES | present | 10:00/11:00 + catch-up | merged report + notification | already configured |
| **v2x.ambimat.com** | **YES** | **YES** | created this run | 10:00/11:00 + catch-up | merged report + notification | **ADDED 2026-09-07** |
| **ai.ambimat.com** | **YES** | **YES** | created this run | 10:00/11:00 + catch-up | merged report + notification | **ADDED 2026-09-07** |
| roboracer.ambimat.com | YES | YES | present | 10:00/11:00 + catch-up | merged report + notification | already configured |
| orders.ambimat.com | YES | YES | present | 10:00/11:00 + catch-up | merged report + notification | already configured |

All eight mandatory sites are covered by both jobs, both on the Mac and on the device.

## Sites present but NOT in the mandatory eight

`esim.ambimat.com` — **kept, flagged for an owner decision.** It is live (HTTP 200,
sitemap present), it has been crawled daily since 2026-07-01, and the queued
`esim_phase3b4_20260901` measurement run targets it. Silently dropping it would delete
working monitoring and orphan a queued job, so it was left in place. If eSIM is in fact
retired, remove it from both inventories and from `queue.tsv` in one deliberate change.

`ambimechanicals` — **absent everywhere, correctly.** Verified by a case-insensitive
search of the entire working tree: zero hits. Not reintroduced, and
`tests/test_site_inventory.py::test_retired_sites_absent` now fails the suite if it ever is.

## Drift guard — CHANGED

`tests/test_site_inventory.py` (stdlib only, runs anywhere) enforces four invariants
against **both** inventories:

1. all eight mandatory sites present
2. no retired site resurrected
3. no duplicate entries
4. the two inventories agree exactly with each other

Negative-tested: removing `v2x` from `sites.yaml` fails invariants 1 and 4 (verified).

Full consolidation into one shared file was deliberately **not** done: the two configs
have genuinely different schemas (the site monitor needs only `base_url`; the SEO
tracker needs `slug`, `seed_keywords` and `primary_clusters`). The guard test closes the
drift hole without a rewrite.

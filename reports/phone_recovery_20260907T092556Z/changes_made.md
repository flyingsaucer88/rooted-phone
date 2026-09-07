# Changes made — 2026-09-07

Everything here is a repair for a defect proved by evidence in this directory.
No change was made to any production website. No credential was created, moved or logged.

## Repository (Mac, authoritative clone `git_repo/Rooted-Phone`)

| File | Change | Why |
| --- | --- | --- |
| `site_monitor/config/sites.yaml` | +`V2X` (`https://v2x.ambimat.com`), +`AI Tools` (`https://ai.ambimat.com`); page-budget comment 7→9 sites | both live and monitored by nothing |
| `phone/seo_tracker_config.yaml` | **new** — the SEO tracker's domain config, now version-controlled, with V2X and AI Tools added (seed keywords + clusters authored from the live pages) | the list existed only on the device, so it drifted unnoticed and untestably |
| `tests/test_site_inventory.py` | **new** — 4 invariants over *both* inventories: eight mandatory present, no retired site, no duplicates, the two agree | nothing failed when two sites went missing |
| `measurement_queue/run_measurement_queue.sh` | per-blocker verdict (`SOURCE PROMPT NOT INSTALLED` / `AUTHENTICATED DATA SOURCE UNAVAILABLE` / `NO EXECUTOR CONFIGURED`); verdict threaded into `write_blocked_evidence`, `REPORT.md`, `result.json`, log line and notification; removed the duplicated `BLOCKED — ` prefix | every blocker was reported as an authentication failure, sending the owner after credentials that were never the cause |
| `measurement_queue/lib_measure.sh` | `mq_notify()` honours `MQ_NOTIFY_DISABLE` | the scenario suite was posting real Android notifications containing fake-clock temp paths, overwriting the live banner |
| `measurement_queue/tests/test_measurement_queue.sh` | pinned `AMBIMAT_MEASURE_CREDS` to an empty temp dir; set `MQ_NOTIFY_DISABLE=1`; renamed the `ES` collision in test 11 to `ESH`; rewrote test 12 to assert the missing-prompt verdict is *not* an auth verdict; added test 12b (genuine credential blocker → auth verdict, single `BLOCKED` prefix, state/REPORT/result agreement) | lock in the fix; test 11 was silently clobbering the eSIM run-id used by later tests |
| `.gitignore` | ignore `reports/phone_recovery_*/raw/` | 14 MB of raw device archives do not belong in git; the analysis and manifests do |

## Device (`u0_a122@` Moto G4 Plus) — deployed and verified

| Phone path | Change |
| --- | --- |
| `~/site_monitor/config/sites.yaml` | replaced with the 9-site repo copy; parses, 9 sites |
| `~/seo_tracker/phone/config.yaml` | replaced with `phone/seo_tracker_config.yaml`; parses, 9 domains |
| `~/measurement_queue/run_measurement_queue.sh` | replaced with the fixed runner |
| `~/measurement_queue/lib_measure.sh` | replaced |
| `~/measurement_queue/tests/test_measurement_queue.sh` | replaced |
| `~/site_monitor/tests/test_redirect_base.py` | added (was missing on-device) |
| `~/.recovery_backup_20260907/` | **new** — pre-change copies of all four replaced files |

Originals are preserved twice: in `~/.recovery_backup_20260907/` on the phone and inside
`raw/phone_home_subset.tar.gz` in this directory.

## Deliberately NOT changed

* **`esim.ambimat.com` left in both inventories.** Not one of the mandatory eight, but
  live, crawled daily since July, and the target of a queued measurement run. Dropping it
  would delete working monitoring and orphan a job. Flagged for an owner decision instead.
* **`queue.tsv` dependency chain left intact.** `ambimat_ga4_gsc_20260829` is starved
  behind a run whose prompt was never supplied. Breaking the dependency would let a
  measurement gate run out of its designed order.
* **Production websites untouched.** `ambimat.com/products/` (404) and the leaked HTML
  comment in `ai.ambimat.com`'s `<title>` are reported, not fixed.
* **No credential created or substituted.** See `authentication_error_root_cause.md`.
* **2026-09-06 not backfilled.** Same-day-only catch-up is the intended design.

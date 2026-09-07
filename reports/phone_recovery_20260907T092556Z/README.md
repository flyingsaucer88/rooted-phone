# Phone recovery audit — 2026-09-07

Full forensic recovery of the Rooted Phone (Moto G4 Plus, `athene_f`) after it was
powered off for a day. Every claim below is tagged **OBSERVED** (measured on the device
or the live web), **INFERRED**, **CHANGED**, **VERIFIED** or **UNRESOLVED**.

Evidence captured **before** any repair.

## Contents

| File | What it holds |
| --- | --- |
| `README.md` | this summary |
| `inventory/device_identity.txt` | device, clock, uptime, battery, network, crontab, processes (SSID/IP/MAC redacted) |
| `inventory/repo_state.md` | both Mac repo clones, branch/HEAD/remote/ahead-behind |
| `scheduler_inventory.md` | every mechanism able to launch work + the activity table |
| `run_history.md` | reconstructed timeline, boot history, per-job completion proof |
| `eight_site_reconciliation.md` | every site list found; the eight-site coverage table |
| `live_site_reconciliation.md` | live probe of all nine hosts + stale-state findings A–F |
| `authentication_error_root_cause.md` | the "authenticated data source unavailable" chain, UI → code → data source |
| `scheduler_durability.md` | the eight durability conditions + SSH-hang regression check |
| `changes_made.md` | every file changed, why |
| `verification_results.md` | post-repair per-site results and test counts |
| `checksums/archive_manifest.csv` | the two raw archives, sha256, file counts |
| `checksums/phone_log_manifest.tsv` | 1978 original phone paths → archive members |
| `checksums/SHA256SUMS` | checksums of archives and inventory files |
| `raw/*.tar.gz` | **not committed** (see `.gitignore`) — the raw device capture, on disk only |

## Headline findings

1. **The phone was off for all of 2026-09-06** and booted 2026-09-07 12:34 IST.
   Catch-up worked: all three daily jobs completed by 13:11. — OBSERVED
2. **Today's 10:00 and 11:00 jobs both ran and did real work** (830 pages crawled, 625 SEO
   pages analysed), contrary to the initial suspicion that nothing ran. — VERIFIED
3. **2026-09-06 was never backfilled and never will be** — catch-up is same-day only, by
   design. — OBSERVED
4. **Two live production sites were monitored by nothing**: `v2x.ambimat.com` and
   `ai.ambimat.com`. Added to both inventories. — CHANGED
5. **The phone-screen error was two different faults wearing one label.** For the two
   oldest runs it was *not* an authentication problem at all — the code stamped
   "AUTHENTICATED DATA SOURCE UNAVAILABLE" on every blocker. Fixed. — CHANGED
6. **The genuine authentication failure is un-provisioned credentials** — the credential
   directory has been empty since it was created on 2026-08-25. Owner action required;
   no credential can be fabricated. — UNRESOLVED (by necessity)

## Extraction integrity — VERIFIED

1978 files, 2026-07-01 → 2026-09-07, pulled over the USB SSH bridge as two gzip archives.
Both pass `gzip -t`; entry counts match the on-device `find | wc -l` (1799 report files
+ 179 scheduler/state files). **Nothing on the phone was deleted, rotated or truncated.**

# "Authenticated data source unavailable" — root cause

## Exact error string — OBSERVED

Two distinct renderings, both from the measurement queue:

Android notification (what is visible on the phone screen):

```
Title:   <label> — BLOCKED
Content: Authenticated data source unavailable. /data/data/com.termux/files/home/scheduled_measurements/<run_id>
```

Persisted state / evidence verdict:

```
BLOCKED — AUTHENTICATED DATA SOURCE UNAVAILABLE
```

## Component that renders it — OBSERVED

`measurement_queue/run_measurement_queue.sh`, dispatched every 30 minutes by the
`ambimat-scheduler-watchdog` cron line via `~/seo_tracker/phone/ensure_scheduler.sh`.
The string is written to four places: the run's `.state` file (`verdict=`), the evidence
`REPORT.md`, `result.json`, and the `termux-notification` banner.

## The finding: ONE message, TWO unrelated causes — OBSERVED

The pre-repair code computed a human-readable `reason` for **three** different blockers
but then unconditionally stamped the **same** verdict and the **same** notification text
on all of them:

```sh
mq_set "$id" verdict "BLOCKED — AUTHENTICATED DATA SOURCE UNAVAILABLE"   # hard-coded
mq_notify "$id" "$label — BLOCKED" "Authenticated data source unavailable. $ev"
```

So the phone reported an authentication failure for runs whose real blocker was a
missing prompt file. The message that prompted this audit was, for the two oldest and
most visible runs, **not an authentication problem at all**.

| Run | Screen said | Actually was |
| --- | --- | --- |
| V2X (2026-08-27) | authenticated data source unavailable | source prompt `v2x_measurement_gate.md` was never installed |
| AmbiSecure (2026-08-29) | authenticated data source unavailable | source prompt `ambisecure_gsc_7day.md` was never installed |
| eSIM (2026-09-01) | authenticated data source unavailable | **correct** — credentials absent |

A second, cosmetic defect: the preflight branch prefixed its own reason with
`BLOCKED — `, which the logger prefixed again, producing `BLOCKED — BLOCKED — …`
in `measurement_queue.log`.

## Affected data source (the genuine case) — OBSERVED

Google Search Console + GA4 (one Google **service-account** credential) and the
Anthropic API key, read by `measurement_queue/api/creds.py` from
`~/.ambimat_measure_creds/`.

```
google_sa : MISSING  (file absent)
bing      : MISSING  (file absent)
linkedin  : MISSING  (file absent)
anthropic : MISSING  (file absent)
```

The directory exists with correct mode 700, created 2026-08-25 13:03 IST, and has been
**empty ever since**. The credential files were never installed on the device.

## Root cause — classified

**Missing credential files (never provisioned).** Explicitly *not*:

* not expired authentication — no token was ever present to expire
* not revoked credentials — nothing to revoke
* not a network failure — see reachability proof below
* not a missing environment variable — `AMBIMAT_MEASURE_CREDS` correctly defaults
* not a permission problem — directory is mode 700, exactly as `creds.py` requires
* not a stale token, GitHub auth, Google API change, storage/path issue, or dead service
* **plus a genuine code defect** — the verdict/notification mislabelled every other blocker as this one

Network reachability from the phone, 2026-09-07 15:06 IST (`api/smoke.py reachability`):

```
OK   oauth2.googleapis.com          TLSv1.3
OK   analyticsdata.googleapis.com   TLSv1.3
OK   analyticsadmin.googleapis.com  TLSv1.3
OK   searchconsole.googleapis.com   TLSv1.3
OK   ssl.bing.com                   TLSv1.3
OK   api.anthropic.com              TLSv1.3
FAIL api.linkedin.com               ConnectionResetError   <- OPTIONAL source; degrades, never blocks
```

Every **critical** endpoint is reachable. The transport is healthy; only the
credential material is absent.

## First evidence — OBSERVED

* First time the phone screen showed this text: **2026-08-27 01:00:06 IST** (V2X, mislabelled).
* First *genuine* authentication block: **2026-09-01 01:00:15 IST** (eSIM).
* 34 auth-labelled log events between 2026-09-01 and 2026-09-07.

## Repair — CHANGED / VERIFIED

**Code (done, verified on the device).** Each blocker now reports its own cause:

| Blocker | Verdict |
| --- | --- |
| prompt file absent | `BLOCKED — SOURCE PROMPT NOT INSTALLED` |
| preflight failed | `BLOCKED — AUTHENTICATED DATA SOURCE UNAVAILABLE` |
| no executor configured | `BLOCKED — NO EXECUTOR CONFIGURED` |

State, `REPORT.md`, `result.json`, the log line and the notification now all agree, and
the doubled `BLOCKED — BLOCKED —` prefix is gone. Verified on the phone at
2026-09-07 15:08:52–15:08:59 IST and in the live notification tray.

**Credentials — REQUIRES OWNER ACTION (the one thing that cannot be done non-interactively).**
A Google service-account key and an Anthropic API key are owner secrets; they exist
nowhere on the device or in the repository, and fabricating or substituting them is not
an option. Install, on the phone only:

```
~/.ambimat_measure_creds/google_service_account.json   (mode 600, dir mode 700)
~/.ambimat_measure_creds/anthropic_api_key             (mode 600)
```

Then verify the *actual authenticated retrieval*, not just the absence of the warning:

```
cd ~/measurement_queue/api && python3 smoke.py full
```

which mints a real token and performs read-only `gsc.sites.list` and
`ga4.accountSummaries` calls through `api/guard.py`'s allowlist.

## UNRESOLVED

* The credentials above (owner action).
* `v2x_measurement_gate.md` and `ambisecure_gsc_7day.md` were never supplied; only
  `MISSING_*.md` placeholders exist. Those two runs stay correctly BLOCKED.
* `ambimat_ga4_gsc_20260829` is consequently **starved**: it depends on
  `ambisecure_gsc_7day_20260829`, which cannot complete without its prompt. Left as-is
  deliberately — breaking the dependency would let a gate run out of its designed order.

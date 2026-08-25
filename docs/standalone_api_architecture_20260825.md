# Standalone API executor for the measurement queue — 2026-08-25

The browser path is dead: the Moto G4 is unrooted, Chrome's DevTools socket admits only
uid 0/2000, Android UI automation is blind from Termux, and no Mac will be attached at
01:00 IST. This replaces the execution backend only. The scheduler — cron, watchdog, boot
catch-up, global locks, the 2026-08-28 blackout, serialization, idempotency, evidence
conventions, the 10:00/11:00/12:00 daily jobs and notifications — is untouched.

    cron / watchdog / boot catch-up      (unchanged)
      -> run_measurement_queue.sh        (unchanged)
        -> preflight_auth.sh             (rewritten: API credentials, not browsers)
        -> run_api_measurement.sh        (new: MQ_EXECUTOR_CMD backend)
          -> api/execute.py              (raw-first: collect, then interpret)
            -> api/guard.py              (read-only allowlist; every call recorded)
            -> api/gauth.py              (service-account RS256, pure Python)
            -> api/collect.py            (GA4 / GSC / Bing / LinkedIn / live HTTP)
            -> api/claude_runtime.py     (Anthropic Messages API, no tools)
          -> REPORT.md + result.json + raw/ + SHA256SUMS + api_call_manifest.jsonl
          -> termux-notification

## Why the crypto is hand-rolled

`google-auth` hard-requires `cryptography`. Its Termux package installs into
python3.14's site-packages while the automation runs on python3.13, and the wheel needs a
Rust toolchain on armv7l. Rather than move the interpreter the existing daily jobs run on,
`gauth.py` mints the service-account JWT with pure-Python `rsa` + `pyasn1`, both already
installed. It refuses any scope that does not end in `.readonly`.

## Mutation guard

`api/guard.py` keys on `(service, operation)` and re-checks method and URL, because
several read-only analytics calls are POSTs (`searchAnalytics.query`,
`urlInspection.index.inspect`, `runReport`) and several mutating calls are not. Anything
absent from `ALLOW` never leaves the process. `DENY` names the mutations explicitly so a
refusal says what was attempted:

    GSC sitemap submit/delete · GSC site add/delete · Indexing API · Request Indexing
    Validate Fix · Bing SubmitUrl/SubmitContent/SubmitFeed/AddSite/RemoveSite
    GA4 property create/patch/delete · GA4 key-event create/patch/delete
    GA4 data-stream create/patch · LinkedIn post/comment/reaction creation

A last-ditch substring net also rejects any URL matching a mutation path regardless of the
operation label, and rejects Bing's `/api.svc/soap` and `/api.svc/pox` transports, which
retire 2026-08-31 — inside our run window. Only `/api.svc/json` is allowed.

## Indexing reconstruction

Search Console's API does not expose the Page Indexing UI aggregate. `collect.census()`
inspects cohorts in the priority order the source prompt defines, caches each URL so a
cohort overlap costs one call, stops at the budget and lists what it skipped. Every result
carries `SOURCE = URL_INSPECTION_RECONSTRUCTION`; nothing is ever labelled
`SOURCE = GSC_AGGREGATE_UI`. Quota: 2000 inspections/property/day, 600/minute.

## Maturity

`collect.mature_window()` implements the 72-hour rule: GA4 report end dates are clamped so
a run cannot report `(not set)` / Unassigned attribution from a window still filling in.
At the 2026-08-29 01:00 IST Ambimat slot that boundary is 2026-08-26.

## Degradation

`preflight_auth.sh` splits sources into critical (GSC, GA4, Claude) and optional (Bing,
LinkedIn, SERP, AI Overview). An optional source that is missing degrades the run and is
reported as `NOT AVAILABLE IN STANDALONE API MODE`; it never blocks it. A missing critical
source blocks, and a blocked run stays retryable.

## Prompt integrity

`execute.py:verify_prompt()` refuses to run on a prompt that is missing, truncated, or
whose SHA-256 does not match `prompts/MANIFEST.tsv`. V2X, AmbiSecure and the complete eSIM
text are still outstanding; their runs cannot be armed until those files arrive.

## Per-run targets

`execute.py` collects nothing without `targets/<run_id>.json`, which names the properties,
windows and cohorts — all defined by that run's authoritative prompt. Three of the four do
not exist yet, deliberately: inventing them would be inventing the measurement.

## Owner provisioning (one time, may use the Mac now)

1. Create or choose a Google Cloud project.
2. Enable the Analytics Data API, Analytics Admin API and Search Console API.
3. Create a dedicated service account; download a JSON key. No IAM roles are needed —
   access is granted per property, not through Cloud IAM.
4. GA4 → each property → Property Access Management → add the service-account email as
   **Viewer**.
5. Search Console → each property → Settings → Users and permissions → add the same email.
   **Full** is required for URL Inspection; Restricted is not sufficient.
6. Bing Webmaster Tools → Settings → API Access → generate an API key.
7. LinkedIn: create a developer app and apply for the Community Management API with
   `r_member_postAnalytics`. Approval is not immediate — see the report for the deadline risk.
8. Create a dedicated Anthropic API key in its own workspace with a spend limit.
9. Install on the phone, never in this repo:

       chmod 700 ~/.ambimat_measure_creds
       ~/.ambimat_measure_creds/google_service_account.json   (600)
       ~/.ambimat_measure_creds/bing_api_key                  (600)
       ~/.ambimat_measure_creds/anthropic_api_key             (600)
       ~/.ambimat_measure_creds/linkedin_oauth.json           (600)

10. `cd ~/measurement_queue/api && python3 smoke.py full` — read-only smoke tests only.
11. Write `targets/<run_id>.json` for each run whose authoritative prompt has arrived.

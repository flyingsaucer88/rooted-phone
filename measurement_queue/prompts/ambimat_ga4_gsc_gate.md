# AMBIMAT.COM — GA4 + GSC POST-REMEDIATION MEASUREMENT GATE

Run this on **28 August 2026**.

This is a **measurement, validation and evidence-reconciliation phase**.

It is NOT a new remediation campaign.

The major GA4 / CF7 / consent / SEO technical work was completed previously. Do not reopen settled defects merely because a diagnostic warning or immature number looks unusual.

Use Claude for Chrome where authenticated Google Analytics / Search Console access is required, and use CLI/browser inspection only where useful for independent production verification.

---

# 1. PRIMARY OBJECTIVE

Determine whether the repaired Ambimat analytics and organic-search measurement environment remains healthy after approximately one week of observation.

Answer four questions:

1. Is GA4 collection still technically healthy?
2. Is `generate_lead` now producing credible lead measurements rather than page-view noise?
3. Has the previous `(not set)` / Unassigned issue remained resolved on mature data?
4. What does GSC now show after the recent SEO/indexing/migration work?

Do not make changes simply because this is a follow-up date.

---

# 2. PROPERTY AUTHORITY

Freshly verify before reading any reports:

* GA4 account: `Ambimat SEO`
* Account ID: `164270115`
* Property: `ambimat`
* Property ID: `250947051`
* Stream ID: `2134489266`
* Measurement ID: `G-03T01GG8K1`
* reporting timezone
* number of web streams
* Google-tag destinations
* connected site tags

Do not trust predecessor screenshots blindly.

Record any unexpected difference.

---

# 3. CHANGE-HISTORY GATE

Before interpreting data, inspect GA4 change history from the end of the previous campaign through the present.

Enumerate every mutation affecting:

* events
* key events
* data filters
* attribution
* channel groups
* stream configuration
* Measurement IDs
* Google tag settings
* cross-domain settings
* unwanted referrals
* retention
* Consent Mode-related configuration where visible
* product links

Classify every change:

* EXPECTED / AUTHORIZED
* EXPLAINED LATER WORK
* UNEXPECTED
* MATERIAL TO MEASUREMENT
* IMMATERIAL TO MEASUREMENT

Do not modify anything while doing this.

---

# 4. `generate_lead` GOVERNANCE CHECK

Freshly inspect the current live definition and actual observed behaviour of:

`generate_lead`

Do NOT inherit the obsolete 18 August page-view-based definition from old reports.

Determine what the event actually represents now.

Verify whether it is connected to a **genuine successful Contact Form 7 mail-send / success condition**, rather than:

* opening `/contact/`
* `page_view`
* `form_start`
* raw DOM `form_submit`
* unsuccessful/reCAPTCHA-blocked submissions

Confirm:

* event exists
* key-event status
* counting method
* current trigger semantics
* stream
* observed event count since remediation
* users generating the event
* relevant landing/source/medium information where available

Cross-reference this against known genuine CF7 successes where possible.

The objective is not to generate another test submission unless there is a proven functional reason.

Do not submit CF7 merely to manufacture analytics data.

Classify:

`GENERATE_LEAD_MEASUREMENT = CREDIBLE`

or

`GENERATE_LEAD_MEASUREMENT = NEEDS_MORE_OBSERVATION`

or

`GENERATE_LEAD_MEASUREMENT = DEFECT_CONFIRMED`

Explain with evidence.

---

# 5. GA4 DATA-MATURITY RULE

Retain the established GA4 maturity rule.

For `(not set)` / Unassigned defect assessment, only treat a complete day as mature when it is at least approximately **72 hours old**.

Do not use immature 26–27 August data to reopen remediation.

For each mature post-remediation day available, record:

* Sessions
* Session source / medium `(not set)`
* `(not set)` rate
* Session default channel group `Unassigned`
* Unassigned rate

Also inspect:

* first-user source / medium
* first-user channel group

Create a daily table.

The standing escalation rule is:

Investigate only if:

1. a complete day at least 72 hours old exceeds **5% `(not set)`**, AND
2. this occurs for **two consecutive mature days**

OR a genuine new defect signal exists, such as:

* first-user contamination
* missing/failed `session_start`
* production hostname leakage
* duplicate base GA tags
* a new active Measurement ID
* broken consent sequencing

One isolated mature day slightly above 5% is not enough.

Immature days are not enough.

---

# 6. GA4 CHANGE FREEZE

The standing position is:

`GA4_CHANGE_FREEZE = YES`

Therefore do NOT alter merely to improve reporting appearance:

* GA4
* Site Kit
* CookieYes
* Consent Mode
* attribution
* channel groups
* stream
* Measurement ID
* hostname configuration
* cross-domain settings
* data filters

Only report a proposed remediation if a new defect is actually proven.

Do not execute it in this run unless there is separate explicit owner authorization.

---

# 7. RUNTIME COLLECTION SANITY

Perform the lightest safe production inspection needed.

Verify:

* one intended production GA4 loader
* one intended config for `G-03T01GG8K1`
* no unexpected active sibling Measurement ID
* no duplicate page-view collection
* expected consent default
* expected post-consent sequence where safely observable
* no production hostname contamination
* no obvious analytics-blocking JavaScript error

Remember the previously identified Site Kit telemetry-style ID must not be misclassified as a second production Measurement ID without runtime evidence that it is actually active.

Do not manufacture sessions unnecessarily.

---

# 8. TAG DIAGNOSTICS

Read GA4 Tag Diagnostics fresh.

Record all current warnings.

Compare them with the previously adjudicated warnings.

Do not repair:

* “Some of your pages are not tagged”
* “Additional domains detected”

merely because they remain visible, if current production evidence still proves them to be stale/false-positive diagnostics.

Only reopen them with new contradictory evidence.

---

# 9. TRAFFIC QUALITY / ATTRIBUTION

For the post-remediation observation window, report at minimum:

* users
* sessions
* engaged sessions
* engagement rate
* Organic Search sessions
* Direct sessions
* Referral sessions
* AI-assistant traffic where GA4 exposes it
* `(not set)`
* Unassigned
* `generate_lead`
* purchase, if still applicable to this property

Do not pretend GA4 contains all site traffic where consent limits observation.

Separate facts from interpretation.

---

# 10. SEARCH CONSOLE — FRESH STATE

Open the correct Ambimat Search Console property.

Read everything fresh.

Record:

**latest GSC data date**

Do not assume a fixed reporting lag.

Measure the current state of:

### Performance

At minimum:

* clicks
* impressions
* CTR
* average position
* query count / breadth
* page count receiving impressions

Compare sensible windows without overlap.

Use:

* an appropriate pre-remediation / pre-migration baseline
* the latest available post-change period

Do not manufacture a “seven-day” comparison if Google has not yet exposed seven complete post-change days.

Explicitly state the actual available date range.

---

# 11. INDEXING / MIGRATION FOLLOW-UP

Re-check the Ambimat → AmbiSecure migration/indexing state established in the SEO campaign.

Freshly determine:

* current expected-indexable Ambimat URLs
* confirmed indexed
* expected-but-not-indexed
* unknown
* migrated sources
* redirect status
* destination indexing progress

For migrated URLs:

* confirm source redirects still work
* verify query-string preservation on representative URLs
* check for redirect chains/loops
* inspect whether Google is beginning to replace Ambimat sources with AmbiSecure destinations

Do not Request Indexing during this measurement run.

Do not alter redirects.

---

# 12. GSC INDEXING CATEGORIES

Refresh the important Search Console indexing categories and distinguish:

* genuinely current issues
* stale Google examples
* intentional exclusions
* migrated URLs
* technical defects

Pay particular attention to:

* Crawled — currently not indexed
* Discovered — currently not indexed
* Page with redirect
* Not found (404)
* Redirect error
* Server error
* Alternate page with proper canonical
* Blocked by robots.txt

Do not report stale examples as live defects without HTTP/canonical/indexability verification.

---

# 13. PRIOR MISSING-URL RECONCILIATION

Re-run the outstanding expected-but-not-indexed set.

For each URL or useful aggregate, determine whether since the previous baseline it is now:

* INDEXED
* STILL EXPECTED BUT NOT INDEXED
* MIGRATED
* INTENTIONALLY EXCLUDED
* REMOVED / REDIRECTED
* UNKNOWN

Report movement rather than merely restating the old total.

---

# 14. CORE WEB VITALS

Refresh GSC Core Web Vitals only as an observation.

Record:

* Mobile Good
* Mobile Needs Improvement
* Mobile Poor
* Desktop Good
* Desktop Needs Improvement
* Desktop Poor

If Google still shows historical/mobile NI groups, do not immediately mutate production.

Identify whether the affected URLs correspond to current live pages and whether the data period is still representative.

---

# 15. NO-CAUSATION RULE

Do not claim:

* SEO work caused an impression increase
* migration caused a ranking increase
* GA4 remediation caused organic traffic growth
* any individual content edit caused ranking movement

unless evidence actually supports causality.

Use wording such as:

* post-remediation observation
* post-migration observation
* correlation
* current movement
* insufficient data

---

# 16. MUTATION PROHIBITION

This run is READ-ONLY unless an independent safety-critical defect is discovered.

Do NOT:

* edit GA4
* edit GTM
* edit CookieYes
* edit Site Kit
* edit WordPress
* edit the MU plugin
* modify CF7
* modify redirects
* change Yoast
* change titles/H1s/canonicals
* Request Indexing
* change Search Console settings
* submit test forms simply to produce events
* create temporary filters
* create permanent Explorations unless absolutely necessary
* deploy code
* push unrelated commits

If a defect is discovered, document the remediation required and STOP for owner authorization.

---

# 17. FINAL REPORT

Return:

## A. Measurement maturity

## B. GA4 property authority

## C. Change-history reconciliation

## D. Runtime analytics integrity

## E. `generate_lead` integrity

## F. Mature `(not set)` daily table

## G. Unassigned / first-user controls

## H. Consent / tag health

## I. Tag Diagnostics

## J. GA4 traffic-quality snapshot

## K. GSC latest-data date

## L. Organic-performance comparison

## M. Query/page breadth

## N. Indexing state

## O. Ambimat → AmbiSecure migration follow-up

## P. Expected-but-not-indexed movement

## Q. Core Web Vitals

## R. New defects, if any

## S. Mutation proof

## T. Recommended next measurement date

End with exactly one of:

`AMBIMAT_GA4_GSC_28AUG = HEALTHY — CONTINUE FREEZE`

`AMBIMAT_GA4_GSC_28AUG = HEALTHY — MORE DATA REQUIRED`

`AMBIMAT_GA4_GSC_28AUG = NEW DEFECT REQUIRES OWNER DECISION`

or

`AMBIMAT_GA4_GSC_28AUG = BLOCKED`

Also state:

`GA4_CHANGE_FREEZE = YES`

unless there is direct evidence sufficient to overturn it.

Proceed autonomously through all safe read-only checks. Do not turn a measurement review into another remediation campaign.

# NOT SUPPLIED — `ambisecure_gsc_7day.md`

**Source purpose:** AmbiSecure SEO — 7-Day GSC Indexing Recovery Check
**Scheduled run ID:** `ambisecure_gsc_7day_20260829`

This prompt was listed as attached in the master scheduling instruction, but its text
was **never delivered** — the message carrying it hit a 50,000-character limit and was
truncated before this prompt appeared. Only the Ambimat and eSIM prompts arrived.

No copy has been stored because no authoritative text exists to store. Reconstructing it
from the master prompt's summary (sections 4–7 for V2X) would fabricate owner instructions
and is refused.

**Effect:** `ambisecure_gsc_7day_20260829` is armed and correctly date-gated, but its preflight will fail with
`Source prompt not installed` and the run will record **BLOCKED** rather than execute.

**To unblock:** drop the exact prompt text at `prompts/ambisecure_gsc_7day.md`, re-run
`install_measurement_queue.sh`, and the manifest will pick up its SHA-256.

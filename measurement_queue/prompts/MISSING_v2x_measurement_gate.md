# NOT SUPPLIED — `v2x_measurement_gate.md`

**Source purpose:** V2X.AMBIMAT.COM — SEO / GSC / GA4 / AI Authority Measurement Gate
**Scheduled run ID:** `v2x_seo_measurement_20260827`

This prompt was listed as attached in the master scheduling instruction, but its text
was **never delivered** — the message carrying it hit a 50,000-character limit and was
truncated before this prompt appeared. Only the Ambimat and eSIM prompts arrived.

No copy has been stored because no authoritative text exists to store. Reconstructing it
from the master prompt's summary (sections 4–7 for V2X) would fabricate owner instructions
and is refused.

**Effect:** `v2x_seo_measurement_20260827` is armed and correctly date-gated, but its preflight will fail with
`Source prompt not installed` and the run will record **BLOCKED** rather than execute.

**To unblock:** drop the exact prompt text at `prompts/v2x_measurement_gate.md`, re-run
`install_measurement_queue.sh`, and the manifest will pick up its SHA-256.

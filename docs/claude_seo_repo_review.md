# `claude-seo` Repository Review (Phase 26)

**Repo:** https://github.com/flyingsaucer88/claude-seo (a fork/mirror of `AgriciDaniel/claude-seo`)
**Reviewed:** 2026-07-01 — shallow clone (source only) at `external/claude-seo/`
**Purpose of review:** decide whether it can run on the Moto G4 Plus (Android 7 / SDK 24 / 32-bit
armeabi-v7a / ~2.95 GB RAM / unrooted / Termux) as our daily site health + hack-indicator + SEO
monitor, or whether we should build a lightweight crawler inspired by it.

## What it actually is

`claude-seo` is **not a standalone crawler**. It is a **Claude Code skill/plugin** (v2.2.0,
"Tier 4 skill") — a marketplace of 25 sub-skills + 18 sub-agents authored as Markdown directives
that are executed *by an AI agent (Claude Code) itself*, plus ~50 Python helper scripts the agent
shells out to. Evidence:

- `.claude-plugin/plugin.json` + `marketplace.json` — it installs into `~/.claude/` as a plugin.
- `skills/*/SKILL.md`, `agents/*.md` — instructions for an LLM, not executable programs.
- `CLAUDE.md`: "Full audits spawn up to 15 subagents simultaneously", "Agents invoked via Agent
  tool, never via Bash." The orchestration layer *is* Claude.

## Runtime / dependency assessment

| Requirement | claude-seo | Moto G4 Plus / Termux | Verdict |
|---|---|---|---|
| Orchestrator | Claude Code (AI agent) + Anthropic API | Not present on phone | ❌ blocker |
| Python | `>=3.10` | Termux Python 3.13.13 | ✅ ok |
| `requests`, `beautifulsoup4` | yes | pip wheels exist | ✅ ok |
| `lxml>=6.1` | yes | needs libxml2/libxslt native build on 32-bit ARM | ⚠️ heavy/fragile |
| `playwright>=1.59` (+ Chromium) | yes (headless render across all agents) | no 32-bit ARM Chromium; ~GB download | ❌ infeasible |
| `weasyprint`, `matplotlib`, `Pillow` | yes (PDF/Excel reports) | native cairo/pango/BLAS builds | ❌ too heavy |
| `google-api-python-client`, `google-auth*`, `google-analytics-data` | yes | needs OAuth + cloud API keys | ❌ out of scope |
| Third-party APIs: DataForSEO, Ahrefs, Moz, Bing WMT, Firecrawl, GSC, GA4, CrUX | yes (paid/keyed) | we want public-crawl-only, no keys | ❌ out of scope |

**Conclusion: cannot be used as-is on the phone.** It requires the Claude Code runtime, an
Anthropic API key, Playwright/Chromium (no 32-bit Android build), and heavy native Python libs
(`lxml`, `weasyprint`, `matplotlib`, `Pillow`) that are impractical to build on Android 7 / 32-bit
Termux. It is also fundamentally an **SEO growth analysis assistant**, not a **defacement /
hack-indicator monitor** — it assumes paid data APIs and a human-in-the-loop AI agent.

## Reusable ideas (design inspiration — we read the source, we do NOT run it)

These scripts are genuinely useful as *design references* for our own lightweight tool:

- **`scripts/parse_html.py`** — clean BeautifulSoup extraction of the exact SEO fields we need:
  `title`, `meta_description`, `meta_robots`, `canonical`, `h1/h2/h3`, internal-vs-external link
  classification by `netloc`, JSON-LD `@graph` flattening, visible-text word count (decomposes
  `script/style/nav/footer/header` first). We reimplement this pattern with `html.parser` (no lxml).
- **`scripts/parasite_risk.py`** — the **advisory, section-level risk** model: regex signal counts
  per page → per-subfolder aggregation → `low/medium/high` with contributing `flags`, explicitly
  documented as *advisory, not proof*. This is exactly the tone we want for spam/injection findings
  (warnings, not "confirmed hack"). We borrow the "count signals, label severity, never assert" idea.
- **`scripts/url_safety.py`** (referenced by parasite_risk via `safe_requests_get`) — SSRF-safe
  fetch: validate URL scheme/host, block private IPs/loopback/metadata. We borrow the principle
  (same-domain-only, http/https-only, skip non-HTML) to keep the crawler polite and safe.
- **`scripts/drift_baseline.py` / `drift_compare.py` / `drift_history.py`** — capture a baseline
  (SQLite) and compare later runs against it with severity rules. This maps directly to our
  requirement "detect sudden suspicious title changes vs last successful run." We implement a
  lightweight JSON-based version (previous `report_latest.json` = baseline) instead of SQLite.
- **`seo-technical` agent** — its checklist (crawlability, indexability, **security headers**)
  confirms the security-header set we check: CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, HSTS.
- **`seo-sitemap`** — confirms sitemap.xml-first discovery, which we adopt.

## Decision

**Build a lightweight, standalone Termux crawler** (`site_monitor/`) in pure Python using only
`requests` + `beautifulsoup4` + `PyYAML` (all pip-installable on Termux without native toolchains,
using `html.parser` so `lxml` is not required). It is *inspired by* claude-seo's HTML parsing,
advisory-risk, drift-baseline, and security-header patterns, but carries **none** of its heavy
runtime (no Claude Code, no Playwright, no cloud APIs, no PDF stack).

Scope guardrails carried over: public GET-only, same-domain crawl, polite delay + timeouts,
bounded page count, **no** vulnerability scanning / admin-path probing / brute force / fuzzing.

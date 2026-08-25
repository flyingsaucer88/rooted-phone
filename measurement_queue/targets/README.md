# Per-run collection targets

`execute.py` will not collect anything for a run without `targets/<run_id>.json`.
That file names the properties, windows and cohorts the run must read — all of
which are defined by the run's own authoritative source prompt. Three of the four
prompts have not been supplied, so their target files deliberately do not exist:
inventing them would be inventing the measurement.

Shape:

```json
{
  "gsc_site": "sc-domain:example.com",
  "ga4_property": "123456789",
  "bing_site": "https://example.com",
  "linkedin_ugc_urn": "urn:li:ugcPost:0000000000000000000",
  "tz_offset_hours": 5.5,
  "inspection_budget": 600,
  "search_analytics_windows": [
    {"tag": "last28_query", "start": "2026-08-01", "end": "2026-08-28",
     "dimensions": ["query"], "row_limit": 25000}
  ],
  "ga4_reports": [
    {"tag": "channels", "dimensions": ["sessionDefaultChannelGroup"],
     "metrics": ["sessions", "engagedSessions"], "ranges": [["2026-08-01", "2026-08-28"]]}
  ],
  "cohorts": [
    {"name": "priority", "urls": ["https://example.com/"]}
  ],
  "live_urls": ["https://example.com/robots.txt"],
  "final_statuses": ["EXAMPLE_VERIFIED", "EXAMPLE_BLOCKED"]
}
```

`ga4_reports` end dates are clamped to the 72-hour maturity boundary by
`collect.mature_window()`; a window cannot report attribution that has not settled.

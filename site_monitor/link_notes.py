#!/usr/bin/env python3
"""Notes about external links whose verification is already known to be limited.

The crawler decides, from live evidence in the current run, whether a link is healthy,
broken, or could not be verified. This module does not participate in that decision. It
only answers a second question about a record the crawler has ALREADY marked unverified:
"has a human looked at this URL before, and what did they find?"

That distinction is the whole point. A note cannot:
  - move a link out of unverified_external,
  - keep a link out of broken_external (404/410/5xx and soft-404 never reach this code),
  - stop a link ageing in the staleness ledger,
  - or make a later successful verification invisible — a URL that answers 200 is not
    recorded as unverified at all, so its note is simply never consulted.

It changes one thing: whether the report reads "unverified — known anti-bot, confirmed
2026-09-09" or "unverified — NEW / unclassified". The second is a finding nobody has
judged yet, and that is worth being able to see at a glance.
"""
from __future__ import annotations

import os

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "config", "external_link_notes.yaml")

# Every class a note may carry. An unrecognised class is dropped rather than trusted: a
# typo must not silently create a category nobody reads.
VALID_CLASSES = ("antibot", "transient", "upstream-failure")


def load_notes(path=DEFAULT_PATH):
    """Return {url: {"class":..., "confirmed":..., "reason":...}}.

    A missing or unreadable registry is not an error — the monitor must run without it,
    annotating nothing. Returning {} makes every unverified link read as NEW, which is the
    safe direction to fail in.
    """
    try:
        import yaml
    except Exception:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:
        return {}
    out = {}
    for entry in (data.get("notes") or []):
        if not isinstance(entry, dict):
            continue
        url = (entry.get("url") or "").strip()
        cls = (entry.get("class") or "").strip()
        if not url or cls not in VALID_CLASSES:
            continue
        out[url] = {"class": cls,
                    "confirmed": str(entry.get("confirmed") or ""),
                    "reason": (entry.get("reason") or "").strip()}
    return out


def annotate(rec, notes):
    """Attach note metadata to one already-unverified record, in place.

    Adds `known` ("antibot"/"transient"/"upstream-failure") when the URL is registered, and
    always adds `known_status` so a reader can separate judged findings from new ones.
    Never touches `status`, `error` or `classification` — those are the live verdict.
    """
    note = notes.get(rec.get("url")) if notes else None
    if note:
        # .get() throughout: annotate() is public and a hand-written note may be partial.
        # A missing field must degrade the annotation, never crash a crawl.
        rec["known"] = note.get("class")
        if note.get("confirmed"):
            rec["known_since"] = note["confirmed"]
        if note.get("reason"):
            rec["known_reason"] = note["reason"]
        rec["known_status"] = "known"
    else:
        rec["known_status"] = "new"
    return rec


def summarise(records):
    """Counts for the report header: how many unverified links are already understood."""
    known = sum(1 for r in records if r.get("known_status") == "known")
    return {"known": known, "new": len(records) - known}

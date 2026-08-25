"""Anthropic Messages API client for the scheduled measurement runs.

Deliberately thin: the phone collects evidence deterministically, then Claude
interprets that evidence against the authoritative source prompt.  Claude gets
no tools and no shell here — it reads what the collectors already wrote.
"""
import json, os, re

URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("MQ_CLAUDE_MODEL", "claude-sonnet-5")
MAX_OUTPUT_TOKENS = int(os.environ.get("MQ_CLAUDE_MAX_OUTPUT", "8000"))
MAX_INPUT_CHARS = int(os.environ.get("MQ_CLAUDE_MAX_INPUT_CHARS", "600000"))  # ~150k tokens

OVERRIDE = """You are interpreting evidence for a scheduled, unattended measurement run
on an Android phone. You have NO tools and NO network access. You cannot act.

Absolute rules:
- Report only what the supplied evidence supports. Never invent, estimate or
  interpolate a metric that is not in the evidence.
- Where evidence is absent, say exactly: NOT AVAILABLE IN STANDALONE API MODE
  or INSUFFICIENT EVIDENCE. Both are acceptable outcomes.
- A number reconstructed from per-URL inspection is labelled
  SOURCE = URL_INSPECTION_RECONSTRUCTION and must never be presented as the
  Search Console Page Indexing UI aggregate.
- This run performed zero mutations and you must not recommend performing one
  as part of the run itself.
- Follow the source prompt's own required final-status wording exactly."""


def build_messages(source_prompt, evidence_summary, raw_index):
    ev = json.dumps(evidence_summary, indent=1, default=str)
    body = ("## AUTHORITATIVE SOURCE PROMPT\n\n%s\n\n"
            "## MACHINE-COLLECTED EVIDENCE (deterministic, read-only)\n\n```json\n%s\n```\n\n"
            "## RAW EVIDENCE FILES ON DISK\n\n%s\n\n"
            "Interpret the evidence against the source prompt and produce the report it asks for."
            % (source_prompt, ev, "\n".join("- " + p for p in raw_index)))
    if len(body) > MAX_INPUT_CHARS:
        raise RuntimeError("evidence exceeds MQ_CLAUDE_MAX_INPUT_CHARS (%d > %d); "
                           "summarise further rather than truncating silently"
                           % (len(body), MAX_INPUT_CHARS))
    return [{"role": "user", "content": body}]


def interpret(guard, api_key, source_prompt, evidence_summary, raw_index,
              model=None, max_tokens=None):
    r = guard.call("anthropic", "messages", "POST", URL,
                   headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                            "content-type": "application/json"},
                   json={"model": model or MODEL,
                         "max_tokens": max_tokens or MAX_OUTPUT_TOKENS,
                         "system": OVERRIDE,
                         "messages": build_messages(source_prompt, evidence_summary, raw_index)},
                   save_as="claude/response.json", timeout=900)
    if r.status_code != 200:
        raise RuntimeError("Anthropic API HTTP %s" % r.status_code)   # body withheld: may echo the key
    d = r.json()
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    return {"text": text, "model": d.get("model"),
            "stop_reason": d.get("stop_reason"), "usage": d.get("usage", {})}


def validate_final_status(text, allowed):
    """The source prompts each mandate one closing token; refuse a report without one."""
    found = [t for t in allowed if re.search(r"(?m)^\W*%s\b" % re.escape(t), text)]
    if len(found) != 1:
        return {"ok": False, "found": found,
                "reason": "expected exactly one of %s, found %d" % (allowed, len(found))}
    if found[0].endswith("VERIFIED") and "INSUFFICIENT EVIDENCE" in text:
        return {"ok": False, "found": found,
                "reason": "claims VERIFIED while also reporting INSUFFICIENT EVIDENCE"}
    return {"ok": True, "final_status": found[0]}


def estimate_cost(input_chars, output_tokens, model=None):
    """Rough pre-flight estimate. Rates are list prices and must be re-checked."""
    rates = {"claude-sonnet-5": (3.0, 15.0), "claude-opus-5": (15.0, 75.0)}
    inp, out = rates.get(model or MODEL, rates["claude-sonnet-5"])
    in_tok = input_chars / 4.0
    return {"model": model or MODEL, "input_tokens_est": int(in_tok),
            "output_tokens_max": output_tokens,
            "usd_est": round(in_tok / 1e6 * inp + output_tokens / 1e6 * out, 3)}


def demo():
    V = validate_final_status
    A = ["ESIM_PHASE3B4_VERIFIED", "ESIM_PHASE3B4_BLOCKED"]
    assert V("blah\nESIM_PHASE3B4_VERIFIED\n", A)["ok"]
    assert V("blah\n`ESIM_PHASE3B4_BLOCKED`\n", A)["final_status"] == "ESIM_PHASE3B4_BLOCKED"
    assert not V("no status here", A)["ok"]
    assert not V("ESIM_PHASE3B4_VERIFIED\nESIM_PHASE3B4_BLOCKED", A)["ok"]      # ambiguous
    assert not V("INSUFFICIENT EVIDENCE for X\nESIM_PHASE3B4_VERIFIED", A)["ok"]  # contradictory
    m = build_messages("SRC", {"a": 1}, ["raw/x.json"])
    assert "AUTHORITATIVE SOURCE PROMPT" in m[0]["content"] and "raw/x.json" in m[0]["content"]
    try:
        build_messages("x" * (MAX_INPUT_CHARS + 10), {}, [])
        raise AssertionError("oversized payload was not refused")
    except RuntimeError:
        pass
    c = estimate_cost(400000, 8000, "claude-sonnet-5")
    assert c["input_tokens_est"] == 100000 and 0.4 < c["usd_est"] < 0.5
    assert "INSUFFICIENT EVIDENCE" in OVERRIDE and "NOT AVAILABLE IN STANDALONE API MODE" in OVERRIDE
    print("claude_runtime demo OK — status validation, size cap, cost estimate")


if __name__ == "__main__":
    demo()

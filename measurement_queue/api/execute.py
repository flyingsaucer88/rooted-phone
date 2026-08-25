"""Standalone measurement executor: collect deterministically, then interpret.

Invoked by run_api_measurement.sh, which the queue calls as MQ_EXECUTOR_CMD.
Raw evidence is written before Claude is called, so every number in the report
traces back to a saved API response.

  execute.py <run_id> <label> <prompt_path> <evidence_dir> <sources>
"""
import hashlib, json, os, subprocess, sys, time

import claude_runtime, collect, creds, gauth, guard

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = os.path.join(os.path.dirname(HERE), "targets")
MANIFEST = os.path.join(os.path.dirname(HERE), "prompts", "MANIFEST.tsv")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def verify_prompt(run_id, path):
    """A run may not proceed on a missing, truncated or unrecorded prompt."""
    base = os.path.basename(path)
    if base.startswith("MISSING_") or not os.path.exists(path):
        return {"ok": False, "reason": "BLOCKED_MISSING_PROMPT: no authoritative prompt stored"}
    digest = sha256(path)
    recorded = None
    if os.path.exists(MANIFEST):
        for line in open(MANIFEST):
            f = line.rstrip("\n").split("\t")
            if len(f) > 4 and f[0] == run_id:
                recorded, status = f[3], (f[-1] if len(f) > 5 else "")
                if "TRUNCATED" in status.upper():
                    return {"ok": False, "sha256": digest,
                            "reason": "BLOCKED_MISSING_PROMPT: stored prompt is truncated"}
                break
    if recorded and recorded != digest:
        return {"ok": False, "sha256": digest,
                "reason": "BLOCKED_MISSING_PROMPT: prompt checksum does not match the manifest"}
    if recorded is None:
        return {"ok": False, "sha256": digest,
                "reason": "BLOCKED_MISSING_PROMPT: prompt is not recorded in MANIFEST.tsv"}
    return {"ok": True, "sha256": digest}


def source_states(sources):
    """Per-source READY / PARTIAL / BLOCKED / NOT_APPLICABLE (degradation rule)."""
    rep = creds.report()
    g = rep["google_sa"]["state"] == "PRESENT"
    out = {}
    for s in sources:
        if s in ("gsc", "ga4"):
            out[s] = "READY" if g else "BLOCKED"
        elif s == "bing":
            out[s] = "READY" if rep["bing"]["state"] == "PRESENT" else "NOT_APPLICABLE"
        elif s == "linkedin":
            out[s] = "READY" if rep["linkedin"]["state"] == "PRESENT" else "NOT_APPLICABLE"
        elif s in ("serp", "ai_overview"):
            out[s] = "NOT_APPLICABLE"
        else:
            out[s] = "NOT_APPLICABLE"
    out["claude"] = "READY" if rep["anthropic"]["state"] == "PRESENT" else "BLOCKED"
    return out


def collect_all(g, targets, states, ev):
    """Deterministic collection driven by the run's targets.json."""
    data = {"collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "timezone": time.strftime("%Z %z"), "sources": {}}
    tok = None
    if states.get("gsc") == "READY" or states.get("ga4") == "READY":
        tok = gauth.GoogleToken(creds.load("google_sa"), g)
        data["google_identity"] = tok.identity

    if states.get("gsc") == "READY" and targets.get("gsc_site"):
        sc = collect.SearchConsole(g, tok)
        site = targets["gsc_site"]
        s = {"site": site, "sites_visible": [e.get("siteUrl") for e in sc.sites().get("siteEntry", [])]}
        s["sitemaps"] = sc.sitemaps(site)
        s["latest_data_date"] = sc.latest_data_date(site)
        for w in targets.get("search_analytics_windows", []):
            s.setdefault("search_analytics", {})[w["tag"]] = sc.search_analytics(
                site, w["start"], w["end"], w.get("dimensions", ["query"]),
                w.get("row_limit", 25000), tag=w["tag"])
        cohorts = [(c["name"], c["urls"]) for c in targets.get("cohorts", [])]
        if cohorts:
            s["indexing_census"] = sc.census(site, cohorts,
                                             targets.get("inspection_budget",
                                                         collect.URL_INSPECTION_DAILY_CAP))
        data["sources"]["gsc"] = s

    if states.get("ga4") == "READY" and targets.get("ga4_property"):
        ga = collect.GA4(g, tok)
        pid = str(targets["ga4_property"])
        mature_end, _ = collect.mature_window(
            tz_offset_hours=targets.get("tz_offset_hours", 5.5))
        a = {"property": pid, "mature_through": mature_end,
             "maturity_rule": "72h; windows ending after this date are not reported as settled",
             "metadata": ga.property_meta(pid), "streams": ga.data_streams(pid),
             "key_events": ga.key_events(pid)}
        for r in targets.get("ga4_reports", []):
            a.setdefault("reports", {})[r["tag"]] = ga.run_report(
                pid, r["dimensions"], r["metrics"],
                [(w[0], min(w[1], mature_end)) for w in r["ranges"]], tag=r["tag"])
        data["sources"]["ga4"] = a

    if states.get("bing") == "READY" and targets.get("bing_site"):
        b = collect.Bing(g, creds.load("bing"))
        site = targets["bing_site"]
        data["sources"]["bing"] = {"sites": b.sites(), "rank_and_traffic": b.rank_and_traffic(site),
                                   "crawl_issues": b.crawl_issues(site), "feeds": b.feeds(site)}

    if states.get("linkedin") == "READY" and targets.get("linkedin_ugc_urn"):
        li = collect.LinkedIn(g, creds.load("linkedin").get("access_token", ""))
        data["sources"]["linkedin"] = li.post_analytics(targets["linkedin_ugc_urn"])

    live = [collect.fetch(g, u, save_as="live/%s.txt" % collect._slug(u))
            for u in targets.get("live_urls", [])]
    for r in live:
        r.pop("text", None)                       # body stays on disk, not in the summary
    if live:
        data["sources"]["live_http"] = live

    for s, st in states.items():
        if st in ("NOT_APPLICABLE", "BLOCKED") and s not in data["sources"]:
            data["sources"][s] = {"state": st,
                                  "value": "NOT AVAILABLE IN STANDALONE API MODE"}
    return data


def main():
    run_id, label, prompt_path, ev, sources = sys.argv[1:6]
    sources = [s for s in sources.split(",") if s]
    os.makedirs(os.path.join(ev, "raw"), exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    result = {"run_id": run_id, "label": label, "started": started,
              "mode": "STANDALONE_PHONE_API_AGENT", "mutations": {
                  "website": 0, "ga4": 0, "gsc": 0, "bing": 0, "linkedin": 0}}

    pv = verify_prompt(run_id, prompt_path)
    result["prompt"] = pv
    states = source_states(sources)
    result["source_states"] = states

    if not pv["ok"]:
        return finish(ev, result, pv["reason"], None)
    if states["claude"] != "READY" or any(states[s] == "BLOCKED" for s in sources if s in states):
        return finish(ev, result, "BLOCKED_CREDENTIAL: " + json.dumps(states), None)

    tpath = os.path.join(TARGETS, run_id + ".json")
    if not os.path.exists(tpath):
        return finish(ev, result, "BLOCKED: no targets/%s.json — the run's properties, "
                                  "cohorts and windows are derived from its authoritative "
                                  "prompt and have not been defined" % run_id, None)
    targets = json.load(open(tpath))

    g = guard.Guard(ev, identity_labels=creds.identities())
    data = collect_all(g, targets, states, ev)
    with open(os.path.join(ev, "evidence.json"), "w") as f:
        json.dump(data, f, indent=1, default=str)

    raw_index = sorted(os.path.relpath(os.path.join(dp, fn), ev)
                       for dp, _, fs in os.walk(os.path.join(ev, "raw")) for fn in fs)
    out = claude_runtime.interpret(g, creds.load("anthropic"), open(prompt_path).read(),
                                   data, raw_index)
    v = claude_runtime.validate_final_status(out["text"], targets.get("final_statuses", []))
    result.update({"claude": {k: out[k] for k in ("model", "stop_reason", "usage")},
                   "final_status_validation": v, "api_calls": g.summary()})
    with open(os.path.join(ev, "REPORT.md"), "w") as f:
        f.write(out["text"])
    return finish(ev, result, None if v["ok"] else "REPORT REJECTED: " + v["reason"],
                  v.get("final_status"))


def finish(ev, result, blocked_reason, final_status):
    result["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    result["status"] = "blocked" if blocked_reason else "completed"
    result["data_collected"] = not blocked_reason
    if blocked_reason:
        result["verdict"] = blocked_reason
        with open(os.path.join(ev, "REPORT.md"), "w") as f:
            f.write("# %s — BLOCKED\n\n%s\n" % (result["label"], blocked_reason))
    else:
        result["verdict"] = final_status
    with open(os.path.join(ev, "result.json"), "w") as f:
        json.dump(result, f, indent=1, default=str)
    subprocess.run("cd %s && find . -type f ! -name SHA256SUMS -print0 | xargs -0 sha256sum "
                   "> SHA256SUMS" % json.dumps(ev), shell=True)
    print(result["verdict"])
    return 1 if blocked_reason else 0


if __name__ == "__main__":
    sys.exit(main())

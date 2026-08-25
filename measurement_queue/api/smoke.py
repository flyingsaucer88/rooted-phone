"""Read-only smoke tests.  Never sends a measurement prompt.

  python3 smoke.py reachability   -- no credentials needed; TLS + unauthenticated probes
  python3 smoke.py full           -- adds authenticated read-only calls for whatever
                                     credentials are actually present
"""
import json, os, socket, ssl, sys, time

import creds, guard, gauth, collect, claude_runtime

HOSTS = ["oauth2.googleapis.com", "analyticsdata.googleapis.com", "analyticsadmin.googleapis.com",
         "searchconsole.googleapis.com", "ssl.bing.com", "api.linkedin.com", "api.anthropic.com"]


def reachability():
    out = []
    ctx = ssl.create_default_context()
    for h in HOSTS:
        t0 = time.time()
        try:
            with socket.create_connection((h, 443), timeout=20) as s:
                with ctx.wrap_socket(s, server_hostname=h) as ss:
                    out.append({"host": h, "tls": ss.version(), "ok": True,
                                "ms": int((time.time() - t0) * 1000)})
        except Exception as e:
            out.append({"host": h, "ok": False, "error": type(e).__name__})
    return out


def full(evidence_dir):
    g = guard.Guard(evidence_dir, identity_labels=creds.identities())
    res = {"credentials": creds.report(), "tests": []}

    def t(name, fn):
        try:
            res["tests"].append({"test": name, "ok": True, "detail": fn()})
        except Exception as e:
            res["tests"].append({"test": name, "ok": False, "error": "%s: %s"
                                 % (type(e).__name__, guard._redact(str(e))[:200])})

    if res["credentials"]["google_sa"]["state"] == "PRESENT":
        tok = gauth.GoogleToken(creds.load("google_sa"), g)
        sc, ga = collect.SearchConsole(g, tok), collect.GA4(g, tok)
        t("google.token_mint", lambda: {"identity": tok.identity, "minted": bool(tok.token())})
        t("gsc.sites.list", lambda: [s.get("siteUrl") for s in sc.sites().get("siteEntry", [])])
        t("ga4.accountSummaries", lambda: [
            {"property": p.get("property"), "displayName": p.get("displayName")}
            for a in ga.account_summaries().get("accountSummaries", [])
            for p in a.get("propertySummaries", [])])
    else:
        res["tests"].append({"test": "google.*", "ok": False, "error": "no service-account credential"})

    if res["credentials"]["bing"]["state"] == "PRESENT":
        b = collect.Bing(g, creds.load("bing"))
        t("bing.GetUserSites", lambda: b.sites().get("d", b.sites()))

    if res["credentials"]["linkedin"]["state"] == "PRESENT":
        li = collect.LinkedIn(g, creds.load("linkedin").get("access_token", ""))
        t("linkedin.userinfo", lambda: {"http": g.call(
            "linkedin", "userinfo", "GET", "https://api.linkedin.com/v2/userinfo",
            headers=li._h(), save_as="linkedin/userinfo.json").status_code})

    if res["credentials"]["anthropic"]["state"] == "PRESENT":
        def tiny():
            r = g.call("anthropic", "messages", "POST", claude_runtime.URL,
                       headers={"x-api-key": creds.load("anthropic"),
                                "anthropic-version": "2023-06-01",
                                "content-type": "application/json"},
                       json={"model": claude_runtime.MODEL, "max_tokens": 16,
                             "messages": [{"role": "user",
                                           "content": "Return exactly API_RUNTIME_OK"}]},
                       save_as="claude/smoke.json", timeout=120)
            txt = "".join(b.get("text", "") for b in r.json().get("content", []))
            return {"http": r.status_code, "reply": txt.strip()[:40],
                    "ok": "API_RUNTIME_OK" in txt}
        t("anthropic.messages", tiny)

    res["guard"] = g.summary()
    return res


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "reachability"
    d = os.environ.get("MQ_SMOKE_DIR", os.path.expanduser("~/scheduled_measurements/_smoke"))
    os.makedirs(d, exist_ok=True)
    out = {"mode": mode, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "reachability": reachability()}
    if mode == "full":
        out["full"] = full(d)
    p = os.path.join(d, "smoke_%s.json" % time.strftime("%Y%m%dT%H%M%S"))
    with open(p, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str)[:4000])
    print("\nwritten: %s" % p)
    bad = [h["host"] for h in out["reachability"] if not h["ok"]]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

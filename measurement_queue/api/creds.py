"""Credential readiness for the scheduled measurement runs.

Reports PRESENT / MISSING / INVALID / EXPIRED and nothing else.  No secret value
is ever returned by status(), written to evidence, or put on a command line.
"""
import json, os, stat, time

DIR = os.path.expanduser(os.environ.get("AMBIMAT_MEASURE_CREDS", "~/.ambimat_measure_creds"))

# name -> (filename, kind)
SPEC = {
    "google_sa":  ("google_service_account.json", "json"),
    "bing":       ("bing_api_key",                "line"),
    "linkedin":   ("linkedin_oauth.json",         "json"),
    "anthropic":  ("anthropic_api_key",           "line"),
}


def path(name):
    return os.path.join(DIR, SPEC[name][0])


def _mode_ok(p, want):
    return stat.S_IMODE(os.stat(p).st_mode) == want


def status(name):
    """Never returns, logs or raises the secret itself."""
    p = path(name)
    if not os.path.isdir(DIR):
        return {"state": "MISSING", "detail": "credential directory absent"}
    if not os.path.exists(p):
        return {"state": "MISSING", "detail": "file absent"}
    if not _mode_ok(DIR, 0o700):
        return {"state": "INVALID", "detail": "credential directory is not mode 700"}
    if not _mode_ok(p, 0o600):
        return {"state": "INVALID", "detail": "credential file is not mode 600"}
    if os.path.getsize(p) == 0:
        return {"state": "INVALID", "detail": "file is empty"}
    kind = SPEC[name][1]
    try:
        if kind == "json":
            d = json.load(open(p))
        else:
            d = open(p).read().strip()
            if not d:
                return {"state": "INVALID", "detail": "no value"}
            return {"state": "PRESENT", "identity": "%s (%d chars)" % (name, len(d))}
    except Exception as e:
        return {"state": "INVALID", "detail": type(e).__name__}

    if name == "google_sa":
        for k in ("client_email", "private_key", "token_uri", "type"):
            if k not in d:
                return {"state": "INVALID", "detail": "missing field %s" % k}
        if d.get("type") != "service_account":
            return {"state": "INVALID", "detail": "not a service_account key"}
        return {"state": "PRESENT", "identity": d["client_email"]}

    if name == "linkedin":
        if "refresh_token" not in d and "access_token" not in d:
            return {"state": "INVALID", "detail": "no token material"}
        exp = d.get("expires_at")
        if exp and time.time() > float(exp) and "refresh_token" not in d:
            return {"state": "EXPIRED", "detail": "access token expired, no refresh token"}
        return {"state": "PRESENT", "identity": d.get("member_label", "linkedin-owner")}
    return {"state": "PRESENT", "identity": name}


def report():
    return {n: status(n) for n in SPEC}


def load(name):
    """Only the collectors call this.  Callers must never log the result."""
    s = status(name)
    if s["state"] != "PRESENT":
        raise RuntimeError("credential %s is %s (%s)" % (name, s["state"], s.get("detail", "")))
    p = path(name)
    return json.load(open(p)) if SPEC[name][1] == "json" else open(p).read().strip()


def identities():
    return {n: status(n).get("identity", "unset") for n in SPEC}


def demo():
    import tempfile
    d = tempfile.mkdtemp()
    global DIR
    DIR = d
    assert status("google_sa")["state"] == "MISSING"
    p = path("google_sa")
    open(p, "w").write(json.dumps({"type": "service_account", "client_email": "x@y.iam.gserviceaccount.com",
                                   "private_key": "k", "token_uri": "t"}))
    os.chmod(d, 0o755); os.chmod(p, 0o600)
    assert status("google_sa")["state"] == "INVALID"          # dir too permissive
    os.chmod(d, 0o700); os.chmod(p, 0o644)
    assert status("google_sa")["state"] == "INVALID"          # file too permissive
    os.chmod(p, 0o600)
    s = status("google_sa")
    assert s["state"] == "PRESENT" and s["identity"] == "x@y.iam.gserviceaccount.com"
    lp = path("linkedin")
    open(lp, "w").write(json.dumps({"access_token": "a", "expires_at": 1}))
    os.chmod(lp, 0o600)
    assert status("linkedin")["state"] == "EXPIRED"
    # status() must never carry secret material
    blob = json.dumps(report())
    assert '"k"' not in blob and '"a"' not in blob
    print("creds demo OK — mode, shape, expiry and no-secret-leak checks pass")


if __name__ == "__main__":
    demo()

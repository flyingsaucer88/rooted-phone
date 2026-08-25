"""Read-only HTTP layer for the scheduled measurement runs.

Every outbound API call in a scheduled gate goes through Guard.call().  An
operation that is not on ALLOW never leaves the process, and every call that
does leave is recorded in the API-call manifest.

The guard keys on (service, operation) and re-checks the method and the URL,
because several read-only analytics operations are POSTs and several mutating
operations are GET-shaped.  Method alone is not a safe signal.
"""
import json, os, re, time, hashlib

VERSION = "1.0"

class MutationGuard(Exception):
    """Raised instead of sending a request that is not provably read-only."""

# (service, operation) -> (method, url regex).  Anything absent is denied.
ALLOW = {
    # --- Google Search Console (searchconsole.googleapis.com serves all of it)
    ("gsc", "sites.list"):
        ("GET",  r"^https://searchconsole\.googleapis\.com/webmasters/v3/sites$"),
    ("gsc", "sites.get"):
        ("GET",  r"^https://searchconsole\.googleapis\.com/webmasters/v3/sites/[^/]+$"),
    ("gsc", "sitemaps.list"):
        ("GET",  r"^https://searchconsole\.googleapis\.com/webmasters/v3/sites/[^/]+/sitemaps$"),
    ("gsc", "sitemaps.get"):
        ("GET",  r"^https://searchconsole\.googleapis\.com/webmasters/v3/sites/[^/]+/sitemaps/[^/]+$"),
    ("gsc", "searchanalytics.query"):
        ("POST", r"^https://searchconsole\.googleapis\.com/webmasters/v3/sites/[^/]+/searchAnalytics/query$"),
    ("gsc", "urlInspection.index.inspect"):
        ("POST", r"^https://searchconsole\.googleapis\.com/v1/urlInspection/index:inspect$"),
    # --- GA4 Data API
    ("ga4", "properties.runReport"):
        ("POST", r"^https://analyticsdata\.googleapis\.com/v1beta/properties/\d+:runReport$"),
    ("ga4", "properties.batchRunReports"):
        ("POST", r"^https://analyticsdata\.googleapis\.com/v1beta/properties/\d+:batchRunReports$"),
    ("ga4", "properties.getMetadata"):
        ("GET",  r"^https://analyticsdata\.googleapis\.com/v1beta/properties/\d+/metadata$"),
    ("ga4", "properties.checkCompatibility"):
        ("POST", r"^https://analyticsdata\.googleapis\.com/v1beta/properties/\d+:checkCompatibility$"),
    # --- GA4 Admin API (read verbs only; no create/patch/delete listed anywhere)
    ("ga4admin", "accountSummaries.list"):
        ("GET",  r"^https://analyticsadmin\.googleapis\.com/v1beta/accountSummaries(\?.*)?$"),
    ("ga4admin", "properties.get"):
        ("GET",  r"^https://analyticsadmin\.googleapis\.com/v1beta/properties/\d+$"),
    ("ga4admin", "properties.list"):
        ("GET",  r"^https://analyticsadmin\.googleapis\.com/v1beta/properties(\?.*)?$"),
    ("ga4admin", "dataStreams.list"):
        ("GET",  r"^https://analyticsadmin\.googleapis\.com/v1beta/properties/\d+/dataStreams(\?.*)?$"),
    ("ga4admin", "dataStreams.get"):
        ("GET",  r"^https://analyticsadmin\.googleapis\.com/v1beta/properties/\d+/dataStreams/\d+$"),
    ("ga4admin", "keyEvents.list"):
        ("GET",  r"^https://analyticsadmin\.googleapis\.com/v1beta/properties/\d+/keyEvents(\?.*)?$"),
    ("ga4admin", "customDimensions.list"):
        ("GET",  r"^https://analyticsadmin\.googleapis\.com/v1beta/properties/\d+/customDimensions(\?.*)?$"),
    ("ga4admin", "changeHistoryEvents.search"):
        ("POST", r"^https://analyticsadmin\.googleapis\.com/v1alpha/accounts/\d+:searchChangeHistoryEvents$"),
    # --- OAuth token mint (not a data endpoint, but it is an outbound call)
    ("google", "oauth2.token"):
        ("POST", r"^https://oauth2\.googleapis\.com/token$"),
    # --- Bing Webmaster Tools, JSON/REST only.  /api.svc/soap and /api.svc/pox
    #     retire 2026-08-31, which is inside our run window; they are not allowed.
    ("bing", "GetUserSites"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetUserSites(\?.*)?$"),
    ("bing", "GetUrlTrafficInfo"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetUrlTrafficInfo(\?.*)?$"),
    ("bing", "GetRankAndTrafficStats"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetRankAndTrafficStats(\?.*)?$"),
    ("bing", "GetQueryStats"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetQueryStats(\?.*)?$"),
    ("bing", "GetPageStats"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetPageStats(\?.*)?$"),
    ("bing", "GetCrawlStats"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetCrawlStats(\?.*)?$"),
    ("bing", "GetCrawlIssues"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetCrawlIssues(\?.*)?$"),
    ("bing", "GetFeeds"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetFeeds(\?.*)?$"),
    ("bing", "GetUrlSubmissionQuota"):
        ("GET",  r"^https://ssl\.bing\.com/webmaster/api\.svc/json/GetUrlSubmissionQuota(\?.*)?$"),
    # --- LinkedIn member post analytics (read finders only)
    ("linkedin", "memberCreatorPostAnalytics"):
        ("GET",  r"^https://api\.linkedin\.com/rest/memberCreatorPostAnalytics(\?.*)?$"),
    ("linkedin", "userinfo"):
        ("GET",  r"^https://api\.linkedin\.com/v2/userinfo$"),
    ("linkedin", "oauth2.refresh"):
        ("POST", r"^https://www\.linkedin\.com/oauth/v2/accessToken$"),
    # --- Anthropic Messages API (the reasoning runtime)
    ("anthropic", "messages"):
        ("POST", r"^https://api\.anthropic\.com/v1/messages$"),
    # --- live site evidence: plain read-only HTTP against our own properties
    ("http", "GET"):  ("GET",  r"^https://[A-Za-z0-9.\-]+/.*$"),
    ("http", "HEAD"): ("HEAD", r"^https://[A-Za-z0-9.\-]+/.*$"),
}

# Named explicitly so the refusal says what was attempted, not just "unknown op".
DENY = {
    ("gsc", "sitemaps.submit"):     "Search Console sitemap submission",
    ("gsc", "sitemaps.delete"):     "Search Console sitemap deletion",
    ("gsc", "sites.add"):           "Search Console property add",
    ("gsc", "sites.delete"):        "Search Console property delete",
    ("gsc", "urlNotifications.publish"): "Google Indexing API submission",
    ("gsc", "requestIndexing"):     "Request Indexing",
    ("gsc", "validateFix"):         "Validate Fix",
    ("bing", "SubmitUrl"):          "Bing URL submission",
    ("bing", "SubmitUrlBatch"):     "Bing batch URL submission",
    ("bing", "SubmitContent"):      "Bing content submission",
    ("bing", "SubmitFeed"):         "Bing sitemap/feed submission",
    ("bing", "AddSite"):            "Bing site add",
    ("bing", "RemoveSite"):         "Bing site removal",
    ("ga4admin", "properties.create"):  "GA4 property create",
    ("ga4admin", "properties.patch"):   "GA4 property update",
    ("ga4admin", "properties.delete"):  "GA4 property delete",
    ("ga4admin", "keyEvents.create"):   "GA4 key-event create",
    ("ga4admin", "keyEvents.patch"):    "GA4 key-event update",
    ("ga4admin", "keyEvents.delete"):   "GA4 key-event delete",
    ("ga4admin", "dataStreams.create"): "GA4 data stream create",
    ("ga4admin", "dataStreams.patch"):  "GA4 data stream update",
    ("linkedin", "ugcPosts.create"):    "LinkedIn post creation",
    ("linkedin", "socialActions.comment"): "LinkedIn comment creation",
    ("linkedin", "socialActions.like"):    "LinkedIn reaction creation",
}

# Last-ditch substring net, checked on every URL regardless of the operation
# name the caller supplied.  Catches a mislabelled call to a mutation path.
FORBIDDEN_URL = re.compile(
    r"(urlNotifications|indexing\.googleapis|SubmitUrl|SubmitContent|SubmitFeed"
    r"|AddSite|RemoveSite|/api\.svc/(soap|pox)|:archive|:delete|/ugcPosts|/socialActions)",
    re.I)


def _redact(s):
    """Strip anything token-shaped out of text that may reach a report."""
    s = re.sub(r"(?i)(key|token|secret|password|assertion|authorization)"
               r"\s*[=:]\s*[\"']?[A-Za-z0-9._\-]{8,}", r"\1=<redacted>", s)
    return re.sub(r"\b(ya29|sk-ant|AIza|Bearer)[A-Za-z0-9._\-]{8,}", "<redacted>", s)


class Guard:
    def __init__(self, evidence_dir, identity_labels=None, session=None):
        self.dir = evidence_dir
        self.raw = os.path.join(evidence_dir, "raw")
        os.makedirs(self.raw, exist_ok=True)
        self.manifest_path = os.path.join(evidence_dir, "api_call_manifest.jsonl")
        self.identity = identity_labels or {}
        self.counts = {}
        self.triggered = []
        self._s = session

    @property
    def s(self):
        # imported lazily so the guard's own checks are testable with no network stack
        if self._s is None:
            import requests
            self._s = requests.Session()
            self._s.headers["User-Agent"] = "ambimat-phone-measure/%s" % VERSION
        return self._s

    def _abort(self, service, op, method, url, why):
        self.triggered.append({"service": service, "operation": op,
                               "method": method, "url": url, "reason": why})
        self._record(service, op, method, url, "WRITE_OR_UNKNOWN", None, None,
                     note="MUTATION_GUARD_TRIGGERED: " + why)
        raise MutationGuard("MUTATION_GUARD_TRIGGERED %s.%s (%s %s): %s"
                            % (service, op, method, _redact(url), why))

    def _record(self, service, op, method, url, cls, status, path, note=""):
        k = "%s.%s" % (service, op)
        self.counts[k] = self.counts.get(k, 0) + 1
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "service": service, "endpoint_category": op, "method": method,
               "url": _redact(url.split("?")[0]),
               "classification": cls, "status_code": status,
               "evidence_path": path, "identity": self.identity.get(service, "unset"),
               "call_index": self.counts[k], "note": note}
        with open(self.manifest_path, "a") as f:
            f.write(json.dumps(row) + "\n")

    def check(self, service, op, method, url):
        """Raise unless (service, op, method, url) is a whitelisted read."""
        key = (service, op)
        if key in DENY:
            self._abort(service, op, method, url,
                        "explicitly denied mutation: " + DENY[key])
        if key not in ALLOW:
            self._abort(service, op, method, url, "operation not on the read-only allowlist")
        want_method, pattern = ALLOW[key]
        if method.upper() != want_method:
            self._abort(service, op, method, url,
                        "method %s does not match allowlisted %s" % (method, want_method))
        if not re.match(pattern, url):
            self._abort(service, op, method, url, "URL does not match the allowlisted path")
        if FORBIDDEN_URL.search(url):
            self._abort(service, op, method, url, "URL matches a forbidden mutation path")
        return True

    def call(self, service, op, method, url, save_as=None, **kw):
        self.check(service, op, method, url)
        r = self.s.request(method, url, timeout=kw.pop("timeout", 60), **kw)
        path = None
        if save_as:
            path = os.path.join(self.raw, save_as)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(r.text)
            path = os.path.relpath(path, self.dir)
        self._record(service, op, method, url, "READ_ONLY", r.status_code, path)
        return r

    def summary(self):
        return {"total_calls": sum(self.counts.values()), "by_operation": dict(self.counts),
                "mutation_guard_triggered": len(self.triggered),
                "all_calls_read_only": not self.triggered}


def demo():
    import tempfile
    g = Guard(tempfile.mkdtemp())
    # allowed shapes pass the check without sending anything
    assert g.check("gsc", "searchanalytics.query", "POST",
                   "https://searchconsole.googleapis.com/webmasters/v3/sites/sc-domain%3Aambimat.com/searchAnalytics/query")
    assert g.check("gsc", "urlInspection.index.inspect", "POST",
                   "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect")
    assert g.check("ga4", "properties.runReport", "POST",
                   "https://analyticsdata.googleapis.com/v1beta/properties/123456:runReport")

    def denied(*a):
        try:
            g.check(*a)
        except MutationGuard as e:
            assert "MUTATION_GUARD_TRIGGERED" in str(e)
            return True
        raise AssertionError("guard let through: %r" % (a,))

    # named mutations
    assert denied("gsc", "sitemaps.submit", "PUT",
                  "https://searchconsole.googleapis.com/webmasters/v3/sites/x/sitemaps/y")
    assert denied("bing", "SubmitUrl", "POST",
                  "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrl")
    assert denied("ga4admin", "keyEvents.patch", "PATCH",
                  "https://analyticsadmin.googleapis.com/v1beta/properties/1/keyEvents/2")
    # unknown operation
    assert denied("gsc", "whatever", "GET", "https://searchconsole.googleapis.com/webmasters/v3/sites")
    # right op, wrong method  (the PUT that would submit a sitemap)
    assert denied("gsc", "sitemaps.list", "PUT",
                  "https://searchconsole.googleapis.com/webmasters/v3/sites/x/sitemaps")
    # right op and method, URL off the allowlisted path
    assert denied("ga4", "properties.runReport", "POST",
                  "https://analyticsadmin.googleapis.com/v1beta/properties/1:runReport")
    # mislabelled call whose URL is a mutation path
    assert denied("http", "GET", "GET",
                  "https://indexing.googleapis.com/v3/urlNotifications:publish")
    # retired Bing transports
    assert denied("bing", "GetUserSites", "GET",
                  "https://ssl.bing.com/webmaster/api.svc/pox/GetUserSites")
    # redaction never leaks a token into the manifest or an exception
    assert "<redacted>" in _redact("Authorization: Bearer ya29.abcdefghijklmnop")
    assert "sk-ant-abcdefgh" not in _redact("x-api-key: sk-ant-abcdefghijklmn")
    s = g.summary()
    assert s["mutation_guard_triggered"] == 8 and s["all_calls_read_only"] is False
    print("guard demo OK — 8 mutation attempts refused, 0 requests sent")


if __name__ == "__main__":
    demo()

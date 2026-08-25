"""Deterministic read-only collectors.  Raw JSON first, interpretation later.

Nothing here decides anything: it fetches, saves the raw response, and returns
parsed data.  Every request goes through guard.Guard, so a mutating endpoint
cannot be reached even by mistake.
"""
import json, os, time, urllib.parse

import gauth

GSC = "https://searchconsole.googleapis.com"
GA4D = "https://analyticsdata.googleapis.com/v1beta"
GA4A = "https://analyticsadmin.googleapis.com/v1beta"
BING = "https://ssl.bing.com/webmaster/api.svc/json"

# Search Console URL Inspection: 2000 URLs/property/day, 600/minute.
URL_INSPECTION_DAILY_CAP = 2000


# --------------------------------------------------------------------------- GSC
class SearchConsole:
    def __init__(self, guard, token):
        self.g, self.t = guard, token
        self._inspected = {}          # url -> result, so a cohort overlap costs one call

    def _site(self, site_url):
        return urllib.parse.quote(site_url, safe="")

    def sites(self):
        return self.g.call("gsc", "sites.list", "GET", GSC + "/webmasters/v3/sites",
                           headers=self.t.headers(), save_as="gsc/sites.json").json()

    def sitemaps(self, site_url):
        return self.g.call("gsc", "sitemaps.list", "GET",
                           "%s/webmasters/v3/sites/%s/sitemaps" % (GSC, self._site(site_url)),
                           headers=self.t.headers(),
                           save_as="gsc/sitemaps_%s.json" % _slug(site_url)).json()

    def search_analytics(self, site_url, start, end, dimensions=("query",),
                         row_limit=25000, tag="", **body):
        payload = {"startDate": start, "endDate": end,
                   "dimensions": list(dimensions), "rowLimit": row_limit}
        payload.update(body)
        return self.g.call("gsc", "searchanalytics.query", "POST",
                           "%s/webmasters/v3/sites/%s/searchAnalytics/query" % (GSC, self._site(site_url)),
                           headers=self.t.headers(), json=payload,
                           save_as="gsc/sa_%s_%s_%s%s.json" % (_slug(site_url), start, end,
                                                               ("_" + tag if tag else ""))).json()

    def latest_data_date(self, site_url, back=10):
        """Search Console lags ~2-3 days; find the newest date with any rows."""
        today = time.strftime("%Y-%m-%d")
        start = time.strftime("%Y-%m-%d", time.localtime(time.time() - back * 86400))
        rows = self.search_analytics(site_url, start, today, dimensions=("date",),
                                     row_limit=100, tag="datedisco").get("rows", [])
        dates = sorted(r["keys"][0] for r in rows)
        return dates[-1] if dates else None

    def inspect(self, url, site_url):
        if url in self._inspected:
            return self._inspected[url]
        if len(self._inspected) >= URL_INSPECTION_DAILY_CAP:
            raise RuntimeError("URL Inspection daily cap reached for this run")
        r = self.g.call("gsc", "urlInspection.index.inspect", "POST",
                        GSC + "/v1/urlInspection/index:inspect",
                        headers=self.t.headers(),
                        json={"inspectionUrl": url, "siteUrl": site_url},
                        save_as="gsc/inspect/%s.json" % _slug(url))
        out = r.json() if r.status_code == 200 else {"_http": r.status_code}
        self._inspected[url] = out
        return out

    def census(self, site_url, cohorts, budget=URL_INSPECTION_DAILY_CAP):
        """Inspect cohorts in priority order until the budget runs out.

        cohorts: list of (name, [urls]) already in the order the source prompt
        cares about.  Returns per-URL classifications plus what was skipped, so
        a truncated census never reads as a complete one.
        """
        out, spent, skipped = [], 0, []
        for name, urls in cohorts:
            for u in urls:
                if u in self._inspected:
                    out.append(dict(classify(self._inspected[u], u), cohort=name, url=u))
                    continue
                if spent >= budget:
                    skipped.append({"cohort": name, "url": u})
                    continue
                spent += 1
                out.append(dict(classify(self.inspect(u, site_url), u), cohort=name, url=u))
        return {"source": "URL_INSPECTION_RECONSTRUCTION",
                "note": "reconstructed from per-URL inspection; NOT the Search Console "
                        "Page Indexing UI aggregate",
                "inspected": spent, "budget": budget,
                "skipped_for_budget": skipped, "urls": out}


def classify(inspection, url):
    """Map one URL Inspection response to a deterministic indexing state."""
    res = (inspection or {}).get("inspectionResult", {})
    idx = res.get("indexStatusResult", {})
    if not idx:
        return {"state": "UNKNOWN", "reason": "no indexStatusResult",
                "source": "URL_INSPECTION_RECONSTRUCTION"}
    cov = (idx.get("coverageState") or "")
    covl = cov.lower()
    robots = idx.get("robotsTxtState") or ""
    indexing = idx.get("indexingState") or ""
    fetch = idx.get("pageFetchState") or ""
    gcanon, ucanon = idx.get("googleCanonical"), idx.get("userCanonical")

    if robots == "DISALLOWED" or indexing == "BLOCKED_BY_ROBOTS_TXT":
        state = "ROBOTS_BLOCKED"
    elif indexing in ("BLOCKED_BY_META_TAG", "BLOCKED_BY_HTTP_HEADER"):
        state = "NOINDEX"
    elif fetch in ("NOT_FOUND", "SOFT_404"):
        state = "NOT_FOUND"
    elif fetch in ("REDIRECT_ERROR",) or "redirect" in covl:
        state = "REDIRECT"
    elif "discovered" in covl and "not indexed" in covl:
        state = "DISCOVERED_NOT_INDEXED"
    elif "crawled" in covl and "not indexed" in covl:
        state = "CRAWLED_NOT_INDEXED"
    elif gcanon and ucanon and gcanon != ucanon:
        state = "CANONICAL_OTHER"
    elif res.get("indexStatusResult", {}).get("verdict") == "PASS" or "indexed" in covl:
        state = "INDEXED"
    else:
        state = "UNKNOWN"
    return {"state": state, "coverage_state": cov, "verdict": idx.get("verdict"),
            "last_crawl": idx.get("lastCrawlTime"), "robots": robots,
            "indexing_state": indexing, "page_fetch": fetch,
            "user_canonical": ucanon, "google_canonical": gcanon,
            "sitemaps": idx.get("sitemap", []), "crawled_as": idx.get("crawledAs"),
            "source": "URL_INSPECTION_RECONSTRUCTION"}


# --------------------------------------------------------------------------- GA4
class GA4:
    def __init__(self, guard, token):
        self.g, self.t = guard, token

    def account_summaries(self):
        return self.g.call("ga4admin", "accountSummaries.list", "GET",
                           GA4A + "/accountSummaries?pageSize=200",
                           headers=self.t.headers(), save_as="ga4/account_summaries.json").json()

    def property_meta(self, pid):
        return self.g.call("ga4admin", "properties.get", "GET", "%s/properties/%s" % (GA4A, pid),
                           headers=self.t.headers(), save_as="ga4/property_%s.json" % pid).json()

    def data_streams(self, pid):
        return self.g.call("ga4admin", "dataStreams.list", "GET",
                           "%s/properties/%s/dataStreams?pageSize=200" % (GA4A, pid),
                           headers=self.t.headers(), save_as="ga4/streams_%s.json" % pid).json()

    def key_events(self, pid):
        return self.g.call("ga4admin", "keyEvents.list", "GET",
                           "%s/properties/%s/keyEvents?pageSize=200" % (GA4A, pid),
                           headers=self.t.headers(), save_as="ga4/keyevents_%s.json" % pid).json()

    def run_report(self, pid, dimensions, metrics, ranges, tag="", **body):
        payload = {"dimensions": [{"name": d} for d in dimensions],
                   "metrics": [{"name": m} for m in metrics],
                   "dateRanges": [{"startDate": a, "endDate": b} for a, b in ranges]}
        payload.update(body)
        return self.g.call("ga4", "properties.runReport", "POST",
                           "%s/properties/%s:runReport" % (GA4D, pid),
                           headers=self.t.headers(), json=payload,
                           save_as="ga4/report_%s_%s.json" % (pid, tag or "x")).json()


def mature_window(now=None, tz_offset_hours=5.5, maturity_hours=72):
    """GA4 (not set) / Unassigned only settle after ~72h; return the safe end date.

    Returns (mature_end_date, cutoff_epoch) in the property's local reckoning so
    a run never reports an attribution number from a window still filling in.
    """
    now = now or time.time()
    cutoff = now - maturity_hours * 3600
    local = time.gmtime(cutoff + tz_offset_hours * 3600)
    return time.strftime("%Y-%m-%d", local), cutoff


# --------------------------------------------------------------------------- Bing
class Bing:
    def __init__(self, guard, api_key):
        self.g, self.k = guard, api_key

    def _get(self, op, **params):
        params["apikey"] = self.k          # query string only; never a process argv
        url = "%s/%s?%s" % (BING, op, urllib.parse.urlencode(params))
        r = self.g.call("bing", op, "GET", url, save_as="bing/%s.json" % op)
        return r.json() if r.status_code == 200 else {"_http": r.status_code, "_body": r.text[:400]}

    def sites(self):
        return self._get("GetUserSites")

    def rank_and_traffic(self, site):
        return self._get("GetRankAndTrafficStats", siteUrl=site)

    def query_stats(self, site):
        return self._get("GetQueryStats", siteUrl=site)

    def crawl_issues(self, site):
        return self._get("GetCrawlIssues", siteUrl=site)

    def feeds(self, site):
        return self._get("GetFeeds", siteUrl=site)


# ----------------------------------------------------------------------- LinkedIn
class LinkedIn:
    """Member post analytics.  Read finders only; see guard.DENY for the rest."""
    API_VERSION = "202508"

    def __init__(self, guard, access_token):
        self.g, self.t = guard, access_token

    def _h(self):
        return {"Authorization": "Bearer " + self.t,
                "LinkedIn-Version": self.API_VERSION,
                "X-Restli-Protocol-Version": "2.0.0"}

    def post_analytics(self, ugc_urn, metrics=None):
        metrics = metrics or ["IMPRESSION", "MEMBERS_REACHED", "REACTION", "COMMENT",
                              "RESHARE", "POST_SAVE", "POST_SEND", "LINK_CLICKS",
                              "FOLLOWER_GAINED_FROM_CONTENT", "PROFILE_VIEW_FROM_CONTENT"]
        q = urllib.parse.urlencode({"q": "entity", "entity": ugc_urn,
                                    "metricTypes": "List(%s)" % ",".join(metrics)}, safe="(),:")
        r = self.g.call("linkedin", "memberCreatorPostAnalytics", "GET",
                        "https://api.linkedin.com/rest/memberCreatorPostAnalytics?" + q,
                        headers=self._h(), save_as="linkedin/post_analytics.json")
        return r.json() if r.status_code == 200 else {"_http": r.status_code, "_body": r.text[:400]}


# --------------------------------------------------------------------------- live
def fetch(guard, url, method="GET", save_as=None):
    r = guard.call("http", method, method, url, save_as=save_as, allow_redirects=False)
    return {"url": url, "status": r.status_code,
            "location": r.headers.get("location"),
            "content_type": r.headers.get("content-type"),
            "elapsed_ms": int(r.elapsed.total_seconds() * 1000),
            "len": len(r.content), "text": r.text if method == "GET" else ""}


def _slug(s):
    return "".join(c if c.isalnum() else "_" for c in s)[:120]


def demo():
    C = classify
    assert C({"inspectionResult": {"indexStatusResult": {
        "verdict": "PASS", "coverageState": "Submitted and indexed",
        "robotsTxtState": "ALLOWED", "indexingState": "INDEXING_ALLOWED"}}}, "u")["state"] == "INDEXED"
    assert C({"inspectionResult": {"indexStatusResult": {
        "verdict": "NEUTRAL", "coverageState": "Crawled - currently not indexed",
        "robotsTxtState": "ALLOWED"}}}, "u")["state"] == "CRAWLED_NOT_INDEXED"
    assert C({"inspectionResult": {"indexStatusResult": {
        "verdict": "NEUTRAL", "coverageState": "Discovered - currently not indexed"}}},
        "u")["state"] == "DISCOVERED_NOT_INDEXED"
    assert C({"inspectionResult": {"indexStatusResult": {
        "coverageState": "Excluded by 'noindex' tag",
        "indexingState": "BLOCKED_BY_META_TAG"}}}, "u")["state"] == "NOINDEX"
    assert C({"inspectionResult": {"indexStatusResult": {
        "robotsTxtState": "DISALLOWED", "coverageState": "Blocked by robots.txt"}}},
        "u")["state"] == "ROBOTS_BLOCKED"
    assert C({"inspectionResult": {"indexStatusResult": {
        "pageFetchState": "NOT_FOUND", "coverageState": "Not found (404)"}}},
        "u")["state"] == "NOT_FOUND"
    assert C({"inspectionResult": {"indexStatusResult": {
        "coverageState": "Page with redirect"}}}, "u")["state"] == "REDIRECT"
    assert C({"inspectionResult": {"indexStatusResult": {
        "verdict": "PASS", "coverageState": "Alternate page with proper canonical tag",
        "userCanonical": "https://a/", "googleCanonical": "https://b/"}}},
        "u")["state"] == "CANONICAL_OTHER"
    assert C({}, "u")["state"] == "UNKNOWN"
    # noindex must win over a stale "indexed" coverage string
    assert C({"inspectionResult": {"indexStatusResult": {
        "coverageState": "Submitted and indexed", "indexingState": "BLOCKED_BY_META_TAG"}}},
        "u")["state"] == "NOINDEX"
    # every result is labelled as a reconstruction, never as the GSC UI aggregate
    assert all(C(x, "u")["source"] == "URL_INSPECTION_RECONSTRUCTION"
               for x in [{}, {"inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}}])
    # 72h maturity: 2026-08-29 01:00 IST -> data only mature through 2026-08-25
    import calendar
    end, _ = mature_window(now=calendar.timegm(time.strptime("2026-08-28 19:30:00",
                                                             "%Y-%m-%d %H:%M:%S")))
    assert end == "2026-08-26", end
    print("collect demo OK — 11 indexing classifications + 72h maturity rule")


if __name__ == "__main__":
    demo()

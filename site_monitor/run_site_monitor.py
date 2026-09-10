#!/data/data/com.termux/files/usr/bin/env python3
"""run_site_monitor.py — lightweight public-crawl site health / hack-indicator / SEO monitor.

Designed to run in Termux on an unrooted Android 7 / 32-bit phone. Pure Python + requests +
beautifulsoup4 + PyYAML. No browser automation, no root, no cloud APIs, no API keys.

It crawls same-domain public pages of the configured sites and reports:
  - broken pages / broken internal & external links (status codes)
  - pages that appear DEFACED (defacement calling-cards in title/H1/text)
  - obvious malicious redirects (homepage/page redirecting to a different registrable domain)
  - potential Japanese-keyword SEO-hack spam
  - potential pharma/casino/adult/loan/crypto/replica SEO spam
  - suspicious injected scripts/iframes/hidden links (esp. to suspicious external domains)
  - basic SEO health (title/description/H1/canonical/robots-meta/word-count/duplicates)
  - basic security headers + TLS certificate expiry
  - title changes vs the previous successful run (drift)

IMPORTANT ACCURACY LIMITATION: this is a public-crawl-based *indicator*. It can only see what is
public at crawl time; it CANNOT prove a hack was attempted in the last 24h. All "suspicious"
findings are advisory WARNINGS, not confirmed compromise. (See README.md.)

Fail-fast / bounded by design (added after a run hung on notification + external link checks):
  - every request uses a (connect, read) timeout tuple
  - each site has a max page count AND a max elapsed-time budget
  - the whole run has a global max elapsed-time budget
  - external-link checking is capped and can be disabled (--no-external-links)
  - progress is printed with flush=True after every page
  - reports are ALWAYS written in a finally block, even on timeout / Ctrl-C / exception
  - phone notifications are detached with /dev/null fds so they can't hang the SSH session

Scope guardrails: GET-only, same-domain, polite delay + timeouts, bounded page count.
NO vulnerability scanning, NO admin-path probing, NO brute force, NO fuzzing.

Usage:
  python run_site_monitor.py --config config/sites.yaml --output-dir ~/site_monitor_reports \
      [--max-pages N] [--global-timeout SEC] [--site-timeout SEC] [--no-external-links] \
      [--open-report false] [--no-notify] [--verbose] [--quiet]
"""
import argparse
import datetime as _dt
import json
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import time
from collections import defaultdict
from urllib.parse import urljoin, urlparse, urldefrag
from urllib import robotparser
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    print("Error: 'requests' is required (pip install requests).", file=sys.stderr)
    sys.exit(1)
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: 'beautifulsoup4' is required (pip install beautifulsoup4).", file=sys.stderr)
    sys.exit(1)
try:
    import yaml
except ImportError:
    print("Error: 'PyYAML' is required (pip install PyYAML).", file=sys.stderr)
    sys.exit(1)

import render_report  # local module (same directory)
import link_notes    # local module: notes about already-unverified external links

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Set by a SIGINT/SIGTERM handler so loops break cleanly and the finally block still writes reports.
_STOP = False


def _handle_stop(signum, frame):
    global _STOP
    _STOP = True
    print(f"\n[monitor] stop signal {signum} received — finishing current step and writing partial report…",
          file=sys.stderr, flush=True)


# Defacement calling-cards. If any appear in a page's TITLE / H1 / visible text we raise an
# ALERT ("page appears defaced"). Kept in code (not just the keyword file) because these are
# higher-confidence than the generic pattern list.
DEFACEMENT_MARKERS = [
    "hacked by", "owned by", "defaced by", "pwned by", "h4ck3d", "hax0r",
    "your site has been hacked", "greetz to", "we are legion",
]

# Markers above that are also ordinary English. In the TITLE/H1 of a page, or on an abnormally
# short one, "owned by" is still damning and still raises the ALERT — that path is unchanged.
# In the body of a normal, long page it is just prose: "Devices owned by infrastructure
# operators", "owned by one engineering organisation". Those produced 10 advisory warnings on
# 2026-09-08, all editorial, none actionable, so the body-only ADVISORY is limited to markers
# that no one writes by accident.
WEAK_DEFACEMENT_MARKERS = {"owned by", "was here"}

# Vocabulary that only a page ABOUT security uses. A defacer writes "Hacked By ShadowTeam" and
# leaves; they do not also write 2,000 words about attack vectors, patching and forensics.
# Used to tell an article that DISCUSSES an attack from a page that IS one — the 2026-09-08
# estate crawl's last editorial false positive was
# /blog/archive/cyber-attacks-in-india-part-1/, a 1,168-word account of Indian bank breaches
# that contains the sentence "…ATM details were hacked by attackers…".
SECURITY_EDITORIAL_TERMS = (
    "vulnerability", "vulnerabilities", "attacker", "attackers", "attack", "breach", "breaches",
    "malware", "ransomware", "phishing", "exploit", "patch", "patched", "cyber", "cybersecurity",
    "security", "encryption", "authentication", "credential", "credentials", "firewall",
    "incident", "forensic", "threat", "mitigation", "compromised", "data leak",
)
# How many distinct such terms make a page credibly editorial.
SECURITY_EDITORIAL_MIN_TERMS = 4
# ...and how much text. A short page with security words is still a defacement candidate.
SECURITY_EDITORIAL_MIN_WORDS = 400

HIDDEN_CSS_HINTS = [
    "display:none", "display: none", "visibility:hidden", "visibility: hidden",
    "font-size:0", "font-size: 0", "text-indent:-9999", "left:-9999", "opacity:0",
]


def now_stamp():
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso():
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def load_keywords(filename):
    path = os.path.join(SCRIPT_DIR, "keywords", filename)
    terms = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    terms.append(line)
    except FileNotFoundError:
        print(f"[monitor] warning: keyword file missing: {path}", file=sys.stderr, flush=True)
    return terms


def reg_domain(host):
    """Approximate registrable domain: last two labels. Good enough for *.ambimat.com."""
    host = (host or "").lower().split(":")[0]
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def norm_url(url):
    """Drop fragment; strip trailing whitespace."""
    return urldefrag(url.strip())[0]


def has_skip_ext(url, skip_exts):
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in skip_exts)


_TERM_RE_CACHE = {}


def host_matches(host, patterns):
    """True if `host` equals one of `patterns` or is a subdomain of one.

    2026-09-08: external_check_skip_hosts was compared with `netloc not in list`, an exact
    match. "facebook.com" therefore did not cover www.facebook.com, and "linkedin.com" did not
    cover in.linkedin.com, so five social links were reported unverified on every run despite
    being explicitly listed as bot-hostile. Suffix matching is anchored at a dot boundary so
    "notfacebook.com" still does NOT match."""
    h = (host or "").lower().strip(".")
    for p in patterns:
        p = p.lower().strip(".")
        if h == p or h.endswith("." + p):
            return True
    return False


def term_in_text(term, text_lower):
    """Match a spam term in already-lowercased text.

    ASCII alphanumeric terms require WORD BOUNDARIES so, e.g., 'cialis' does not match inside
    'specialist' and 'loan' does not match inside 'download' (a real false-positive seen in
    testing). Non-ASCII terms (Japanese/CJK) have no ASCII word boundaries, so they use plain
    substring matching."""
    t = term.lower()
    if t.isascii() and any(ch.isalnum() for ch in t):
        pat = _TERM_RE_CACHE.get(t)
        if pat is None:
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])")
            _TERM_RE_CACHE[t] = pat
        return pat.search(text_lower) is not None
    return t in text_lower


# Statuses that mean "this third party refuses automated clients", not "this link is dead".
# Only ever applied to EXTERNAL links: an internal 401/403 is a real finding about our site.
EXTERNAL_BLOCKING_CODES = {401, 403, 429}

# A 2xx whose FINAL url is the remote's own not-found page. fime.com serves its 404 with
# HTTP 200, so two dead references on ambimat.com passed every status check ever run against
# them; they were only caught by reading where the redirect landed. Matched on the final path
# only, anchored, so a real article at /404-explained/ is not swept up.
_SOFT_404_PATHS = re.compile(r"^/(404|not[-_]?found|page[-_]?not[-_]?found|error[-_]?404)/?$", re.I)

# Error-shape -> classification for a link that could not be verified. The point is that
# "unverified" stops being one undifferentiated bucket: an anti-bot 403 is a permanent
# property of the remote, a connect-refusal from this vantage point says nothing about the
# remote at all, and a read timeout is usually transient. Reporting them identically is what
# made 7 links look like 7 possible dead links.
_UNVERIFIED_SHAPES = (
    ("unverified-tls-chain",
     ("certificate_verify_failed", "unable to get local issuer", "sslcertverificationerror",
      "certificate verify failed")),
    ("unverified-network-blocked",
     ("connecttimeouterror", "connection refused", "econnrefused", "newconnectionerror",
      "name or service not known", "nodename nor servname", "failed to resolve",
      "temporary failure in name resolution", "connect timeout")),
    ("unverified-timeout",
     ("read timed out", "readtimeout", "timed out")),
)


def classify_unverified(status, error):
    """Name the REASON a link could not be verified, instead of leaving every failure as one
    anonymous 'unverified'.

    Deliberately not an allowlist: every value returned here still counts as unverified and
    still ages in the staleness ledger. It only stops an anti-bot 403 and a LAN appliance
    swallowing the connection from reading as 'this link may be dead'."""
    if status in EXTERNAL_BLOCKING_CODES:
        return "unverified-expected-antibot"
    blob = (error or "").lower()
    for label, needles in _UNVERIFIED_SHAPES:
        if any(n in blob for n in needles):
            return label
    return "unverified-unknown"


# An iframe src using one of these executes script or inlines a document instead of loading a
# page. Nothing on this estate legitimately does that, so it is an alert wherever it appears.
_DANGEROUS_SCHEMES = {"javascript", "data", "vbscript", "blob"}


class SiteCrawler:
    def __init__(self, site, crawl_cfg, alerts_cfg, sec_headers, keywords, prev_titles, verbose=False):
        self.name = site["name"]
        self.base_url = site["base_url"].rstrip("/")
        self.start = self.base_url + "/"
        self.host = urlparse(self.base_url).netloc
        self.reg = reg_domain(self.host)
        self.cfg = crawl_cfg
        self.alerts_cfg = alerts_cfg
        self.sec_headers = sec_headers
        self.kw = keywords
        self.prev_titles = prev_titles or {}
        self.verbose = verbose
        self.fail_codes = set(alerts_cfg.get("fail_on_status_codes", []))
        self.susp_domains = [d.lower() for d in alerts_cfg.get("suspicious_external_domains", [])]
        self.ext_skip_hosts = [h.lower() for h in alerts_cfg.get("external_check_skip_hosts", [])]
        self.expected_iframe_hosts = [h.lower() for h in
                                      alerts_cfg.get("expected_iframe_hosts",
                                                     alerts_cfg.get("known_iframe_hosts", []))]
        self.expected_embeds = []   # verified-expected frames: reported, never warned
        # Notes about links whose verification is already known to be limited. Read-only
        # metadata: it annotates records the crawler has already judged unverified and
        # can never change that judgement. See link_notes.py.
        self.link_notes = link_notes.load_notes()
        self.editorial_security_pages = []  # defacement marker judged editorial, with evidence

        # (connect, read) timeout tuple — a hung TCP connect or a slow body can never block forever.
        conn = crawl_cfg.get("connect_timeout_seconds", crawl_cfg.get("request_timeout_seconds", 10))
        read = crawl_cfg.get("read_timeout_seconds", crawl_cfg.get("request_timeout_seconds", 10))
        self.timeout = (conn, read)

        self.session = requests.Session()
        self.session.headers["User-Agent"] = crawl_cfg.get("user_agent", "RootedPhoneSiteMonitor/0.1")

        self.visited = {}            # url -> status (crawled pages)
        self.pages = []              # compact per-page records
        self.alerts = []
        self.warnings = []
        self.internal_links = set()  # discovered same-host link targets
        self.external_links = set()  # discovered off-host link targets
        self.link_sources = {}       # url -> a page it was found on
        self.titles = {}             # url -> title (this run, for drift + dup detection)
        self.descriptions = {}       # url -> description (dup detection)
        self.error = None
        self.timed_out = False
        self.skipped = []            # human-readable notes about capped/skipped work
        self.deadline = None         # monotonic time budget for this site (set in crawl)

    # ---- helpers -------------------------------------------------------
    def _alert(self, atype, detail, url=None):
        self.alerts.append({"type": atype, "detail": detail, "url": url})

    def _warn(self, wtype, detail, url=None):
        self.warnings.append({"type": wtype, "detail": detail, "url": url})

    def _same_host(self, url):
        return urlparse(url).netloc == self.host

    def _out_of_time(self):
        return _STOP or (self.deadline is not None and time.monotonic() > self.deadline)

    # Connection-level failures that are worth exactly one retry: the peer dropped or timed out
    # the socket without answering. These are the shapes a shared-host hiccup takes, and they are
    # indistinguishable at the first attempt from a real outage — the retry is what tells them
    # apart. A page that answers on the second try was never down; a page that is genuinely
    # broken fails both times and still reports. Deliberately does NOT retry an HTTP error
    # response: a 404 or a 500 is an answer, and re-asking cannot change it.
    _TRANSIENT_FETCH_ERRORS = ("connectionreset", "connection reset", "connection aborted",
                               "remotedisconnected", "connection broken", "timed out",
                               "readtimeout", "protocolerror")

    def _get(self, url, allow_redirects=True):
        maxb = self.cfg.get("max_body_bytes", 3000000)
        for attempt in range(2):
            try:
                r = self.session.get(url, timeout=self.timeout,
                                     allow_redirects=allow_redirects, stream=True)
                content = r.raw.read(maxb + 1, decode_content=True)  # bounded read protects memory
                r._content = content[:maxb]
                r._content_consumed = True
                r.close()
                return r
            except Exception as exc:
                blob = f"{type(exc).__name__} {exc}".lower()
                transient = any(t in blob for t in self._TRANSIENT_FETCH_ERRORS)
                if attempt == 1 or not transient:
                    raise
                time.sleep(1.0)

    def _status_only(self, url):
        """HEAD, confirmed with GET on any failure; retried once.
        Returns (status:int|None, error, final_url:str|None).
        A None status means 'could not verify' (connection error/timeout — e.g. transient rate
        limiting during a request burst), NOT necessarily a broken link. Callers treat None as
        UNVERIFIED, distinct from a real failing status code.

        A HEAD failure is never trusted on its own. Plenty of hosts serve GET perfectly well
        while refusing HEAD outright — addtoany.com answers HEAD with 403 and GET with 302,
        which put 15 working share links on the Orders "broken external links" list. GET is
        what a real visitor performs, so it is the only fair verdict. The extra request is
        bounded: it only happens for links that already looked broken."""
        last_err = None
        for attempt in range(2):
            try:
                r = self.session.head(url, timeout=self.timeout, allow_redirects=True)
                if r.status_code in self.fail_codes or r.status_code >= 400:
                    r = self.session.get(url, timeout=self.timeout, allow_redirects=True, stream=True)
                    r.close()
                return r.status_code, None, r.url
            except Exception:
                try:
                    r = self.session.get(url, timeout=self.timeout, allow_redirects=True, stream=True)
                    r.close()
                    return r.status_code, None, r.url
                except Exception as e2:
                    last_err = str(e2)
            if attempt == 0:
                time.sleep(1.0)  # brief backoff, then one retry (rides out transient throttling)
        return None, last_err, None

    # ---- discovery -----------------------------------------------------
    def _load_robots(self):
        rp = robotparser.RobotFileParser()
        try:
            data = self._get(urljoin(self.base_url + "/", "robots.txt"))
            if data.status_code == 200 and data.text:
                rp.parse(data.text.splitlines())
            else:
                return None
        except Exception:
            return None
        return rp

    def _sitemap_urls(self):
        """Fetch /sitemap.xml (and up to 5 child sitemaps) → same-host page URLs."""
        seeds = []
        seen_sitemaps = 0
        queue = [urljoin(self.base_url + "/", "sitemap.xml")]
        tried = set()
        while queue and seen_sitemaps < 6 and not self._out_of_time():
            sm = queue.pop(0)
            if sm in tried:
                continue
            tried.add(sm)
            try:
                r = self._get(sm)
                if r.status_code != 200 or not r.content:
                    continue
                seen_sitemaps += 1
                root = ET.fromstring(r.content)
            except Exception:
                continue
            for loc in root.iter():
                if not loc.tag.endswith("loc") or not (loc.text and loc.text.strip()):
                    continue
                u = norm_url(loc.text.strip())
                if u.lower().endswith(".xml"):
                    queue.append(u)          # nested sitemap
                elif self._same_host(u):
                    seeds.append(u)
        return seeds

    # ---- per-page analysis --------------------------------------------
    def _analyze(self, url, resp):
        html = resp.text or ""
        raw_lower = html.lower()
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            self._warn("parse-error", f"could not parse HTML: {e}", url)
            return

        # Resolve relative links against the URL we actually landed on, not the one we
        # requested. A page that 3xx-redirects to another host serves root-relative hrefs
        # ("/products/") that belong to the *target* host; joining them onto the requested
        # URL invents phantom paths on this site and reports them as broken pages.
        base = getattr(resp, "url", None) or url
        base_tag = soup.find("base", href=True)
        if base_tag:
            base = urljoin(base, base_tag["href"].strip()) or base
        if urlparse(base).netloc != urlparse(url).netloc:
            self._warn("offsite-redirect",
                       f"page redirected off-host to {base}; its links resolve against that host",
                       url)

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None
        description = None
        robots_meta = None
        for meta in soup.find_all("meta"):
            name = (meta.get("name") or "").lower()
            if name == "description":
                description = meta.get("content")
            elif name == "robots":
                robots_meta = meta.get("content")
        canonical_tag = soup.find("link", rel="canonical")
        canonical = canonical_tag.get("href") if canonical_tag else None
        h1s = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]

        self.titles[url] = title
        self.descriptions[url] = description

        internal_here, external_here = [], []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            full = norm_url(urljoin(base, href))
            if urlparse(full).scheme not in ("http", "https"):
                continue
            if self._same_host(full):
                internal_here.append(full)
                self.internal_links.add(full)
            else:
                external_here.append(full)
                self.external_links.add(full)
            self.link_sources.setdefault(full, url)

            style = (a.get("style") or "").replace(" ", "").lower()
            hidden = any(h.replace(" ", "") in style for h in HIDDEN_CSS_HINTS)
            if not hidden:
                for parent in list(a.parents)[:4]:
                    pstyle = (getattr(parent, "get", lambda *_: "")("style") or "").replace(" ", "").lower()
                    if any(h.replace(" ", "") in pstyle for h in HIDDEN_CSS_HINTS):
                        hidden = True
                        break
            if hidden and not self._same_host(full):
                self._warn("hidden-link", f"hidden/off-screen link to external URL: {full}", url)

        for tag_name, attr in (("iframe", "src"), ("script", "src")):
            for t in soup.find_all(tag_name):
                src = (t.get(attr) or "").strip()
                if not src:
                    continue
                # A frame whose src is script or an inline document is never legitimate here.
                # Test the RAW attribute: urljoin() would resolve these into something that
                # looks like an ordinary URL.
                if tag_name == "iframe" and src.split(":", 1)[0].strip().lower() in _DANGEROUS_SCHEMES:
                    self._alert("iframe-dangerous-scheme",
                                f"iframe with a script/data src: {src[:120]}", url)
                    continue
                full = urljoin(base, src)
                host = urlparse(full).netloc.lower()
                if host and host != self.host:
                    if set(host.split(".")) & set(self.susp_domains):
                        self._alert("injected-external",
                                    f"{tag_name} loading from suspicious external domain: {full}", url)
                    elif tag_name == "iframe":
                        # THE IFRAME INVARIANT: only reviewed origins may be framed on this
                        # estate. An expected host is recorded as VERIFIED — it is not
                        # "suspicious" and must not sit in a warning bucket run after run.
                        # Anything else is an ALERT: an unexplained third-party frame is one of
                        # the clearest signatures of an injection, and "nobody approved this
                        # origin" is exactly the condition worth surfacing loudly.
                        if host_matches(host, self.expected_iframe_hosts):
                            self.expected_embeds.append({"url": url, "host": host, "src": full})
                        else:
                            self._alert("unexpected-iframe-host",
                                        "iframe from an origin absent from expected_iframe_hosts: "
                                        f"{full}", url)

        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        visible = soup.get_text(" ", strip=True)
        visible_lower = visible.lower()
        word_count = len(re.findall(r"\b\w+\b", visible))

        # Defacement detection with corroboration to avoid false positives on articles that merely
        # discuss hacking (e.g. a blog post containing "…were hacked by attackers…"). A marker is a
        # high-confidence ALERT only when it appears in the TITLE/H1, or the page is abnormally short
        # (defaced pages are usually stripped to a short message). A marker found only in the body of
        # an otherwise-normal page (real title, substantial text) is downgraded to an advisory warning.
        title_h1 = " ".join(filter(None, [title or "", " ".join(h1s)])).lower()
        marker_hit = next((m for m in DEFACEMENT_MARKERS
                           if m in title_h1 or m in visible_lower[:20000]), None)
        if marker_hit:
            in_prominent = marker_hit in title_h1
            short_page = word_count < 80
            if in_prominent or short_page:
                where = "title/H1" if in_prominent else f"very short page ({word_count} words)"
                self._alert("defacement", f"defacement marker {marker_hit!r} in {where}", url)
            elif marker_hit not in WEAK_DEFACEMENT_MARKERS:
                # Body-only hit on a normal, long page. Before warning, ask whether this reads
                # like security WRITING rather than a takeover. A defaced page is short, loses
                # its real title, and says nothing else; a security article is long, keeps its
                # title (already checked above) and is dense with the vocabulary of the subject.
                sec_terms = {t for t in SECURITY_EDITORIAL_TERMS if term_in_text(t, visible_lower)}
                editorial = (word_count >= SECURITY_EDITORIAL_MIN_WORDS
                             and len(sec_terms) >= SECURITY_EDITORIAL_MIN_TERMS)
                if editorial:
                    self.editorial_security_pages.append({
                        "url": url, "marker": marker_hit, "words": word_count,
                        "security_terms": sorted(sec_terms)[:8],
                    })
                else:
                    self._warn("defacement-marker-in-content",
                               f"defacement-style phrase {marker_hit!r} in page text — title looks "
                               f"normal ({word_count} words) but the page does not read as security "
                               f"writing ({len(sec_terms)} topic terms); verify manually", url)

        # A Japanese keyword hack injects JAPANESE SCRIPT. The romaji/English variants in the
        # keyword file ("betting", "casino", "replica", "loan"…) are ordinary English words that
        # occur in normal writing, so on their own they prove nothing: on 2026-09-08 the only
        # three hits estate-wide were the phrase "without betting on which specific transit chip
        # survives" and two EMV application-identifier listings. Require real corroboration —
        # any CJK term (the actual signature), or at least two DISTINCT English variants
        # co-occurring, which is what an injected spam block looks like and what a sentence of
        # English prose does not.
        jp_hits = [t for t in self.kw["japanese"] if term_in_text(t, visible_lower)][:15]
        cjk_hits = [t for t in jp_hits if not t.isascii()]
        if cjk_hits or len(jp_hits) >= 2:
            self._warn("japanese-spam", f"possible Japanese-SEO-spam terms: {', '.join(jp_hits)}", url)
        spam_hits = [t for t in self.kw["spam"] if term_in_text(t, visible_lower)][:15]
        if spam_hits:
            self._warn("seo-spam", f"potential SEO-spam terms: {', '.join(spam_hits)}", url)
        pat_hits = [p for p in self.kw["patterns"] if p.lower() in raw_lower][:15]
        if pat_hits:
            self._warn("suspicious-pattern", f"suspicious HTML/JS patterns: {', '.join(pat_hits)}", url)

        for ext in external_here:
            ehost = urlparse(ext).netloc.lower()
            if set(ehost.split(".")) & set(self.susp_domains):
                self._warn("suspicious-external-link", f"link to suspicious external domain: {ext}", url)

        self.pages.append({
            "url": url,
            "status": resp.status_code,
            "title": title,
            "description": description,
            "h1_count": len(h1s),
            "canonical": canonical,
            "robots_meta": robots_meta,
            "word_count": word_count,
            "internal_links": len(internal_here),
            "external_links": len(external_here),
        })

    # ---- main crawl ----------------------------------------------------
    def crawl(self, max_pages, global_deadline=None):
        delay = self.cfg.get("delay_between_requests_seconds", 1.0)
        skip_exts = [e.lower() for e in self.cfg.get("skip_extensions", [])]
        respect = self.cfg.get("respect_robots_txt", True)
        site_budget = self.cfg.get("max_seconds_per_site", 180)

        site_start = time.monotonic()
        site_deadline = site_start + site_budget
        self.deadline = min(site_deadline, global_deadline) if global_deadline else site_deadline

        try:
            home = self._get(self.start)
        except Exception as e:
            self.error = f"homepage fetch failed: {e}"
            return
        self.final_url = home.url
        final_host = urlparse(home.url).netloc
        if reg_domain(final_host) != self.reg:
            self._alert("external-redirect",
                        f"homepage redirected to a different domain: {home.url}", self.start)
        elif final_host and final_host != self.host:
            self.host = final_host
            self.base_url = f"{urlparse(home.url).scheme}://{final_host}"
        self.http = {"status": home.status_code,
                     "redirected_to": home.url if home.url != self.start else None}
        self._check_security_headers(home)

        rp = self._load_robots() if respect else None

        queue = [norm_url(home.url)]
        if self.cfg.get("use_sitemap", True):
            for u in self._sitemap_urls():
                queue.append(u)
        enqueued = set(queue)

        while queue and len(self.visited) < max_pages:
            if self._out_of_time():
                self.timed_out = True
                self.skipped.append(f"crawl stopped by time/stop budget after {len(self.visited)} pages")
                break
            url = queue.pop(0)
            if url in self.visited or not self._same_host(url) or has_skip_ext(url, skip_exts):
                continue
            if rp is not None:
                try:
                    if not rp.can_fetch(self.session.headers["User-Agent"], url):
                        continue
                except Exception:
                    pass
            try:
                resp = self._get(url)
            except Exception as e:
                self.visited[url] = None
                self._warn("fetch-error", f"could not fetch: {e}", url)
                if self.verbose:
                    print(f"    [{self.name}] ERR {url} ({e})", flush=True)
                time.sleep(delay)
                continue

            self.visited[url] = resp.status_code
            if resp.status_code in self.fail_codes:
                self._alert("broken-page", f"HTTP {resp.status_code}", url)

            ctype = (resp.headers.get("Content-Type") or "").lower()
            if resp.status_code == 200 and ("html" in ctype or ctype == ""):
                self._analyze(url, resp)
                for link in list(self.internal_links):
                    if (link not in enqueued and self._same_host(link)
                            and not has_skip_ext(link, skip_exts)):
                        enqueued.add(link)
                        queue.append(link)
            if self.verbose:
                print(f"    [{self.name}] #{len(self.visited)} {resp.status_code} {url}", flush=True)
            time.sleep(delay)

    def _check_security_headers(self, resp):
        present, missing = [], []
        low = {k.lower(): v for k, v in resp.headers.items()}
        for h in self.sec_headers:
            (present if h.lower() in low else missing).append(h)
        self.security_headers = {"present": present, "missing": missing}
        if missing:
            self._warn("security-headers",
                       f"missing recommended security headers: {', '.join(missing)}", self.final_url)

    def check_cert(self):
        host = self.host.split(":")[0]
        if urlparse(self.base_url).scheme != "https":
            return {"host": host, "error": "not https"}
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=self.timeout[0]) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
            not_after = cert.get("notAfter")
            exp = _dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=_dt.timezone.utc)
            days = (exp - _dt.datetime.now(_dt.timezone.utc)).days
            warn_days = self.alerts_cfg.get("cert_expiry_warn_days", 21)
            if days < 0:
                self._alert("cert-expired", f"TLS certificate expired {not_after}", self.base_url)
            elif days <= warn_days:
                self._warn("cert-expiry", f"TLS certificate expires in {days} days ({not_after})", self.base_url)
            return {"host": host, "not_after": not_after, "days_to_expiry": days}
        except Exception as e:
            return {"host": host, "error": str(e)}

    def check_links(self, check_external):
        """Bounded broken-link checks: internal links we didn't crawl, then external links.
        Stops early if the site/global time budget is exhausted.

        Returns (broken_internal, broken_external, unverified_internal, unverified_external).
        A link is 'broken' only when it returns a real failing status code (in fail_on_status_codes).
        A link that returns None (connection error/timeout — often transient rate limiting) is
        recorded as UNVERIFIED, never counted as broken."""
        broken_internal, broken_external = [], []
        unverified_internal, unverified_external = [], []
        max_int = self.cfg.get("max_internal_link_checks_per_site", 100)
        max_ext = self.cfg.get("max_external_links_per_site", 20)
        skip_exts = [e.lower() for e in self.cfg.get("skip_extensions", [])]
        delay = min(self.cfg.get("delay_between_requests_seconds", 1.0), 0.5)

        to_check = [u for u in self.internal_links
                    if u not in self.visited and not has_skip_ext(u, skip_exts)][:max_int]
        checked_int = 0
        for u in to_check:
            if self._out_of_time():
                self.skipped.append(f"internal link check stopped early ({checked_int}/{len(to_check)} checked)")
                break
            st, err, final = self._status_only(u)
            checked_int += 1
            rec = {"url": u, "status": st, "found_on": self.link_sources.get(u)}
            if st is None:
                rec["error"] = err
                rec["classification"] = classify_unverified(st, err)
                unverified_internal.append(link_notes.annotate(rec, self.link_notes))
            elif st in self.fail_codes:
                broken_internal.append(rec)
            elif self._is_soft_404(final):
                rec["final_url"] = final
                rec["error"] = f"HTTP {st}, but the redirect landed on the remote's not-found page"
                rec["classification"] = "soft-404"
                broken_internal.append(rec)
            time.sleep(delay)

        if not check_external:
            self.skipped.append("external link checking disabled for this run")
            return broken_internal, broken_external, unverified_internal, unverified_external

        externals = [u for u in self.external_links
                     if not host_matches(urlparse(u).netloc, self.ext_skip_hosts)][:max_ext]
        skipped_hosts = len(self.external_links) - len(externals)
        if skipped_hosts > 0:
            self.skipped.append(f"{skipped_hosts} external links skipped (bot-hostile social/CDN hosts)")
        checked_ext = 0
        for u in externals:
            if self._out_of_time():
                self.skipped.append(f"external link check stopped early ({checked_ext}/{len(externals)} checked)")
                break
            st, err, final = self._status_only(u)
            checked_ext += 1
            rec = {"url": u, "status": st, "found_on": self.link_sources.get(u)}
            if st is None:
                rec["error"] = err
                rec["classification"] = classify_unverified(st, err)
                unverified_external.append(link_notes.annotate(rec, self.link_notes))
            elif st in EXTERNAL_BLOCKING_CODES:
                # A third party refusing an automated client is not a broken link, and it is
                # not something this site can fix. cisa.gov answers our crawler with 403 and
                # a browser with 200; gsma.com, centralbank.ae and slack.com refuse every
                # non-browser client. Reporting those as "broken" buried the one link that
                # genuinely was (an NXP page returning a real 404) under five that were not.
                # 404/410/5xx stay broken: those ARE actionable dead outbound links.
                rec["error"] = f"external host refused an automated request (HTTP {st})"
                rec["classification"] = classify_unverified(st, err)
                unverified_external.append(link_notes.annotate(rec, self.link_notes))
            elif st in self.fail_codes:
                broken_external.append(rec)
            elif self._is_soft_404(final):
                # fime.com answers every dead path with HTTP 200 on /404. Two references on
                # ambimat.com survived every status check this monitor ever ran because of it.
                rec["final_url"] = final
                rec["error"] = f"HTTP {st}, but the redirect landed on the remote's not-found page"
                rec["classification"] = "soft-404"
                broken_external.append(rec)
            time.sleep(delay)
        return broken_internal, broken_external, unverified_internal, unverified_external

    @staticmethod
    def _is_soft_404(final_url):
        """True when a 2xx response finished on the remote's own not-found page."""
        if not final_url:
            return False
        try:
            return bool(_SOFT_404_PATHS.match(urlparse(final_url).path))
        except Exception:
            return False

    @staticmethod
    def _page_identity(page):
        """The canonical identity of a crawled URL.

        Two URLs that declare the same rel=canonical are the same page as far
        as search engines are concerned: `https://x/a` and `https://x/a/`,
        `http://` and `https://` variants, and query-string variants such as
        WooCommerce's `?add-to-cart=15` all collapse here. Grouping by raw URL
        instead reported those as duplicate titles/descriptions, which they are
        not. Falls back to the URL when a page declares no canonical.
        """
        return ((page.get("canonical") or page.get("url") or "").strip().rstrip("/")
                or (page.get("url") or ""))

    def _seo_summary(self):
        missing_title, missing_desc, missing_h1, missing_canon, noindex = [], [], [], [], []
        # title/description -> {canonical identity: first URL seen for it}
        title_map, desc_map = defaultdict(dict), defaultdict(dict)
        for p in self.pages:
            ident = self._page_identity(p)
            if not p["title"]:
                missing_title.append(p["url"])
            else:
                title_map[p["title"].strip().lower()].setdefault(ident, p["url"])
            if not p["description"]:
                missing_desc.append(p["url"])
            else:
                desc_map[p["description"].strip().lower()].setdefault(ident, p["url"])
            if not p["h1_count"]:
                missing_h1.append(p["url"])
            if not p["canonical"]:
                missing_canon.append(p["url"])
            if p["robots_meta"] and "noindex" in p["robots_meta"].lower():
                noindex.append(p["url"])
        # A duplicate needs two DISTINCT canonical identities, not two URLs.
        dup_titles = {k: sorted(v.values()) for k, v in title_map.items() if len(v) > 1}
        dup_desc = {k: sorted(v.values()) for k, v in desc_map.items() if len(v) > 1}
        for url in missing_title:
            self._warn("missing-title", "page has no <title>", url)
        for url in missing_h1:
            self._warn("missing-h1", "page has no H1", url)
        # A noindex page is never shown in search, so a missing description or
        # canonical on one is not an SEO defect. Report both numbers rather than
        # dropping the finding: the indexable count is the actionable one.
        noindex_set = set(noindex)
        return {
            "pages_missing_title": missing_title,
            "pages_missing_description": missing_desc,
            "pages_missing_h1": missing_h1,
            "pages_missing_canonical": missing_canon,
            "noindex_pages": noindex,
            "duplicate_titles": dup_titles,
            "duplicate_descriptions": dup_desc,
            "indexable_missing_description": [u for u in missing_desc if u not in noindex_set],
            "indexable_missing_canonical": [u for u in missing_canon if u not in noindex_set],
        }

    def _title_drift(self):
        drift = []
        for url, new in self.titles.items():
            old = self.prev_titles.get(url)
            if old is not None and old != new:
                drift.append({"url": url, "old": old, "new": new})
                self._warn("title-drift", "title changed since last run", url)
        return drift

    def build(self, check_external=True):
        if self.error:
            return {"name": self.name, "base_url": self.base_url,
                    "reachable": False, "error": self.error,
                    "alerts": [{"type": "unreachable", "detail": self.error, "url": self.base_url}],
                    "warnings": [], "pages_crawled": 0, "timed_out": self.timed_out,
                    "skipped": self.skipped}
        cert = self.check_cert()
        broken_internal, broken_external, unverified_internal, unverified_external = \
            self.check_links(check_external)
        seo = self._seo_summary()
        drift = self._title_drift()
        broken_pages = [{"url": u, "status": st} for u, st in self.visited.items()
                        if st in self.fail_codes]
        return {
            "name": self.name,
            "base_url": self.base_url,
            "final_url": getattr(self, "final_url", self.base_url),
            "reachable": True,
            "error": None,
            "pages_crawled": len(self.pages),
            "timed_out": self.timed_out,
            "skipped": self.skipped,
            "http": self.http,
            "security_headers": self.security_headers,
            "cert": cert,
            "alerts": self.alerts,
            "warnings": self.warnings,
            "seo": seo,
            "broken_pages": broken_pages,
            "broken_internal_links": broken_internal,
            "broken_external_links": broken_external,
            "unverified_internal_links": unverified_internal,
            "unverified_external_links": unverified_external,
            "expected_embeds": self.expected_embeds,
            "editorial_security_pages": self.editorial_security_pages,
            "title_drift": drift,
            "pages": self.pages,
        }


LEDGER_NAME = "unverified_ledger.json"


def load_ledger(output_dir):
    path = os.path.join(output_dir, LEDGER_NAME)
    if os.path.isfile(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def age_unverified_links(site_reports, output_dir, stale_days, today=None):
    """Age every still-unverified link, and warn once it has been unverified too long.

    An anti-bot 403 is correctly not a broken link, but "correctly not broken" must not become
    "trusted forever". A resource that genuinely disappears behind a WAF would otherwise sit in
    the unverified bucket for the rest of time with nobody ever looking at it again.

    So each unverified URL carries the date it FIRST failed to verify, and any URL that has
    been unverified for `stale_days` raises a warning asking for a human check. A URL that
    verifies on any later run is dropped from the ledger, which resets its clock - so this is
    a re-verification schedule, not an allowlist, and it cannot be satisfied by doing nothing.

    Returns the ledger to persist."""
    ledger = load_ledger(output_dir)
    now = today or _dt.datetime.now(_dt.timezone.utc).date()
    seen = set()
    for site in site_reports:
        recs = list(site.get("unverified_external_links", [])) + \
               list(site.get("unverified_internal_links", []))
        for rec in recs:
            url = rec.get("url")
            if not url:
                continue
            seen.add(url)
            entry = ledger.get(url) or {}
            first = entry.get("first_unverified") or now.isoformat()
            entry["first_unverified"] = first
            entry["last_classification"] = rec.get("classification", "unverified-unknown")
            try:
                days = (now - _dt.date.fromisoformat(first)).days
            except Exception:
                days = 0
            entry["days_unverified"] = days
            ledger[url] = entry
            rec["first_unverified"] = first
            rec["days_unverified"] = days
            if days >= stale_days:
                rec["stale"] = True
                site.setdefault("warnings", []).append({
                    "type": "external-link-unverified-too-long",
                    "detail": (f"{url} has been unverified for {days} days "
                               f"({rec.get('classification', 'unverified-unknown')}); "
                               f"confirm by hand that it still resolves"),
                    "url": rec.get("found_on") or url,
                })
    # A link that verified this run leaves the ledger, which restarts its clock.
    for url in [u for u in ledger if u not in seen]:
        del ledger[url]
    return ledger


def save_ledger(ledger, output_dir):
    try:
        with open(os.path.join(output_dir, LEDGER_NAME), "w") as f:
            json.dump(ledger, f, indent=1, sort_keys=True)
    except Exception:
        pass


def load_prev_titles(output_dir):
    """Load url->title map from the previous report_latest.json for drift detection."""
    path = os.path.join(output_dir, "report_latest.json")
    prev = {}
    if os.path.isfile(path):
        try:
            with open(path) as f:
                data = json.load(f)
            for s in data.get("sites", []):
                for p in s.get("pages", []):
                    if p.get("url"):
                        prev[p["url"]] = p.get("title")
        except Exception:
            pass
    return prev


def notify(summary, status, enabled):
    """Fire a phone notification/toast. Detached with /dev/null fds + a new session so the helper
    process can NEVER hold an SSH channel open (this was the original 'hang' root cause)."""
    if not enabled:
        return {"notification": False, "toast": False}
    result = {"notification": False, "toast": False}
    title = "Ambimat Site Monitor"
    devnull = subprocess.DEVNULL
    if shutil.which("termux-notification"):
        try:
            subprocess.run(["termux-notification", "--title", f"{title}: {status}",
                            "--content", summary, "--id", "ambimat_site_monitor"],
                           timeout=20, stdin=devnull, stdout=devnull, stderr=devnull,
                           start_new_session=True)
            result["notification"] = True
        except Exception as e:
            print(f"[monitor] termux-notification failed/skipped: {e}", file=sys.stderr, flush=True)
    if shutil.which("termux-toast"):
        try:
            subprocess.run(["termux-toast", "-s", summary[:120]],
                           timeout=20, stdin=devnull, stdout=devnull, stderr=devnull,
                           start_new_session=True)
            result["toast"] = True
        except Exception as e:
            print(f"[monitor] termux-toast failed/skipped: {e}", file=sys.stderr, flush=True)
    return result


def write_reports(report, output_dir, stamp):
    """Write JSON + MD (timestamped) and latest.{json,md,html}. Safe to call from a finally block."""
    json_path = os.path.join(output_dir, f"report_{stamp}.json")
    md_path_ts = os.path.join(output_dir, f"report_{stamp}.md")
    md = render_report.render_markdown(report)
    html_doc = render_report.render_html(report)
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(md_path_ts, "w") as f:
        f.write(md)
    for name, content in (("report_latest.json", json.dumps(report, indent=2, ensure_ascii=False)),
                          ("report_latest.md", md),
                          ("report_latest.html", html_doc)):
        with open(os.path.join(output_dir, name), "w") as f:
            f.write(content)
    return json_path, md_path_ts


def main():
    ap = argparse.ArgumentParser(description="Ambimat public-crawl site monitor.")
    ap.add_argument("--config", default=os.path.join(SCRIPT_DIR, "config", "sites.yaml"))
    ap.add_argument("--only", default=None,
                    help="crawl ONLY the site with this exact name (one site per process; "
                         "used by run_daily.sh to bound memory on low-RAM devices)")
    ap.add_argument("--output-dir", default=os.path.expanduser("~/site_monitor_reports"))
    ap.add_argument("--max-pages", type=int, default=None, help="override max_pages_per_site")
    ap.add_argument("--global-timeout", type=int, default=None, help="override global_max_seconds")
    ap.add_argument("--site-timeout", type=int, default=None, help="override max_seconds_per_site")
    ap.add_argument("--no-external-links", action="store_true", help="skip external link checks")
    ap.add_argument("--open-report", default="false", help="true/false: open HTML report on phone")
    ap.add_argument("--no-notify", action="store_true", help="skip termux notification/toast")
    ap.add_argument("--verbose", action="store_true", help="print each page as it is crawled")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    if args.only:
        cfg["sites"] = [s for s in cfg.get("sites", []) if s.get("name") == args.only]
        if not cfg["sites"]:
            print(f"[monitor] --only '{args.only}' matched no site in config", file=sys.stderr)
            return 2
    crawl_cfg = dict(cfg.get("crawl", {}))
    alerts_cfg = cfg.get("alerts", {})
    sec_headers = cfg.get("security_headers", [])
    keywords = {
        "japanese": load_keywords("japanese_spam.txt"),
        "spam": load_keywords("suspicious_spam.txt"),
        "patterns": load_keywords("suspicious_patterns.txt"),
    }

    # CLI overrides
    if args.site_timeout is not None:
        crawl_cfg["max_seconds_per_site"] = args.site_timeout
    max_pages = args.max_pages or crawl_cfg.get("max_pages_per_site", 20)
    global_max = args.global_timeout if args.global_timeout is not None else crawl_cfg.get("global_max_seconds", 600)
    check_external = crawl_cfg.get("check_external_links", True) and not args.no_external_links

    os.makedirs(args.output_dir, exist_ok=True)
    prev_titles = load_prev_titles(args.output_dir)
    stamp = now_stamp()
    global_deadline = time.monotonic() + global_max

    site_reports = []
    interrupted = False
    try:
        for site in cfg.get("sites", []):
            if _STOP or time.monotonic() > global_deadline:
                interrupted = True
                print(f"[monitor] global time budget reached — skipping remaining sites.", flush=True)
                site_reports.append({"name": site["name"], "base_url": site["base_url"],
                                     "reachable": False, "error": "skipped: global timeout",
                                     "alerts": [], "warnings": [], "pages_crawled": 0,
                                     "skipped": ["not crawled: global timeout"]})
                continue
            if not args.quiet:
                print(f"[monitor] crawling {site['name']} ({site['base_url']}) …", flush=True)
            c = SiteCrawler(site, crawl_cfg, alerts_cfg, sec_headers, keywords, prev_titles,
                            verbose=args.verbose)
            try:
                c.crawl(max_pages, global_deadline)
            except Exception as e:
                c.error = c.error or f"crawl aborted: {e}"
            report = c.build(check_external=check_external)
            site_reports.append(report)
            if not args.quiet:
                extra = " [TIMED OUT]" if report.get("timed_out") else ""
                print(f"    {render_report._status_word(report)} — "
                      f"{report.get('pages_crawled', 0)} pages, "
                      f"{len(report.get('alerts', []))} alerts, "
                      f"{len(report.get('warnings', []))} warnings{extra}", flush=True)
    except KeyboardInterrupt:
        interrupted = True
        print("[monitor] interrupted — writing partial report.", file=sys.stderr, flush=True)
    finally:
        stale_days = int(alerts_cfg.get("unverified_stale_days", 30))
        save_ledger(age_unverified_links(site_reports, args.output_dir, stale_days),
                    args.output_dir)
        totals = {
            "sites_total": len(cfg.get("sites", [])),
            "sites_reported": len(site_reports),
            "sites_unreachable": sum(1 for s in site_reports if not s.get("reachable")),
            "sites_with_alerts": sum(1 for s in site_reports if s.get("alerts")),
            "sites_ok": sum(1 for s in site_reports
                            if s.get("reachable") and not s.get("alerts") and not s.get("warnings")),
            "sites_timed_out": sum(1 for s in site_reports if s.get("timed_out")),
            "pages_crawled": sum(s.get("pages_crawled", 0) for s in site_reports),
            "broken_pages": sum(len(s.get("broken_pages", [])) for s in site_reports),
            "broken_links": sum(len(s.get("broken_internal_links", []))
                                + len(s.get("broken_external_links", [])) for s in site_reports),
            "unverified_links": sum(len(s.get("unverified_internal_links", []))
                                    + len(s.get("unverified_external_links", [])) for s in site_reports),
            "suspicious_warnings": sum(len(s.get("warnings", [])) for s in site_reports),
            "external_links_checked": check_external,
            "partial": interrupted or _STOP,
        }
        report = {
            "generated_at": now_iso(),
            "generator": "RootedPhoneSiteMonitor/0.1",
            "limitation": render_report.LIMITATION,
            "run_args": {"max_pages": max_pages, "global_timeout": global_max,
                         "site_timeout": crawl_cfg.get("max_seconds_per_site"),
                         "check_external_links": check_external},
            "sites": site_reports,
            "totals": totals,
        }
        json_path, md_path_ts = write_reports(report, args.output_dir, stamp)

        status = render_report.overall_status(report)
        summary = render_report.compact_summary(report)
        print("\n" + "=" * 60, flush=True)
        print(summary, flush=True)
        if totals["partial"]:
            print("[monitor] NOTE: partial run (interrupted/timed out) — results are incomplete.", flush=True)
        print(f"[monitor] json:     {json_path}", flush=True)
        print(f"[monitor] markdown: {md_path_ts}", flush=True)
        print(f"[monitor] latest:   {os.path.join(args.output_dir, 'report_latest.html')}", flush=True)
        print("=" * 60, flush=True)

        notify(summary, status, enabled=not args.no_notify)
        if str(args.open_report).lower() in ("true", "1", "yes"):
            render_report._open_on_phone(os.path.join(args.output_dir, "report_latest.html"))

    return 1 if render_report.overall_status(report) == "ALERT" else 0


if __name__ == "__main__":
    sys.exit(main())

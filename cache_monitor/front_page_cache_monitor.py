#!/usr/bin/env python3
"""ambimat.com front-page cache monitor — STRICTLY INSPECT-AND-REPORT.

This program observes what an ordinary visitor receives from https://ambimat.com/ and,
when (and only when) read-only server access has been explicitly configured, it also
observes the on-disk W3TC page-cache entry. It then classifies the state and writes
evidence.

It has NO capability to change anything, anywhere:

  * The only outbound HTTP it can perform is a plain GET of the configured URL with a
    declared user agent. There is no code path that adds a query string, a cookie, a
    conditional header, or any cache directive to that request.
  * The only remote commands it can execute are the fixed, argument-validated templates
    in SERVER_READ_ONLY_COMMANDS below. A command that is not one of those templates
    cannot be constructed, because the templates are the only strings ever handed to ssh.
  * The only files it writes are its own evidence files, under the evidence directory
    given on the command line.

Finding a problem produces an alert and evidence. It never produces an action.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import http.client
import json
import os
import re
import shlex
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
UTC = _dt.timezone.utc


def _ist() -> _dt.tzinfo:
    """Asia/Kolkata.

    Termux's Python has no bundled tzdata, so zoneinfo may not resolve the key. India
    has observed a fixed UTC+05:30 with no daylight saving since 1945, so the explicit
    offset is exact for every date this job will ever stamp — it is a fallback, never a
    guess, and the job never depends on an ambiguous system default.
    """
    try:
        import zoneinfo

        return zoneinfo.ZoneInfo("Asia/Kolkata")
    except Exception:
        return _dt.timezone(_dt.timedelta(hours=5, minutes=30), "IST")


IST = _ist()

# --------------------------------------------------------------------------------------
# Classifications (exactly the set the operator specified; no recovery/repair states)
# --------------------------------------------------------------------------------------
PASS_HEALTHY = "PASS_HEALTHY_READ_ONLY"
PASS_PUBLIC_ONLY = "PASS_PUBLIC_HEALTHY_SERVER_INSPECTION_UNAVAILABLE"
WARN_OVER_LIFETIME = "WARN_CACHE_FILE_OVER_LIFETIME"
ALERT_STALE = "ALERT_STALE_OR_OBSOLETE_METADATA"
ALERT_MISMATCH = "ALERT_PUBLIC_SERVER_MISMATCH"
FAIL_PUBLIC = "FAIL_PUBLIC_REQUEST"
BLOCKED_SERVER = "BLOCKED_SERVER_INSPECTION"
SKIPPED_DONE = "SKIPPED_ALREADY_COMPLETED"
DEFERRED_LOCK = "DEFERRED_MAINTENANCE_LOCK"
ERROR_INTERNAL = "ERROR_MONITOR_INTERNAL"

# A classification that represents a conclusive observation of the public page. The
# scheduler records the day as done for these, so the catch-up system does not re-inspect
# the same stale page over and over. A stale result is a completed inspection.
CONCLUSIVE = {
    PASS_HEALTHY,
    PASS_PUBLIC_ONLY,
    WARN_OVER_LIFETIME,
    ALERT_STALE,
    ALERT_MISMATCH,
    BLOCKED_SERVER,
}

# Severity order, worst first, used to pick the overall classification.
SEVERITY = [
    ERROR_INTERNAL,
    FAIL_PUBLIC,
    ALERT_STALE,
    ALERT_MISMATCH,
    WARN_OVER_LIFETIME,
    BLOCKED_SERVER,
    PASS_PUBLIC_ONLY,
    PASS_HEALTHY,
]

# Exit codes. 0 means "the inspection completed and was recorded" — including when the
# finding is a stale-cache ALERT, which is a finding, not a job failure (same convention
# as the existing 10:00 site-monitor job). Non-zero means the inspection did not conclude,
# so the watchdog should try again later.
EXIT_OK = 0
EXIT_PUBLIC_FAILED = 4
EXIT_INTERNAL = 5

# Response headers that are never written to evidence.
HEADER_DENYLIST = {
    "set-cookie",
    "cookie",
    "authorization",
    "proxy-authorization",
    "www-authenticate",
    "proxy-authenticate",
    "x-api-key",
}

# Cache-relevant headers reported explicitly (others are still captured, sanitized).
CACHE_HEADERS = [
    "age",
    "cache-control",
    "expires",
    "etag",
    "last-modified",
    "x-cache",
    "x-cache-status",
    "x-w3tc-cache",
    "x-powered-by-w3tc",
    "cf-cache-status",
    "vary",
    "date",
    "server",
]


# --------------------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------------------
def now_utc() -> _dt.datetime:
    return _dt.datetime.now(tz=UTC)


def stamp(dt: _dt.datetime) -> dict:
    return {
        "utc": dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ist": dt.astimezone(IST).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "epoch": int(dt.timestamp()),
    }


def compact_utc(dt: _dt.datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


# --------------------------------------------------------------------------------------
# The single public observation
# --------------------------------------------------------------------------------------
class _RecordingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follows ordinary redirects and records the chain. Adds no headers of its own."""

    def __init__(self, chain: list):
        self.chain = chain

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append({"status": code, "from": req.full_url, "to": newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicObservation:
    def __init__(self):
        self.ok = False
        self.error = None
        self.status = None
        self.final_url = None
        self.redirects = []
        self.elapsed_ms = None
        self.headers = {}
        self.body = b""
        self.retry_after = None


def observe_public(url: str, user_agent: str, timeout: int, max_redirects: int) -> PublicObservation:
    """Perform ONE ordinary, non-bypass public GET.

    The request carries exactly two headers beyond what the stdlib requires for HTTP/1.1:
    a declared User-Agent and a browser-ordinary Accept. It carries no query string, no
    cookie, no conditional validator, no Cache-Control, no Pragma, and no purge/refresh
    header. It is the minimum request needed to see what a visitor sees.
    """
    obs = PublicObservation()
    chain: list = []
    handler = _RecordingRedirectHandler(chain)
    handler.max_redirections = max_redirects
    opener = urllib.request.build_opener(
        handler,
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    # Deliberately empty: no cookie processor is installed, so no cookie can be sent.
    opener.addheaders = []

    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", user_agent)
    req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

    started = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as resp:
            obs.status = resp.status
            obs.final_url = resp.url
            obs.headers = _collect_headers(resp.headers)
            obs.body = resp.read()
            obs.ok = True
    except urllib.error.HTTPError as exc:  # a real HTTP response with a >=400 status
        obs.status = exc.code
        obs.final_url = exc.url
        obs.headers = _collect_headers(exc.headers)
        try:
            obs.body = exc.read()
        except Exception:  # pragma: no cover - body is optional for error responses
            obs.body = b""
        obs.retry_after = obs.headers.get("retry-after")
        obs.ok = True  # an HTTP response was received; whether it is usable is decided later
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, http.client.HTTPException, OSError) as exc:
        obs.error = f"{type(exc).__name__}: {exc}"
    finally:
        obs.elapsed_ms = int((time.monotonic() - started) * 1000)
    obs.redirects = chain
    return obs


def _collect_headers(msg) -> dict:
    out = {}
    for key, value in msg.items():
        k = key.lower()
        if k in HEADER_DENYLIST:
            continue
        out[k] = value.strip() if isinstance(value, str) else value
    return out


def fetch_with_bounded_retries(cfg: dict, sleeper=None, fetcher=None) -> tuple:
    """Retry ONLY transport-level failures that prevented an inspection.

    A retry is never used to wait for content to change, to trigger anything on the
    server, or to re-check a page that already answered. As soon as a usable response is
    in hand the loop stops, permanently.
    """
    # Resolved at call time, not at definition time, so a test can substitute a fixture
    # reader and be certain no real request is made.
    fetcher = fetcher or observe_public
    sleeper = sleeper or time.sleep

    rt = cfg.get("transport_retry", {})
    max_attempts = int(rt.get("max_attempts", 3))
    backoff = list(rt.get("backoff_seconds", [20, 45]))
    cap = int(rt.get("retry_after_cap_seconds", 120))

    history = []
    obs = None
    for attempt in range(1, max_attempts + 1):
        obs = fetcher(
            cfg["url"],
            cfg["user_agent"],
            int(cfg.get("request_timeout_seconds", 45)),
            int(cfg.get("max_redirects", 5)),
        )
        entry = {
            "attempt": attempt,
            "at_utc": stamp(now_utc())["utc"],
            "status": obs.status,
            "error": obs.error,
            "elapsed_ms": obs.elapsed_ms,
        }

        if obs.error is not None:
            entry["outcome"] = "transport_failure"
            reason = "transport"
        elif obs.status == 429:
            entry["outcome"] = "http_429"
            reason = "429"
        elif obs.status is not None and 500 <= obs.status <= 599:
            entry["outcome"] = "http_5xx"
            reason = "5xx"
        else:
            entry["outcome"] = "response_captured"
            history.append(entry)
            break

        if attempt >= max_attempts:
            entry["retry_decision"] = "exhausted"
            history.append(entry)
            break

        if reason == "429" and obs.retry_after:
            delay = _parse_retry_after(obs.retry_after, cap)
            entry["retry_after_header"] = obs.retry_after
        else:
            delay = backoff[min(attempt - 1, len(backoff) - 1)] if backoff else 20
        delay = min(int(delay), cap)
        entry["retry_decision"] = f"retry_in_{delay}s"
        history.append(entry)
        sleeper(delay)

    return obs, history


def _parse_retry_after(value: str, cap: int) -> int:
    value = (value or "").strip()
    if value.isdigit():
        return min(int(value), cap)
    try:
        when = _dt.datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
        return max(0, min(int((when - now_utc()).total_seconds()), cap))
    except ValueError:
        return min(30, cap)


# --------------------------------------------------------------------------------------
# Metadata extraction
# --------------------------------------------------------------------------------------
_CANONICAL_RE = re.compile(
    rb"""<link[^>]+rel=["']canonical["'][^>]*>""", re.IGNORECASE)
_HREF_RE = re.compile(rb"""href=["']([^"']+)["']""", re.IGNORECASE)
_CONTENT_RE = re.compile(rb"""content=["']([^"']*)["']""", re.IGNORECASE)
_CONTENT_URL_RE = re.compile(rb'"contentUrl"\s*:\s*"([^"]+)"')


def _meta(body: bytes, attr: str, name: str):
    pattern = re.compile(
        rb"<meta[^>]+" + attr.encode() + rb"""=["']""" + re.escape(name.encode()) + rb"""["'][^>]*>""",
        re.IGNORECASE,
    )
    m = pattern.search(body)
    if not m:
        return None
    c = _CONTENT_RE.search(m.group(0))
    return c.group(1).decode("utf-8", "replace") if c else None


def extract_metadata(body: bytes, cfg: dict) -> dict:
    canonical = None
    m = _CANONICAL_RE.search(body)
    if m:
        h = _HREF_RE.search(m.group(0))
        if h:
            canonical = h.group(1).decode("utf-8", "replace")

    ignore = cfg.get("schema_logo_path_segments_to_ignore", [])
    # Schema graphs are JSON, so their URLs arrive with escaped solidi (https:\/\/…).
    schema_urls = [
        u.decode("utf-8", "replace").replace("\\/", "/")
        for u in _CONTENT_URL_RE.findall(body)
    ]
    primary_schema = None
    for u in schema_urls:
        if not any(seg in u for seg in ignore):
            primary_schema = u
            break

    return {
        "canonical": canonical,
        "og_image": _meta(body, "property", "og:image"),
        "og_image_width": _meta(body, "property", "og:image:width"),
        "og_image_height": _meta(body, "property", "og:image:height"),
        "twitter_image": _meta(body, "name", "twitter:image"),
        "twitter_card": _meta(body, "name", "twitter:card"),
        "schema_image": primary_schema,
        "schema_content_urls": schema_urls,
    }


def evaluate_metadata(meta: dict, cfg: dict) -> dict:
    """Compare what was served against the mapping. Reports; decides nothing else."""
    governed = cfg["governed_image"]["path_segment"]
    obsolete = {o["path_segment"]: o for o in cfg.get("obsolete_images", [])}
    checks = cfg.get("checks", {})

    obsolete_hits = []
    missing_expected = []
    unexpected = []

    def classify_field(field: str, value):
        spec = checks.get(field, {})
        if value is None:
            if spec.get("required"):
                missing_expected.append({"field": field, "reason": "absent"})
            return "absent"
        for seg, info in obsolete.items():
            if seg in value:
                obsolete_hits.append(
                    {
                        "field": field,
                        "value": value,
                        "matched_path_segment": seg,
                        "obsolete_attachment_id": info.get("attachment_id"),
                    }
                )
                return "obsolete"
        if spec.get("must_be") == "governed_image":
            if governed in value:
                return "governed"
            unexpected.append({"field": field, "value": value, "reason": "not_the_governed_image"})
            if spec.get("required"):
                missing_expected.append({"field": field, "reason": "not_the_governed_image"})
            return "unrecognised"
        return "present"

    field_states = {
        "og_image": classify_field("og_image", meta.get("og_image")),
        "twitter_image": classify_field("twitter_image", meta.get("twitter_image")),
        "schema_image": classify_field("schema_image", meta.get("schema_image")),
    }

    expected_canonical = cfg.get("expected_canonical")
    canonical_ok = meta.get("canonical") == expected_canonical
    field_states["canonical"] = "ok" if canonical_ok else "mismatch_or_absent"
    if not canonical_ok and checks.get("canonical", {}).get("required"):
        missing_expected.append(
            {
                "field": "canonical",
                "reason": "absent" if meta.get("canonical") is None else "mismatch",
                "observed": meta.get("canonical"),
                "expected": expected_canonical,
            }
        )

    return {
        "field_states": field_states,
        "obsolete_detected": bool(obsolete_hits),
        "obsolete_hits": obsolete_hits,
        "expected_metadata_missing": missing_expected,
        "unexpected_values": unexpected,
        "governed_path_segment": governed,
    }


# --------------------------------------------------------------------------------------
# Optional server-side READ-ONLY inspection
# --------------------------------------------------------------------------------------
# The complete set of remote commands this program can issue. Each entry is a fixed
# template; the only substitution is a path or a WordPress option name, both quoted and
# both validated before use. There is no template here that writes, deletes, renames,
# truncates, changes a mode, runs a cron event, or manages a cache — and no code path
# that builds a remote command any other way.
SERVER_READ_ONLY_COMMANDS = {
    "wp_option": "wp --path={path} --skip-plugins --skip-themes option get {option}",
    "wp_cron_list": "wp --path={path} --skip-plugins --skip-themes cron event list --format=json --fields=hook,next_run_gmt",
    "test_exists": "test -e {path} && echo exists || echo absent",
    "test_regular": "test -f {path} && echo regular || echo not_regular",
    "test_symlink": "test -L {path} && echo symlink || echo not_symlink",
    "realpath": "realpath {path}",
    "readlink": "readlink -f {path}",
    "stat": "stat -c '%U|%G|%a|%Y|%s|%F' {path}",
    "sha256": "sha256sum {path}",
}

_SAFE_PATH_RE = re.compile(r"^/[A-Za-z0-9._/\-]+$")
_SAFE_OPTION_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class ServerInspectionUnavailable(Exception):
    """Raised when server inspection is not configured or cannot be proven read-only."""


class ServerInspectionBlocked(Exception):
    """Raised when configured server inspection failed on auth, permissions, or paths."""


def _validated_path(path: str) -> str:
    if not _SAFE_PATH_RE.match(path or "") or ".." in path:
        raise ServerInspectionBlocked(f"path failed validation: {path!r}")
    return shlex.quote(path)


def _validated_option(option: str) -> str:
    if not _SAFE_OPTION_RE.match(option or ""):
        raise ServerInspectionBlocked(f"option name failed validation: {option!r}")
    return shlex.quote(option)


class SshReader:
    """Runs ONLY the templates above, over ssh, in batch mode."""

    def __init__(self, sc: dict):
        self.host = sc["host"]
        self.user = sc["user"]
        self.port = int(sc.get("port", 22))
        self.key = os.path.expanduser(sc["identity_file"])
        self.wp_path = sc["wp_path"]
        self.timeout = int(sc.get("timeout_seconds", 30))
        self.executed: list = []

    def run(self, template_key: str, **kwargs) -> str:
        template = SERVER_READ_ONLY_COMMANDS[template_key]  # KeyError = programmer error
        subs = {}
        if "path" in kwargs:
            subs["path"] = _validated_path(kwargs["path"])
        if "option" in kwargs:
            subs["option"] = _validated_option(kwargs["option"])
        remote = template.format(**subs)
        argv = [
            "ssh",
            "-i", self.key,
            "-p", str(self.port),
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"ConnectTimeout={min(self.timeout, 20)}",
            f"{self.user}@{self.host}",
            "--",
            remote,
        ]
        self.executed.append({"template": template_key, "remote_command": remote})
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=self.timeout + 10
        )
        if proc.returncode != 0 and template_key not in ("test_exists", "test_regular", "test_symlink"):
            err = (proc.stderr or "").strip().splitlines()
            tail = err[-1] if err else f"rc={proc.returncode}"
            if any(t in tail.lower() for t in ("permission denied", "publickey", "denied", "authentication")):
                raise ServerInspectionBlocked(f"{template_key}: {tail}")
            raise ServerInspectionBlocked(f"{template_key}: {tail}")
        return (proc.stdout or "").strip()


def load_server_config(path: str):
    if not path or not os.path.exists(path):
        raise ServerInspectionUnavailable("no server-inspection configuration is installed")
    with open(path, "r", encoding="utf-8") as fh:
        sc = json.load(fh)
    if not sc.get("enabled"):
        raise ServerInspectionUnavailable("server inspection is present but not enabled")
    for field in ("host", "user", "identity_file", "wp_path"):
        if not sc.get(field):
            raise ServerInspectionUnavailable(f"server-inspection configuration is missing {field!r}")
    if not os.path.exists(os.path.expanduser(sc["identity_file"])):
        raise ServerInspectionUnavailable("the configured ssh identity file is not present on this device")
    return sc


def inspect_server(sc: dict, cfg: dict, public_sha256: str, reader_cls=SshReader) -> dict:
    reader = reader_cls(sc)
    out = {
        "available": True,
        "commands_executed": [],
        "siteurl": None,
        "home": None,
        "cache_engine": "not_inspected (outside the proven read-only command set)",
        "cache_path": None,
        "exists": None,
        "is_regular_file": None,
        "is_symlink": None,
        "resolved_path": None,
        "path_within_expected_cache_root": None,
        "owner": None,
        "group": None,
        "mode": None,
        "mtime_utc": None,
        "age_seconds": None,
        "size_bytes": None,
        "sha256": None,
        "sha256_matches_public_body": None,
        "configured_lifetime_seconds": cfg.get("pgcache_lifetime_seconds"),
        "over_lifetime": None,
        "w3_pgcache_cleanup_next_run_gmt": None,
        "cleanup_overdue": None,
        "notes": [],
    }

    wp_path = sc["wp_path"]
    out["siteurl"] = reader.run("wp_option", path=wp_path, option="siteurl")
    out["home"] = reader.run("wp_option", path=wp_path, option="home")

    host = re.sub(r"^https?://", "", out["home"] or "").strip("/") or "ambimat.com"
    cache_path = os.path.join(wp_path, cfg["cache_path_template"].format(host=host))
    out["cache_path"] = cache_path

    out["exists"] = reader.run("test_exists", path=cache_path) == "exists"
    if not out["exists"]:
        out["notes"].append("no cache entry at the resolved path at inspection time")
        _read_cron(reader, sc, cfg, out)
        out["commands_executed"] = reader.executed
        return out

    out["is_regular_file"] = reader.run("test_regular", path=cache_path) == "regular"
    out["is_symlink"] = reader.run("test_symlink", path=cache_path) == "symlink"
    resolved = reader.run("realpath", path=cache_path)
    out["resolved_path"] = resolved

    expected_root = os.path.join(wp_path, "wp-content/cache/page_enhanced")
    within = bool(resolved) and (resolved == expected_root or resolved.startswith(expected_root + "/"))
    out["path_within_expected_cache_root"] = within
    if not within or out["is_symlink"] or not out["is_regular_file"]:
        out["notes"].append(
            "UNSAFE OR UNEXPECTED CACHE PATH — reported only. No hashing, no further action, "
            "no change of any kind was performed."
        )
        _read_cron(reader, sc, cfg, out)
        out["commands_executed"] = reader.executed
        return out

    st = reader.run("stat", path=resolved)
    parts = st.split("|")
    if len(parts) == 6:
        out["owner"], out["group"], out["mode"] = parts[0], parts[1], parts[2]
        mtime = int(parts[3])
        out["size_bytes"] = int(parts[4])
        out["mtime_utc"] = _dt.datetime.fromtimestamp(mtime, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        out["age_seconds"] = max(0, int(now_utc().timestamp()) - mtime)
        lifetime = cfg.get("pgcache_lifetime_seconds")
        if lifetime:
            out["over_lifetime"] = out["age_seconds"] > int(lifetime)

    digest = reader.run("sha256", path=resolved).split()
    if digest:
        out["sha256"] = digest[0]
        out["sha256_matches_public_body"] = (digest[0] == public_sha256)

    _read_cron(reader, sc, cfg, out)
    out["commands_executed"] = reader.executed
    return out


def _read_cron(reader, sc, cfg, out) -> None:
    """Read the scheduled time of the W3TC page-cache cleanup event. Listing only."""
    try:
        raw = reader.run("wp_cron_list", path=sc["wp_path"])
        events = json.loads(raw) if raw else []
        for ev in events:
            if ev.get("hook") == "w3_pgcache_cleanup":
                out["w3_pgcache_cleanup_next_run_gmt"] = ev.get("next_run_gmt")
                try:
                    nxt = _dt.datetime.strptime(ev["next_run_gmt"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                    out["cleanup_overdue"] = nxt < now_utc()
                except (KeyError, ValueError):
                    out["cleanup_overdue"] = None
                break
    except (ServerInspectionBlocked, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        out["notes"].append(f"cron event listing unavailable: {exc}")


# --------------------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------------------
def classify(public_ok: bool, meta_eval: dict, server: dict, server_state: str) -> tuple:
    """Return (overall_classification, reasons)."""
    reasons = []
    candidates = []

    if not public_ok:
        return FAIL_PUBLIC, ["the public request could not be completed after bounded transport retries"]

    if meta_eval["obsolete_detected"]:
        candidates.append(ALERT_STALE)
        for hit in meta_eval["obsolete_hits"]:
            reasons.append(
                f"{hit['field']} serves the known obsolete image "
                f"{hit['matched_path_segment']} (attachment {hit['obsolete_attachment_id']})"
            )
    if meta_eval["expected_metadata_missing"]:
        candidates.append(ALERT_STALE)
        for miss in meta_eval["expected_metadata_missing"]:
            reasons.append(f"expected {miss['field']} is {miss['reason']}")

    if server_state == "available":
        if server.get("sha256_matches_public_body") is False:
            candidates.append(ALERT_MISMATCH)
            reasons.append(
                "the public response body and the on-disk cache entry have different SHA-256 digests"
            )
        if server.get("over_lifetime") or server.get("cleanup_overdue"):
            candidates.append(WARN_OVER_LIFETIME)
            if server.get("over_lifetime"):
                reasons.append(
                    f"cache entry age {server.get('age_seconds')}s exceeds the configured lifetime "
                    f"{server.get('configured_lifetime_seconds')}s"
                )
            if server.get("cleanup_overdue"):
                reasons.append("the w3_pgcache_cleanup event is scheduled in the past (cleanup appears overdue)")
        if server.get("path_within_expected_cache_root") is False:
            candidates.append(WARN_OVER_LIFETIME)
            reasons.append("the resolved cache path lies outside the expected cache root — reported only")
    elif server_state == "blocked":
        candidates.append(BLOCKED_SERVER)
        reasons.append(server.get("blocked_reason", "server inspection was blocked"))
    else:  # unavailable / skipped
        candidates.append(PASS_PUBLIC_ONLY)
        reasons.append(server.get("unavailable_reason", "server inspection unavailable"))

    if not candidates:
        candidates.append(PASS_HEALTHY)
    if server_state == "available" and candidates == [PASS_HEALTHY]:
        reasons.append("public evidence and read-only server evidence are consistent")

    overall = min(candidates, key=lambda c: SEVERITY.index(c))
    if overall == PASS_PUBLIC_ONLY and not reasons:
        reasons.append("public evidence appears healthy; server inspection unavailable")
    return overall, reasons


# --------------------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------------------
def sanitize_headers(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in HEADER_DENYLIST}


def write_evidence(evidence_dir: str, result: dict, obs, meta: dict, retries: list) -> None:
    os.makedirs(evidence_dir, mode=0o700, exist_ok=True)

    def w(name, text):
        p = os.path.join(evidence_dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(p, 0o600)

    w("result.json", json.dumps(result, indent=2, sort_keys=True) + "\n")

    if obs is not None and obs.headers:
        lines = [f"HTTP {obs.status}"]
        lines += [f"{k}: {v}" for k, v in sorted(sanitize_headers(obs.headers).items())]
        lines.append("")
        lines.append("(Sanitized: cookie, authorization and authenticate headers are never recorded.)")
        w("response-headers.txt", "\n".join(lines) + "\n")

    w("parsed-metadata.txt", _metadata_text(meta, result))
    w("request-procedure.txt", _procedure_text(result))
    w("retry-history.txt", json.dumps(retries, indent=2) + "\n")
    w("scheduler.txt", _scheduler_text(result))
    w("server-inspection.txt", _server_text(result))
    w("SUMMARY.txt", human_summary(result))
    w("notification.txt", notification_text(result) + "\n")

    _write_manifest(evidence_dir, "EVIDENCE.sha256")


def _metadata_text(meta: dict, result: dict) -> str:
    ev = result.get("metadata_evaluation", {})
    lines = ["=== CANONICAL / SOCIAL / SCHEMA METADATA AS SERVED ==="]
    for key in ("canonical", "og_image", "og_image_width", "og_image_height",
                "twitter_image", "twitter_card", "schema_image"):
        lines.append(f"{key:18}: {meta.get(key) if meta.get(key) is not None else 'ABSENT'}")
    lines.append("")
    lines.append("=== EVALUATION AGAINST config/expected_metadata.json ===")
    lines.append(f"governed image path segment : {ev.get('governed_path_segment')}")
    lines.append(f"field states                : {json.dumps(ev.get('field_states', {}))}")
    lines.append(f"known obsolete detected     : {ev.get('obsolete_detected')}")
    for hit in ev.get("obsolete_hits", []):
        lines.append(f"  OBSOLETE {hit['field']} -> {hit['matched_path_segment']} "
                     f"(attachment {hit['obsolete_attachment_id']})")
    for miss in ev.get("expected_metadata_missing", []):
        lines.append(f"  MISSING/UNEXPECTED {miss['field']}: {miss['reason']}")
    lines.append("")
    lines.append("This is an observation. No change was made to the site.")
    return "\n".join(lines) + "\n"


def _procedure_text(result: dict) -> str:
    pub = result.get("public", {})
    return (
        "=== EXACT REQUEST PROCEDURE ===\n"
        f"requested URL      : {result.get('url')}\n"
        f"declared UA        : {result.get('user_agent')}\n"
        f"public requests    : {result.get('public_request_count')}\n"
        "query string       : none\n"
        "cache directives   : none sent (no Cache-Control, no Pragma, no cache-busting parameter)\n"
        "cookies            : none set, sent or manipulated (no cookie processor installed)\n"
        "conditional headers: none sent (no If-None-Match, no If-Modified-Since)\n"
        "session            : logged out; ordinary public visitor path only\n"
        f"request time (UTC) : {pub.get('request_utc')}\n"
        f"http status        : {pub.get('status')}\n"
        f"final URL          : {pub.get('final_url')}\n"
        f"redirect chain     : {json.dumps(pub.get('redirect_chain', []))}\n"
        f"response time (ms) : {pub.get('elapsed_ms')}\n"
        f"content-type       : {pub.get('content_type')}\n"
        f"content length     : {pub.get('content_length_bytes')}\n"
        f"body sha256        : {pub.get('body_sha256')}\n"
        f"mutation_attempted : {result.get('mutation_attempted')}\n"
        f"repair_attempted   : {result.get('repair_attempted')}\n"
    )


def _scheduler_text(result: dict) -> str:
    s = result.get("scheduler", {})
    return (
        "=== SCHEDULER EVIDENCE ===\n"
        f"scheduled time (IST)   : {s.get('scheduled_time_ist')}\n"
        f"run kind               : {s.get('run_kind')}\n"
        f"start                  : {json.dumps(s.get('started', {}))}\n"
        f"finish                 : {json.dumps(s.get('finished', {}))}\n"
        f"lock result            : {s.get('lock_result')}\n"
        f"maintenance lock       : {s.get('maintenance_lock')}\n"
        f"marker date before run : {s.get('marker_date_before')}\n"
        f"next scheduled (IST)   : {s.get('next_scheduled_ist')}\n"
    )


def _server_text(result: dict) -> str:
    srv = result.get("server", {})
    head = (
        "=== READ-ONLY SERVER INSPECTION ===\n"
        f"state                       : {result.get('server_inspection_state')}\n"
        f"server_commands_read_only   : {result.get('server_commands_read_only')}\n"
    )
    if result.get("server_inspection_state") != "available":
        return head + f"reason                      : {srv.get('unavailable_reason') or srv.get('blocked_reason')}\n"
    body = "".join(
        f"{k:28}: {json.dumps(v) if isinstance(v, (list, dict)) else v}\n"
        for k, v in srv.items()
        if k != "commands_executed"
    )
    cmds = "\nCommands executed (all from the fixed read-only template set):\n" + "".join(
        f"  [{c['template']}] {c['remote_command']}\n" for c in srv.get("commands_executed", [])
    )
    return head + body + cmds


def _write_manifest(evidence_dir: str, manifest_name: str) -> None:
    """Checksum every evidence file EXCEPT the manifest itself (self-exclusion)."""
    entries = []
    for name in sorted(os.listdir(evidence_dir)):
        if name == manifest_name:
            continue
        path = os.path.join(evidence_dir, name)
        if not os.path.isfile(path):
            continue
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        entries.append(f"{h.hexdigest()}  {name}")
    p = os.path.join(evidence_dir, manifest_name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(entries) + "\n")
    os.chmod(p, 0o600)


# --------------------------------------------------------------------------------------
# Human summary / notification
# --------------------------------------------------------------------------------------
def human_summary(result: dict) -> str:
    pub = result.get("public", {})
    srv = result.get("server", {})
    stale = result.get("stale_or_obsolete_detected")
    lines = [
        f"ambimat.com front-page cache inspection — {result.get('classification')}",
        "",
        f"run kind            : {result['scheduler'].get('run_kind')}",
        f"started (IST)       : {result['scheduler'].get('started', {}).get('ist')}",
        f"finished (IST)      : {result['scheduler'].get('finished', {}).get('ist')}",
        f"HTTP status         : {pub.get('status')}",
        f"stale/obsolete      : {'YES' if stale else 'no'}",
        f"cache file age      : {srv.get('age_seconds', 'unknown')}",
        f"server inspection   : {result.get('server_inspection_state')}",
        f"public requests     : {result.get('public_request_count')}",
        "",
        "No repair attempted.",
        "",
        "Reasons:",
    ]
    lines += [f"  - {r}" for r in result.get("reasons", [])] or ["  - (none)"]
    lines += ["", f"Evidence: {result.get('evidence_dir')}",
              f"Next scheduled inspection: {result['scheduler'].get('next_scheduled_ist')}"]
    if stale:
        lines += ["", "Manual review required — monitoring job made no changes."]
    return "\n".join(lines) + "\n"


def notification_text(result: dict) -> str:
    pub = result.get("public", {})
    srv = result.get("server", {})
    stale = result.get("stale_or_obsolete_detected")
    prefix = "!! " if stale else ""
    age = srv.get("age_seconds")
    parts = [
        f"{prefix}{result.get('classification')}",
        f"HTTP {pub.get('status')}",
        f"stale/obsolete: {'YES' if stale else 'no'}",
        f"cache age: {age if age is not None else 'unknown'}",
        f"server inspection: {result.get('server_inspection_state')}",
        "No repair attempted.",
    ]
    if stale:
        parts.append("Manual review required — monitoring job made no changes.")
    parts.append(f"Evidence: {result.get('evidence_dir')}")
    parts.append(f"Next: {result['scheduler'].get('next_scheduled_ist')}")
    return " | ".join(parts)


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def build_result(cfg: dict, args, obs, retries, started, marker_before) -> dict:
    finished = now_utc()
    body = obs.body if obs is not None else b""
    public_ok = bool(obs is not None and obs.error is None and obs.status is not None
                     and obs.status != 429 and not (500 <= obs.status <= 599))

    meta = extract_metadata(body, cfg) if public_ok else {}
    meta_eval = evaluate_metadata(meta, cfg) if public_ok else {
        "obsolete_detected": False, "obsolete_hits": [], "expected_metadata_missing": [],
        "unexpected_values": [], "field_states": {}, "governed_path_segment": None,
    }

    body_sha = hashlib.sha256(body).hexdigest() if body else None
    headers = sanitize_headers(obs.headers) if obs is not None else {}

    server: dict = {}
    server_state = "unavailable"
    server_commands_read_only = "unavailable"
    if public_ok:
        try:
            sc = load_server_config(args.server_config)
            server = inspect_server(sc, cfg, body_sha)
            server_state = "available"
            server_commands_read_only = True
        except ServerInspectionUnavailable as exc:
            server = {"available": False, "unavailable_reason": str(exc)}
            server_state = "unavailable"
            server_commands_read_only = "unavailable"
        except (ServerInspectionBlocked, subprocess.SubprocessError, OSError, ValueError) as exc:
            server = {"available": False, "blocked_reason": f"{type(exc).__name__}: {exc}"}
            server_state = "blocked"
            server_commands_read_only = True  # nothing but read-only templates was ever attempted

    classification, reasons = classify(public_ok, meta_eval, server, server_state)

    result = {
        "job": "ambimat_front_page_cache_monitor",
        "purpose": "inspect and report only — this job has no capability to change anything",
        "url": cfg["url"],
        "user_agent": cfg["user_agent"],
        "classification": classification,
        "reasons": reasons,
        "stale_or_obsolete_detected": classification in (ALERT_STALE, ALERT_MISMATCH),
        "conclusive_inspection": classification in CONCLUSIVE,
        "mutation_attempted": False,
        "repair_attempted": False,
        "public_request_count": len(retries),
        "server_commands_read_only": server_commands_read_only,
        "server_inspection_state": server_state,
        "public": {
            "request_utc": stamp(started)["utc"],
            "status": obs.status if obs is not None else None,
            "transport_error": obs.error if obs is not None else "no attempt recorded",
            "final_url": obs.final_url if obs is not None else None,
            "redirect_chain": obs.redirects if obs is not None else [],
            "elapsed_ms": obs.elapsed_ms if obs is not None else None,
            "content_type": headers.get("content-type"),
            "content_length_bytes": len(body) if body else 0,
            "body_sha256": body_sha,
            "cache_headers": {h: headers.get(h) for h in CACHE_HEADERS if h in headers},
            "all_headers_sanitized": headers,
        },
        "metadata": meta,
        "metadata_evaluation": meta_eval,
        "server": server,
        "retry_history": retries,
        "scheduler": {
            "scheduled_time_ist": SCHEDULED_TIME_IST,
            "run_kind": args.run_kind,
            "started": stamp(started),
            "finished": stamp(finished),
            "lock_result": args.lock_result,
            "maintenance_lock": args.maintenance_lock,
            "marker_date_before": marker_before,
            "next_scheduled_ist": _next_run_ist(finished),
        },
        "evidence_dir": args.evidence_dir,
    }
    return result, meta


# The one place the cache monitor's scheduled time is written down. Moved from
# 12:00 to 10:00 IST on 2026-09-07 with the rest of the daily schedule; the cron
# line and the watchdog due time (DUE_HM in run_cache_monitor_daily.sh) must agree.
SCHEDULED_HOUR_IST = 10
SCHEDULED_TIME_IST = "10:00"


def _next_run_ist(from_dt: _dt.datetime) -> str:
    local = from_dt.astimezone(IST)
    due = local.replace(hour=SCHEDULED_HOUR_IST, minute=0, second=0, microsecond=0)
    if local >= due:
        due += _dt.timedelta(days=1)
    return due.strftime("%Y-%m-%d ") + SCHEDULED_TIME_IST + " IST"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only ambimat.com front-page cache inspection.")
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "config", "expected_metadata.json"))
    ap.add_argument("--server-config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "config", "server_inspection.json"))
    ap.add_argument("--evidence-root", default=os.path.expanduser("~/cache_monitor_reports"))
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--run-kind", default="scheduled",
                    choices=["scheduled", "catch_up", "manual", "canary"])
    ap.add_argument("--lock-result", default="acquired")
    ap.add_argument("--maintenance-lock", default="clear")
    ap.add_argument("--marker-date-before", default=None)
    ap.add_argument("--print-notification", action="store_true")
    args = ap.parse_args(argv)

    started = now_utc()
    if not args.evidence_dir:
        args.evidence_dir = os.path.join(args.evidence_root, f"noon-cache-inspection-{compact_utc(started)}")

    try:
        with open(args.config, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        obs, retries = fetch_with_bounded_retries(cfg)
        result, meta = build_result(cfg, args, obs, retries, started, args.marker_date_before)
        write_evidence(args.evidence_dir, result, obs, meta, retries)
    except Exception as exc:  # the monitor itself failed
        finished = now_utc()
        result = {
            "job": "ambimat_front_page_cache_monitor",
            "classification": ERROR_INTERNAL,
            "reasons": [f"{type(exc).__name__}: {exc}"],
            "stale_or_obsolete_detected": False,
            "conclusive_inspection": False,
            "mutation_attempted": False,
            "repair_attempted": False,
            "public_request_count": 0,
            "server_commands_read_only": "unavailable",
            "server_inspection_state": "unavailable",
            "public": {}, "server": {},
            "scheduler": {
                "scheduled_time_ist": SCHEDULED_TIME_IST, "run_kind": args.run_kind,
                "started": stamp(started), "finished": stamp(finished),
                "lock_result": args.lock_result, "maintenance_lock": args.maintenance_lock,
                "marker_date_before": args.marker_date_before,
                "next_scheduled_ist": _next_run_ist(finished),
            },
            "evidence_dir": args.evidence_dir,
        }
        try:
            write_evidence(args.evidence_dir, result, None, {}, [])
        except Exception:  # pragma: no cover
            pass
        if args.print_notification:
            print(notification_text(result))
        else:
            print(human_summary(result))
        return EXIT_INTERNAL

    if args.print_notification:
        print(notification_text(result))
    else:
        print(human_summary(result))

    if result["classification"] == FAIL_PUBLIC:
        return EXIT_PUBLIC_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

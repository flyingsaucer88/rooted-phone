#!/usr/bin/env python3
"""Fixture tests for the read-only front-page cache monitor.

Every test here is offline: no test in this file makes a network request, and none of
them touches the phone's real markers, locks, crontab or evidence directories.

Run:  python3 cache_monitor/tests/test_cache_monitor.py
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
sys.path.insert(0, ROOT)

import front_page_cache_monitor as m  # noqa: E402

def fixture(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as fh:
        return fh.read()


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def read_json(path: str):
    return json.loads(read(path))


CFG = read_json(os.path.join(ROOT, "config", "expected_metadata.json"))


def evaluate(name: str) -> dict:
    return m.evaluate_metadata(m.extract_metadata(fixture(name), CFG), CFG)


class FakeObs:
    def __init__(self, body=b"", status=200, error=None, headers=None, retry_after=None):
        self.ok = error is None
        self.error = error
        self.status = status
        self.final_url = CFG["url"]
        self.redirects = []
        self.elapsed_ms = 42
        self.headers = headers or {"content-type": "text/html; charset=UTF-8"}
        self.body = body
        self.retry_after = retry_after


class Args:
    run_kind = "manual"
    lock_result = "acquired"
    maintenance_lock = "clear"
    evidence_dir = "/dev/null/never"
    server_config = "/nonexistent/server_inspection.json"


def run_monitor(body_fixture, server_config=None, server_reader=None, evidence_dir=None):
    args = Args()
    if server_config:
        args.server_config = server_config
    if evidence_dir:
        args.evidence_dir = evidence_dir
    obs = FakeObs(body=fixture(body_fixture))
    retries = [{"attempt": 1, "outcome": "response_captured"}]
    result, _meta = m.build_result(CFG, args, obs, retries, m.now_utc(), "none")
    return result


# ---------------------------------------------------------------------------
# 1. Metadata parsing and evaluation
# ---------------------------------------------------------------------------
class TestMetadataParsing(unittest.TestCase):
    def test_parses_the_real_stale_shape(self):
        meta = m.extract_metadata(fixture("stale_obsolete.html"), CFG)
        self.assertEqual(meta["canonical"], "https://ambimat.com/")
        self.assertIn("2022/05/image_2022.png", meta["og_image"])
        self.assertEqual(meta["og_image_width"], "1021")
        self.assertIsNone(meta["twitter_image"])  # absent in the real stack output
        self.assertIn("ambimat-home-ambimat.com-1200x630-1.png", meta["schema_image"])

    def test_schema_solidus_unescaping_and_logo_skipping(self):
        meta = m.extract_metadata(fixture("stale_obsolete.html"), CFG)
        self.assertNotIn("\\/", meta["schema_image"])
        self.assertNotIn("Ambimat-Logo.png", meta["schema_image"])

    def test_healthy_fixture_is_clean(self):
        ev = evaluate("healthy.html")
        self.assertFalse(ev["obsolete_detected"])
        self.assertEqual(ev["expected_metadata_missing"], [])
        self.assertEqual(ev["field_states"]["og_image"], "governed")

    def test_absent_twitter_image_is_not_an_alert(self):
        ev = evaluate("healthy.html")
        self.assertEqual(ev["field_states"]["twitter_image"], "absent")
        self.assertFalse(any(x["field"] == "twitter_image" for x in ev["expected_metadata_missing"]))

    def test_present_governed_twitter_image_is_clean(self):
        ev = evaluate("healthy_with_twitter.html")
        self.assertFalse(ev["obsolete_detected"])

    def test_obsolete_og_image_is_detected(self):
        ev = evaluate("stale_obsolete.html")
        self.assertTrue(ev["obsolete_detected"])
        self.assertEqual(ev["obsolete_hits"][0]["obsolete_attachment_id"], 9920)

    def test_obsolete_twitter_image_alone_is_detected(self):
        ev = evaluate("obsolete_twitter_only.html")
        self.assertTrue(ev["obsolete_detected"])
        self.assertEqual(ev["obsolete_hits"][0]["field"], "twitter_image")

    def test_missing_required_metadata_is_recorded(self):
        ev = evaluate("missing_metadata.html")
        fields = {x["field"] for x in ev["expected_metadata_missing"]}
        self.assertEqual(fields, {"canonical", "og_image"})

    def test_wrong_canonical_is_recorded(self):
        ev = evaluate("wrong_canonical.html")
        self.assertIn("canonical", {x["field"] for x in ev["expected_metadata_missing"]})


# ---------------------------------------------------------------------------
# 2. Classification
# ---------------------------------------------------------------------------
class TestClassification(unittest.TestCase):
    def test_healthy_public_only(self):
        r = run_monitor("healthy.html")
        self.assertEqual(r["classification"], m.PASS_PUBLIC_ONLY)
        self.assertTrue(r["conclusive_inspection"])
        self.assertFalse(r["stale_or_obsolete_detected"])

    def test_stale_alerts(self):
        r = run_monitor("stale_obsolete.html")
        self.assertEqual(r["classification"], m.ALERT_STALE)
        self.assertTrue(r["stale_or_obsolete_detected"])
        self.assertTrue(r["conclusive_inspection"], "a stale finding is a COMPLETED inspection")

    def test_missing_metadata_alerts(self):
        r = run_monitor("missing_metadata.html")
        self.assertEqual(r["classification"], m.ALERT_STALE)

    def test_healthy_with_server_evidence(self):
        server = {"sha256_matches_public_body": True, "over_lifetime": False,
                  "cleanup_overdue": False, "path_within_expected_cache_root": True}
        cls, reasons = m.classify(True, evaluate("healthy.html"), server, "available")
        self.assertEqual(cls, m.PASS_HEALTHY)
        self.assertTrue(reasons)

    def test_over_lifetime_warns(self):
        server = {"sha256_matches_public_body": True, "over_lifetime": True,
                  "age_seconds": 7200, "configured_lifetime_seconds": 3600,
                  "cleanup_overdue": False, "path_within_expected_cache_root": True}
        cls, _ = m.classify(True, evaluate("healthy.html"), server, "available")
        self.assertEqual(cls, m.WARN_OVER_LIFETIME)

    def test_cleanup_overdue_warns(self):
        server = {"sha256_matches_public_body": True, "over_lifetime": False,
                  "cleanup_overdue": True, "path_within_expected_cache_root": True}
        cls, _ = m.classify(True, evaluate("healthy.html"), server, "available")
        self.assertEqual(cls, m.WARN_OVER_LIFETIME)

    def test_public_server_mismatch_alerts(self):
        server = {"sha256_matches_public_body": False, "over_lifetime": False,
                  "cleanup_overdue": False, "path_within_expected_cache_root": True}
        cls, _ = m.classify(True, evaluate("healthy.html"), server, "available")
        self.assertEqual(cls, m.ALERT_MISMATCH)

    def test_stale_outranks_mismatch_and_warn(self):
        server = {"sha256_matches_public_body": False, "over_lifetime": True,
                  "cleanup_overdue": True, "path_within_expected_cache_root": True}
        cls, _ = m.classify(True, evaluate("stale_obsolete.html"), server, "available")
        self.assertEqual(cls, m.ALERT_STALE)

    def test_blocked_server_inspection(self):
        cls, _ = m.classify(True, evaluate("healthy.html"),
                            {"blocked_reason": "publickey denied"}, "blocked")
        self.assertEqual(cls, m.BLOCKED_SERVER)
        self.assertIn(m.BLOCKED_SERVER, m.CONCLUSIVE)

    def test_failed_public_request(self):
        cls, _ = m.classify(False, {}, {}, "unavailable")
        self.assertEqual(cls, m.FAIL_PUBLIC)
        self.assertNotIn(m.FAIL_PUBLIC, m.CONCLUSIVE)

    def test_no_recovery_classifications_exist(self):
        banned = ["PASS_NATURAL_RECOVERY", "PASS_FRONT_PAGE_ONLY_RECOVERY",
                  "FAIL_STALE_AFTER_BOUNDED_RECOVERY"]
        for b in banned:
            self.assertNotIn(b, read(os.path.join(ROOT, "front_page_cache_monitor.py")))


# ---------------------------------------------------------------------------
# 3. Retries — transport only, never to re-check content
# ---------------------------------------------------------------------------
class TestRetries(unittest.TestCase):
    def test_one_request_when_the_page_answers(self):
        calls = []

        def fetcher(*a):
            calls.append(a)
            return FakeObs(body=fixture("stale_obsolete.html"))

        obs, hist = m.fetch_with_bounded_retries(CFG, sleeper=lambda s: None, fetcher=fetcher)
        self.assertEqual(len(calls), 1, "a stale page must NOT be re-requested")
        self.assertEqual(hist[0]["outcome"], "response_captured")

    def test_transport_failure_is_bounded(self):
        calls = []

        def fetcher(*a):
            calls.append(a)
            return FakeObs(error="URLError: connection refused", status=None)

        obs, hist = m.fetch_with_bounded_retries(CFG, sleeper=lambda s: None, fetcher=fetcher)
        self.assertEqual(len(calls), CFG["transport_retry"]["max_attempts"])
        self.assertEqual(hist[-1]["retry_decision"], "exhausted")

    def test_429_honours_retry_after(self):
        slept = []
        seq = [FakeObs(status=429, headers={"retry-after": "37"}, retry_after="37"),
               FakeObs(body=fixture("healthy.html"))]

        def fetcher(*a):
            return seq.pop(0)

        obs, hist = m.fetch_with_bounded_retries(CFG, sleeper=slept.append, fetcher=fetcher)
        self.assertEqual(slept, [37])
        self.assertEqual(hist[0]["retry_after_header"], "37")
        self.assertEqual(len(hist), 2)

    def test_retry_after_is_capped(self):
        cap = CFG["transport_retry"]["retry_after_cap_seconds"]
        self.assertEqual(m._parse_retry_after("99999", cap), cap)

    def test_5xx_is_retried_then_gives_up(self):
        calls = []

        def fetcher(*a):
            calls.append(a)
            return FakeObs(status=503, body=b"")

        obs, hist = m.fetch_with_bounded_retries(CFG, sleeper=lambda s: None, fetcher=fetcher)
        self.assertEqual(len(calls), 3)
        self.assertEqual(hist[-1]["outcome"], "http_5xx")

    def test_404_is_not_retried(self):
        calls = []

        def fetcher(*a):
            calls.append(a)
            return FakeObs(status=404, body=b"<html></html>")

        m.fetch_with_bounded_retries(CFG, sleeper=lambda s: None, fetcher=fetcher)
        self.assertEqual(len(calls), 1)


# ---------------------------------------------------------------------------
# 4. Server inspection — read-only guarantees
# ---------------------------------------------------------------------------
class FakeReader:
    """Stands in for SshReader. Records every command the monitor asks for."""

    def __init__(self, sc, responses=None, raise_on=None):
        self.sc = sc
        self.executed = []
        self.responses = responses or {}
        self.raise_on = raise_on or {}

    def run(self, key, **kwargs):
        template = m.SERVER_READ_ONLY_COMMANDS[key]
        subs = {}
        if "path" in kwargs:
            subs["path"] = m._validated_path(kwargs["path"])
        if "option" in kwargs:
            subs["option"] = m._validated_option(kwargs["option"])
        remote = template.format(**subs)
        self.executed.append({"template": key, "remote_command": remote})
        if key in self.raise_on:
            raise self.raise_on[key]
        value = self.responses.get(key, "")
        return value(kwargs) if callable(value) else value


SC = {"host": "h", "user": "u", "port": 22, "identity_file": "/dev/null",
      "wp_path": "/home/example/domains/ambimat.com/public_html"}


def reader_factory(**kw):
    return lambda sc: FakeReader(sc, **kw)


def stat_line(age_seconds, size=192835, owner="example", group="o", mode="644"):
    mtime = int(m.now_utc().timestamp()) - age_seconds
    return f"{owner}|{group}|{mode}|{mtime}|{size}|regular file"


class TestServerInspection(unittest.TestCase):
    def _responses(self, **over):
        cache = ("/home/example/domains/ambimat.com/public_html/"
                 "wp-content/cache/page_enhanced/ambimat.com/_index_slash_ssl.html")
        base = {
            "wp_option": lambda kw: "https://ambimat.com",
            "test_exists": "exists",
            "test_regular": "regular",
            "test_symlink": "not_symlink",
            "realpath": cache,
            "stat": stat_line(600),
            "sha256": "abc123  " + cache,
            "wp_cron_list": json.dumps([
                {"hook": "w3_pgcache_cleanup",
                 "next_run_gmt": (m.now_utc() + datetime.timedelta(minutes=30))
                 .strftime("%Y-%m-%d %H:%M:%S")}]),
        }
        base.update(over)
        return base

    def test_only_allowlisted_templates_are_issued(self):
        out = m.inspect_server(SC, CFG, "abc123",
                               reader_cls=reader_factory(responses=self._responses()))
        keys = {c["template"] for c in out["commands_executed"]}
        self.assertTrue(keys.issubset(set(m.SERVER_READ_ONLY_COMMANDS)))
        self.assertTrue(out["exists"])
        self.assertTrue(out["sha256_matches_public_body"])
        self.assertFalse(out["over_lifetime"])
        self.assertFalse(out["cleanup_overdue"])

    def test_over_lifetime_is_computed(self):
        out = m.inspect_server(SC, CFG, "abc123",
                               reader_cls=reader_factory(
                                   responses=self._responses(stat=stat_line(7200))))
        self.assertTrue(out["over_lifetime"])
        self.assertGreater(out["age_seconds"], 3600)

    def test_hash_mismatch_is_reported(self):
        out = m.inspect_server(SC, CFG, "different-digest",
                               reader_cls=reader_factory(responses=self._responses()))
        self.assertFalse(out["sha256_matches_public_body"])

    def test_symlinked_cache_path_reports_only(self):
        out = m.inspect_server(SC, CFG, "abc123",
                               reader_cls=reader_factory(
                                   responses=self._responses(test_symlink="symlink")))
        self.assertTrue(out["is_symlink"])
        self.assertIsNone(out["sha256"], "an unexpected path must not even be hashed")
        self.assertTrue(any("UNSAFE OR UNEXPECTED" in n for n in out["notes"]))
        keys = [c["template"] for c in out["commands_executed"]]
        self.assertNotIn("sha256", keys)

    def test_cache_path_outside_the_cache_root_reports_only(self):
        out = m.inspect_server(SC, CFG, "abc123",
                               reader_cls=reader_factory(
                                   responses=self._responses(realpath="/etc/passwd")))
        self.assertFalse(out["path_within_expected_cache_root"])
        self.assertIsNone(out["sha256"])

    def test_missing_cache_file_is_reported_not_repaired(self):
        out = m.inspect_server(SC, CFG, "abc123",
                               reader_cls=reader_factory(
                                   responses=self._responses(test_exists="absent")))
        self.assertFalse(out["exists"])
        self.assertIn("no cache entry", " ".join(out["notes"]))

    def test_overdue_cleanup_is_reported(self):
        past = (m.now_utc() - datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        out = m.inspect_server(SC, CFG, "abc123",
                               reader_cls=reader_factory(responses=self._responses(
                                   wp_cron_list=json.dumps(
                                       [{"hook": "w3_pgcache_cleanup", "next_run_gmt": past}]))))
        self.assertTrue(out["cleanup_overdue"])

    def test_auth_failure_raises_blocked(self):
        with self.assertRaises(m.ServerInspectionBlocked):
            m.inspect_server(SC, CFG, "abc123", reader_cls=reader_factory(
                responses=self._responses(),
                raise_on={"wp_option": m.ServerInspectionBlocked("Permission denied (publickey)")}))

    def test_path_validator_rejects_injection(self):
        for bad in ["/tmp/x; rm -rf /", "/tmp/../etc", "relative/path", "/tmp/$(id)", ""]:
            with self.assertRaises(m.ServerInspectionBlocked, msg=bad):
                m._validated_path(bad)

    def test_option_validator_rejects_injection(self):
        for bad in ["siteurl; id", "Site-Url", "", "../x"]:
            with self.assertRaises(m.ServerInspectionBlocked, msg=bad):
                m._validated_option(bad)

    def test_absent_config_is_unavailable_not_blocked(self):
        with self.assertRaises(m.ServerInspectionUnavailable):
            m.load_server_config("/nonexistent/server_inspection.json")

    def test_disabled_config_is_unavailable(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"enabled": False}, fh)
            p = fh.name
        try:
            with self.assertRaises(m.ServerInspectionUnavailable):
                m.load_server_config(p)
        finally:
            os.unlink(p)

    def test_enabled_config_with_missing_key_is_unavailable(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"enabled": True, "host": "h", "user": "u",
                       "identity_file": "/nonexistent/key", "wp_path": "/x"}, fh)
            p = fh.name
        try:
            with self.assertRaises(m.ServerInspectionUnavailable):
                m.load_server_config(p)
        finally:
            os.unlink(p)

    def test_example_config_ships_disabled(self):
        example = read_json(os.path.join(ROOT, "config", "server_inspection.example.json"))
        self.assertFalse(example["enabled"])


# ---------------------------------------------------------------------------
# 5. Evidence
# ---------------------------------------------------------------------------
class TestEvidence(unittest.TestCase):
    def test_evidence_files_and_self_excluding_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            ev = os.path.join(td, "run")
            r = run_monitor("stale_obsolete.html", evidence_dir=ev)
            obs = FakeObs(body=fixture("stale_obsolete.html"),
                          headers={"content-type": "text/html", "etag": '"2f143-657e583550537"',
                                   "last-modified": "Fri, 31 Jul 2026 10:18:42 GMT",
                                   "set-cookie": "SECRET=should-never-appear"})
            m.write_evidence(ev, r, obs, r["metadata"], r["retry_history"])

            for name in ["result.json", "SUMMARY.txt", "notification.txt",
                         "response-headers.txt", "parsed-metadata.txt",
                         "request-procedure.txt", "retry-history.txt",
                         "scheduler.txt", "server-inspection.txt", "EVIDENCE.sha256"]:
                self.assertTrue(os.path.exists(os.path.join(ev, name)), name)

            manifest = read(os.path.join(ev, "EVIDENCE.sha256"))
            self.assertNotIn("EVIDENCE.sha256", manifest, "manifest must exclude itself")
            listed = {ln.split("  ", 1)[1] for ln in manifest.strip().splitlines()}
            on_disk = {f for f in os.listdir(ev) if f != "EVIDENCE.sha256"}
            self.assertEqual(listed, on_disk)

    def test_no_secret_headers_reach_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            ev = os.path.join(td, "run")
            r = run_monitor("healthy.html", evidence_dir=ev)
            obs = FakeObs(body=fixture("healthy.html"),
                          headers={"content-type": "text/html",
                                   "set-cookie": "SECRET=leak",
                                   "authorization": "Bearer leak"})
            m.write_evidence(ev, r, obs, r["metadata"], [])
            blob = ""
            for f in os.listdir(ev):
                blob += read(os.path.join(ev, f))
            self.assertNotIn("SECRET=leak", blob)
            self.assertNotIn("Bearer leak", blob)

    def test_required_explicit_fields(self):
        r = run_monitor("stale_obsolete.html")
        self.assertIs(r["mutation_attempted"], False)
        self.assertIs(r["repair_attempted"], False)
        self.assertEqual(r["public_request_count"], 1)
        self.assertIn(r["server_commands_read_only"], (True, False, "unavailable"))

    def test_notification_content(self):
        r = run_monitor("stale_obsolete.html")
        note = m.notification_text(r)
        for expected in [m.ALERT_STALE, "HTTP 200", "stale/obsolete: YES",
                         "No repair attempted.",
                         "Manual review required — monitoring job made no changes.",
                         "Next:"]:
            self.assertIn(expected, note)

    def test_healthy_notification_is_not_alarming(self):
        note = m.notification_text(run_monitor("healthy.html"))
        self.assertNotIn("Manual review required", note)
        self.assertIn("No repair attempted.", note)


# ---------------------------------------------------------------------------
# 6. Timezone / next-run arithmetic (Asia/Kolkata)
# ---------------------------------------------------------------------------
class TestTimezone(unittest.TestCase):
    def test_next_noon_before_noon_is_today(self):
        t = datetime.datetime(2026, 8, 1, 3, 0, tzinfo=m.UTC)  # 08:30 IST
        self.assertEqual(m._next_noon_ist(t), "2026-08-01 12:00 IST")

    def test_next_noon_after_noon_is_tomorrow(self):
        t = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=m.UTC)  # 14:30 IST
        self.assertEqual(m._next_noon_ist(t), "2026-08-02 12:00 IST")

    def test_ist_offset_is_plus_0530(self):
        t = datetime.datetime(2026, 8, 1, 6, 30, tzinfo=m.UTC)
        s = m.stamp(t)
        self.assertEqual(s["utc"], "2026-08-01T06:30:00Z")
        self.assertEqual(s["ist"], "2026-08-01T12:00:00+0530")

    def test_late_utc_maps_to_next_ist_day(self):
        t = datetime.datetime(2026, 8, 1, 19, 0, tzinfo=m.UTC)  # 2026-08-02 00:30 IST
        self.assertEqual(m.stamp(t)["ist"][:10], "2026-08-02")


# ---------------------------------------------------------------------------
# 7. Static proof: no mutation or repair capability
# ---------------------------------------------------------------------------
class TestNoMutationPath(unittest.TestCase):
    def test_audit_script_passes(self):
        audit = os.path.join(HERE, "audit_no_mutation.sh")
        proc = subprocess.run(["bash", audit], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_no_repair_flags_in_the_cli(self):
        proc = subprocess.run([sys.executable,
                               os.path.join(ROOT, "front_page_cache_monitor.py"), "--help"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        for flag in ["--fix", "--purge", "--recover", "--repair", "--flush", "--warm", "--rebuild"]:
            self.assertNotIn(flag, proc.stdout)

    def test_remote_command_set_is_small_and_read_only(self):
        self.assertEqual(
            set(m.SERVER_READ_ONLY_COMMANDS),
            {"wp_option", "wp_cron_list", "test_exists", "test_regular",
             "test_symlink", "realpath", "readlink", "stat", "sha256"},
        )

    def test_audit_actually_catches_an_injected_violation(self):
        """Negative control: prove the audit is not vacuously passing."""
        injections = [
            ('    subprocess.run(["ssh", "host", "wp cache flush"])\n', "cache flush"),
            ('    req.add_header("Cache-Control", "no-cache")\n', "no-cache"),
            ('    os.remove("/tmp/x")\n', "os.remove"),
            ('    ap.add_argument("--purge")\n', "--purge"),
        ]
        source = read(os.path.join(ROOT, "front_page_cache_monitor.py"))
        for snippet, token in injections:
            with tempfile.TemporaryDirectory() as td:
                shadow = os.path.join(td, "cache_monitor")
                os.makedirs(os.path.join(shadow, "tests"))
                for f in ["run_cache_monitor_daily.sh", "install_noon_job.sh",
                          "ensure_scheduler_noon_block.sh"]:
                    with open(os.path.join(shadow, f), "w") as fh:
                        fh.write(read(os.path.join(ROOT, f)))
                with open(os.path.join(shadow, "front_page_cache_monitor.py"), "w") as fh:
                    fh.write(source + "\n\ndef _injected_violation():\n" + snippet)
                with open(os.path.join(shadow, "tests", "audit_no_mutation.py"), "w") as fh:
                    fh.write(read(os.path.join(HERE, "audit_no_mutation.py")))
                proc = subprocess.run(
                    [sys.executable, os.path.join(shadow, "tests", "audit_no_mutation.py")],
                    capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1, f"audit missed {token!r}\n{proc.stdout}")
                self.assertIn(token, proc.stdout)

    def test_the_request_carries_no_cache_directives(self):
        source = read(os.path.join(ROOT, "front_page_cache_monitor.py"))
        body = source.split("def observe_public")[1].split("def _collect_headers")[0]
        self.assertIn("User-Agent", body)
        self.assertIn("Accept", body)
        # Exactly two request headers are ever added.
        self.assertEqual(body.count("req.add_header("), 2)


# ---------------------------------------------------------------------------
# 8. End-to-end through main(), still fully offline
# ---------------------------------------------------------------------------
class TestEndToEndOffline(unittest.TestCase):
    def _run(self, body_fixture, status=200):
        original = m.observe_public
        m.observe_public = lambda *a, **k: FakeObs(body=fixture(body_fixture), status=status)
        try:
            with tempfile.TemporaryDirectory() as td:
                ev = os.path.join(td, "run")
                rc = m.main(["--evidence-dir", ev, "--run-kind", "manual",
                             "--server-config", "/nonexistent/server_inspection.json"])
                return rc, read_json(os.path.join(ev, "result.json")), sorted(os.listdir(ev))
        finally:
            m.observe_public = original

    def test_stale_page_exits_zero_and_records_everything(self):
        rc, result, files = self._run("stale_obsolete.html")
        self.assertEqual(rc, m.EXIT_OK, "a stale finding is a completed inspection")
        self.assertEqual(result["classification"], m.ALERT_STALE)
        self.assertEqual(result["public_request_count"], 1)
        self.assertIs(result["mutation_attempted"], False)
        self.assertIs(result["repair_attempted"], False)
        self.assertEqual(result["server_commands_read_only"], "unavailable")
        self.assertIn("EVIDENCE.sha256", files)
        self.assertIn("result.json", files)

    def test_healthy_page_end_to_end(self):
        rc, result, _ = self._run("healthy.html")
        self.assertEqual(rc, m.EXIT_OK)
        self.assertEqual(result["classification"], m.PASS_PUBLIC_ONLY)

    def test_internal_failure_is_reported_not_hidden(self):
        original = m.fetch_with_bounded_retries
        m.fetch_with_bounded_retries = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with tempfile.TemporaryDirectory() as td:
                ev = os.path.join(td, "run")
                rc = m.main(["--evidence-dir", ev])
                result = read_json(os.path.join(ev, "result.json"))
        finally:
            m.fetch_with_bounded_retries = original
        self.assertEqual(rc, m.EXIT_INTERNAL)
        self.assertEqual(result["classification"], m.ERROR_INTERNAL)
        self.assertFalse(result["conclusive_inspection"])

    def test_repeated_transport_failure_exits_nonzero(self):
        original = m.observe_public
        m.observe_public = lambda *a, **k: FakeObs(error="URLError: no route", status=None)
        try:
            with tempfile.TemporaryDirectory() as td:
                ev = os.path.join(td, "run")
                sleep_original = m.time.sleep
                m.time.sleep = lambda s: None
                try:
                    rc = m.main(["--evidence-dir", ev])
                finally:
                    m.time.sleep = sleep_original
                result = read_json(os.path.join(ev, "result.json"))
        finally:
            m.observe_public = original
        self.assertEqual(rc, m.EXIT_PUBLIC_FAILED)
        self.assertEqual(result["classification"], m.FAIL_PUBLIC)
        self.assertEqual(result["public_request_count"], CFG["transport_retry"]["max_attempts"])
        self.assertFalse(result["conclusive_inspection"])


def _block_all_network() -> None:
    """Make it impossible for this suite to reach the internet.

    Any attempt to open a socket raises. That is the proof that every result below came
    from a fixture, and that running the tests never touches the live site.
    """
    import socket as _socket

    class _Blocked(_socket.socket):
        def __init__(self, *a, **k):
            raise RuntimeError("the offline test suite must not open a network connection")

    def _blocked_connect(*a, **k):
        raise RuntimeError("the offline test suite must not open a network connection")

    _socket.socket = _Blocked
    _socket.create_connection = _blocked_connect


if __name__ == "__main__":
    _block_all_network()
    unittest.main(verbosity=2)

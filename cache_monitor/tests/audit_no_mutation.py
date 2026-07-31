#!/usr/bin/env python3
"""Static proof that the noon cache monitor has no mutation or repair capability.

The audit reads the shipped runtime files and fails loudly if it finds anything that
could change the site, bypass the cache, or act on a finding.

It deliberately audits EXECUTABLE content only — Python code with docstrings removed,
shell with comment lines removed — because the prose in those files necessarily names the
things the job must never do ("no purge, no warm-up"), and a naive grep would confuse the
prohibition with the act.

Exit 0 = clean. Exit 1 = at least one finding, printed with file and line.
"""

from __future__ import annotations

import ast
import io
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNTIME_PY = ["front_page_cache_monitor.py"]
RUNTIME_SH = [
    "run_cache_monitor_daily.sh",
    "install_noon_job.sh",
    "ensure_scheduler_noon_block.sh",
]

# TIER 1 — command-shaped. These may not appear in executable code anywhere, in any
# context, because there is no legitimate reason for this job to name them at all.
PROHIBITED_ABSOLUTE = [
    # cache management / deliberate cron triggering
    "cron event run", "--due-now", "cache flush", "cache clear", "cache delete",
    "w3-total-cache", "expire_now", "w3tc_flush", "pgcache_flush",
    # mutating WP-CLI
    "option update", "option set", "option delete", "option add", "option patch",
    "post update", "post meta", "post delete", "db query", "db import",
    "yoast index", "plugin activate", "plugin deactivate", "plugin install",
    "theme activate", "media regenerate", "media import", "transient delete",
    # SQL that is not a SELECT
    "insert into", "delete from", "drop table", "truncate table", "alter table",
    "replace into", "update wp_", "set autocommit",
    # filesystem mutation
    "rm -rf /", "unlink(", "shutil.rmtree", "os.remove", "os.unlink", "os.rename",
    "os.truncate", "truncate -", "chown ", "ln -s",
    # repair-shaped switches
    "--fix", "--purge", "--repair", "--recover", "--warm", "--rebuild", "--flush",
    "--invalidate", "repair_mode", "fix_mode", "auto_fix",
]

# TIER 2 — vocabulary. The job MUST be able to say these words in the text it reports
# ("No repair attempted", "no Pragma sent"), so they are permitted inside the evidence
# and notification builders and nowhere else. Anywhere else they would describe an act.
PROHIBITED_CONTEXTUAL = [
    "purge", "flush", "invalidate", "warm", "preload", "rebuild", "regenerate",
    "repair", "remediat", "rollback", "recover(",
    "no-cache", "nocache", "pragma", "if-none-match", "if-modified-since",
    "must-revalidate", "max-age=0", "cache-bust", "cachebust", "_cb=", "?nocache",
]

# Functions whose entire job is to write human- or machine-readable report text.
REPORT_FUNCTIONS = {
    "_procedure_text", "_metadata_text", "_server_text", "_scheduler_text",
    "human_summary", "notification_text", "write_evidence", "build_result",
    "classify", "main",
}

# Field names that legitimately contain a tier-2 word. Removed before tier-2 scanning so
# the required evidence fields do not read as findings.
ALLOWED_IDENTIFIERS = [
    "repair_attempted", "w3_pgcache_cleanup_next_run_gmt", "w3_pgcache_cleanup",
    "cleanup_overdue", "_read_cron",
]

# Paths that identify the live site. Nothing in a write position may mention them.
SITE_PATHS = ["wp-content", "page_enhanced", "public_html", "wp-config"]

# The only remote command templates that may exist.
EXPECTED_TEMPLATE_KEYS = {
    "wp_option", "wp_cron_list", "test_exists", "test_regular",
    "test_symlink", "realpath", "readlink", "stat", "sha256",
}
# Every template must begin with one of these provably read-only commands.
ALLOWED_TEMPLATE_HEADS = re.compile(
    r"^(wp --path=\{path\} --skip-plugins --skip-themes (option get|cron event list)"
    r"|test -[efL] \{path\}|realpath \{path\}|readlink -f \{path\}"
    r"|stat -c [^ ]+ \{path\}|sha256sum \{path\})"
)

findings: list = []


def report(path: str, line: int, message: str) -> None:
    findings.append(f"{path}:{line}: {message}")


# ---------------------------------------------------------------------------
def strip_python(src: str) -> list:
    """Return [(lineno, text)] of executable Python lines: comments and docstrings gone."""
    tree = ast.parse(src)
    doc_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                d = body[0]
                doc_lines.update(range(d.lineno, (d.end_lineno or d.lineno) + 1))

    comment_lines = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            comment_lines.add(tok.start[0])

    out = []
    for i, text in enumerate(src.splitlines(), start=1):
        if i in doc_lines:
            continue
        if i in comment_lines:
            text = text.split("#", 1)[0]
        if text.strip():
            out.append((i, text))
    return out


def strip_shell(src: str) -> list:
    out = []
    for i, text in enumerate(src.splitlines(), start=1):
        stripped = text.strip()
        if stripped.startswith("#"):
            continue
        if stripped:
            out.append((i, text))
    return out


def enclosing_functions(src: str) -> dict:
    """line number -> name of the innermost enclosing function (or '<module>')."""
    tree = ast.parse(src)
    owner = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                owner[ln] = node.name
    return owner


def scan_lines(rel: str, lines: list, owner: dict | None = None) -> None:
    owner = owner or {}
    for lineno, text in lines:
        low = text.lower()
        for token in PROHIBITED_ABSOLUTE:
            if token in low:
                report(rel, lineno, f"prohibited command {token!r} in executable code: {text.strip()}")
        scrubbed = low
        for ident in ALLOWED_IDENTIFIERS:
            scrubbed = scrubbed.replace(ident.lower(), "")
        if owner.get(lineno) in REPORT_FUNCTIONS:
            continue  # report text may name what the job does not do
        for token in PROHIBITED_CONTEXTUAL:
            if token in scrubbed:
                report(rel, lineno,
                       f"prohibited token {token!r} outside the report writers "
                       f"(in {owner.get(lineno, '<module>')}): {text.strip()}")


# ---------------------------------------------------------------------------
def audit_python(rel: str) -> None:
    path = os.path.join(ROOT, rel)
    src = open(path, encoding="utf-8").read()
    scan_lines(rel, strip_python(src), enclosing_functions(src))
    tree = ast.parse(src)

    # 1. The remote template set is exactly the expected read-only set.
    templates = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "SERVER_READ_ONLY_COMMANDS" for t in node.targets):
            templates = ast.literal_eval(node.value)
    if templates is None:
        report(rel, 0, "SERVER_READ_ONLY_COMMANDS not found")
    else:
        if set(templates) != EXPECTED_TEMPLATE_KEYS:
            report(rel, 0, f"unexpected remote template keys: {sorted(set(templates) ^ EXPECTED_TEMPLATE_KEYS)}")
        for key, tpl in templates.items():
            if not ALLOWED_TEMPLATE_HEADS.match(tpl):
                report(rel, 0, f"remote template {key!r} is not a recognised read-only command: {tpl}")

    # 2. ssh is invoked from exactly one function, and only with a template.
    ssh_sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "ssh":
            ssh_sites.append(node.lineno)
    if len(ssh_sites) != 1:
        report(rel, 0, f"expected exactly one ssh invocation site, found {len(ssh_sites)}")

    # 3. No template may name a mutation, and none may name the cleanup hook — so the
    #    hook can be READ from a cron listing but can never be handed to the server.
    for key, tpl in (templates or {}).items():
        low = tpl.lower()
        for token in PROHIBITED_ABSOLUTE + PROHIBITED_CONTEXTUAL + ["w3_pgcache_cleanup"]:
            if token in low:
                report(rel, 0, f"remote template {key!r} contains {token!r}")

    # 3b. Exactly one subprocess call site, and it lives in the read-only ssh reader.
    subprocess_sites = [
        (n.lineno, owner)
        for owner, node in [(f.name, f) for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)]
        for n in ast.walk(node)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "run"
        and getattr(getattr(n.func, "value", None), "id", None) == "subprocess"
    ]
    if len(subprocess_sites) != 1 or subprocess_sites[0][1] != "run":
        report(rel, 0, f"expected exactly one subprocess.run inside SshReader.run, found {subprocess_sites}")

    # 3c. Exactly one place opens a network connection, and it is the public observation.
    open_sites = [
        (n.lineno, owner)
        for owner, node in [(f.name, f) for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)]
        for n in ast.walk(node)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "open"
        and getattr(getattr(n.func, "value", None), "id", None) == "opener"
    ]
    if len(open_sites) != 1 or open_sites[0][1] != "observe_public":
        report(rel, 0, f"expected exactly one outbound HTTP call inside observe_public, found {open_sites}")

    # 4. Files are opened for writing only inside the evidence writers.
    writers = {"write_evidence", "_write_manifest", "w"}
    for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for call in [c for c in ast.walk(func) if isinstance(c, ast.Call)]:
            name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
            if name != "open":
                continue
            mode = None
            if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
                mode = call.args[1].value
            for kw in call.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if mode and any(ch in mode for ch in "wax+") and func.name not in writers:
                report(rel, call.lineno, f"write-mode open() outside the evidence writers ({func.name})")

    # 5. The outbound request adds exactly two headers and no query string.
    for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        if func.name != "observe_public":
            continue
        adds = [c for c in ast.walk(func) if isinstance(c, ast.Call)
                and getattr(c.func, "attr", None) == "add_header"]
        if len(adds) != 2:
            report(rel, func.lineno, f"observe_public adds {len(adds)} request headers, expected exactly 2")
        for c in adds:
            hdr = c.args[0].value if c.args and isinstance(c.args[0], ast.Constant) else "?"
            if hdr not in ("User-Agent", "Accept"):
                report(rel, c.lineno, f"unexpected request header {hdr!r}")
        for c in ast.walk(func):
            if isinstance(c, ast.BinOp) and isinstance(c.op, ast.Add):
                report(rel, c.lineno, "string concatenation inside observe_public (possible URL tampering)")

    # 6. argparse exposes no action-shaped flag.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    low = a.value.lower()
                    if any(k in low for k in ("fix", "purge", "repair", "recover", "warm",
                                              "rebuild", "flush", "clear", "delete", "write")):
                        report(rel, node.lineno, f"action-shaped CLI flag {a.value!r}")


def audit_shell(rel: str) -> None:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        report(rel, 0, "expected runtime file is missing")
        return
    src = open(path, encoding="utf-8").read()
    lines = strip_shell(src)
    scan_lines(rel, lines)

    for lineno, text in lines:
        low = text.lower()
        mutating = any(v in low for v in ("rm ", "rm -", "chmod", "chown", "mv ", "touch ",
                                          "> ", ">>", "mkdir", "crontab -"))
        if mutating and any(p in low for p in SITE_PATHS):
            report(rel, lineno, f"local mutation references a live-site path: {text.strip()}")
        if "curl" in low or "wget" in low:
            report(rel, lineno, "the wrapper must not make its own HTTP request")


def main() -> int:
    for rel in RUNTIME_PY:
        audit_python(rel)
    for rel in RUNTIME_SH:
        audit_shell(rel)

    print("=== read-only audit of the noon cache monitor ===")
    print(f"audited: {', '.join(RUNTIME_PY + RUNTIME_SH)}")
    if findings:
        print(f"\nFAIL — {len(findings)} finding(s):")
        for f in findings:
            print(f"  {f}")
        return 1
    print("\nPASS — no purge, flush, invalidate, warm, rebuild, delete, cron-run,")
    print("       database-write, WordPress-write, cache-bypass or repair path exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

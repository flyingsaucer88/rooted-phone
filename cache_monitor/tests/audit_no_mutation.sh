#!/usr/bin/env bash
# Thin wrapper so the read-only audit can be run from a shell or from cron.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$(command -v python3 || command -v python)}"
exec "$PY" "$DIR/audit_no_mutation.py"

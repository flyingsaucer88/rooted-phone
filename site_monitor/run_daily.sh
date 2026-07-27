#!/data/data/com.termux/files/usr/bin/bash
# Daily site-monitor runner — PER-SITE PROCESSES (one fresh Python per site) so memory stays
# bounded on the low-RAM phone (a single all-sites process OOM-killed at ~700 pages). Each site is
# crawled in its own process writing per_site/<slug>/report_latest.json; a merge step then produces
# one combined report_latest.{json,md,html}. Invoked by the 10:00 cron path
# (seo_tracker/phone/run_site_monitor_daily.sh) and by run_once.sh.
#
# Job success = "ran and produced a combined report". Per-site ALERTs (broken pages, etc.) are
# findings, NOT job failures, so they never cause the watchdog to retry endlessly.
PREFIX="/data/data/com.termux/files/usr"
export PATH="$PREFIX/bin:$PREFIX/bin/applets:/system/bin:/system/xbin"
export HOME="/data/data/com.termux/files/home"
export LANG="en_US.UTF-8"

cd "$HOME/site_monitor" || exit 1
OUTDIR="${SITE_MONITOR_OUTDIR:-$HOME/site_monitor_reports}"
PER="$OUTDIR/per_site"
LOG="$OUTDIR/daily_runner.log"
mkdir -p "$PER"

echo "===== $(date '+%F %T %z') daily run start (per-site mode) =====" >> "$LOG"

# Enumerate sites as "slug<TAB>name" from the config (slug = host with dots -> underscores).
LIST="$(python - <<'PY'
import yaml
from urllib.parse import urlparse
c = yaml.safe_load(open("config/sites.yaml"))
for s in c.get("sites", []):
    slug = urlparse(s["base_url"]).netloc.replace(".", "_")
    print(f"{slug}\t{s['name']}")
PY
)"

order=""
while IFS="$(printf '\t')" read -r slug name; do
  [ -z "$slug" ] && continue
  order="${order:+$order,}$name"
  echo "----- $(date '+%F %T %z') site START: $name ($slug) -----" >> "$LOG"
  python run_site_monitor.py --config config/sites.yaml --only "$name" \
    --output-dir "$PER/$slug" --open-report false --no-notify >> "$LOG" 2>&1
  src=$?
  echo "----- $(date '+%F %T %z') site END:   $name (crawler rc=$src; alert=1 is a finding, not a job failure) -----" >> "$LOG"
done <<EOF
$LIST
EOF

# Merge all per-site reports into one combined report_latest.* in the main output dir.
python merge_reports.py --per-site-dir "$PER" --output-dir "$OUTDIR" --order "$order" >> "$LOG" 2>&1
mrc=$?

# One combined phone notification (detached: /dev/null fds so it can never hold the parent open).
if command -v termux-notification >/dev/null 2>&1; then
  SUM="$(python -c 'import json,render_report,sys; print(render_report.compact_summary(json.load(open(sys.argv[1]))))' "$OUTDIR/report_latest.json" 2>/dev/null)"
  termux-notification --id ambimat_site_monitor --title "Ambimat Site Monitor" \
    --content "${SUM:-daily run complete}" >/dev/null 2>&1 </dev/null || true
fi

echo "===== $(date '+%F %T %z') daily run end (merge rc=$mrc) =====" >> "$LOG"
# Exit reflects whether a combined report was produced, NOT whether findings exist.
exit "$mrc"

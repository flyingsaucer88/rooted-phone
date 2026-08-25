#!/data/data/com.termux/files/usr/bin/bash
# Rebuilds the consolidated result index (master prompt §19).
# Index only — never touches or overwrites the per-run evidence directories.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
. "${AMBIMAT_LIB_COMMON:-/data/data/com.termux/files/home/seo_tracker/phone/lib_common.sh}"
. "$DIR/lib_measure.sh"
mkdir -p "$MQ_EVIDENCE_ROOT" 2>/dev/null

MD="$MQ_EVIDENCE_ROOT/LATEST.md"; JS="$MQ_EVIDENCE_ROOT/LATEST.json"
{
  echo "# Scheduled measurement runs — index"; echo
  echo "Generated $(TZ=Asia/Kolkata date '+%F %T %z') (Asia/Kolkata). Index only; evidence lives in each run directory."
  echo
  echo "| Run | Intended Time | Actual Time | Status | Verdict | Evidence Directory |"
  echo "| --- | --- | --- | --- | --- | --- |"
} > "$MD"
while IFS=$'\t' read -r id due dep prompt_file label sources; do
  case "$id" in \#*|"") continue ;; esac
  printf '| %s | %s | %s | %s | %s | %s |\n' \
    "$label" "$(mq_get "$id" intended_ist "$due IST")" "$(mq_get "$id" actual_end "—")" \
    "$(mq_get "$id" status scheduled)" "$(mq_get "$id" verdict "—")" \
    "$(mq_get "$id" evidence_dir "—")" >> "$MD"
done < "$MQ_QUEUE_FILE"
{ echo; echo "Blackout dates (no measurement runs): \`$MQ_BLACKOUT_DATES\`"; } >> "$MD"

python - "$MQ_QUEUE_FILE" "$MQ_STATE_DIR" "$JS" "$MQ_BLACKOUT_DATES" <<'PY'
import json,os,sys
qf,sd,out,black = sys.argv[1:5]
def st(rid):
    p=os.path.join(sd,rid+".state"); d={}
    if os.path.exists(p):
        for ln in open(p):
            if "=" in ln: k,v=ln.rstrip("\n").split("=",1); d[k]=v
    return d
rows=[]
for ln in open(qf):
    if ln.startswith("#") or not ln.strip(): continue
    f=ln.rstrip("\n").split("\t")
    if len(f)<6: continue
    rid,due,dep,pf,label,src=f[:6]; s=st(rid)
    rows.append({"run_id":rid,"label":label,"intended_ist":s.get("intended_ist",due),
                 "actual_ist":s.get("actual_end"),"status":s.get("status","scheduled"),
                 "verdict":s.get("verdict"),"evidence_dir":s.get("evidence_dir"),
                 "depends_on":None if dep=="-" else dep,"required_sources":src.split(","),
                 "attempts_today":int(s.get("attempts","0")),"prompt_file":pf})
json.dump({"generated_ist":__import__("subprocess").check_output(
             ["date","+%FT%T%z"],env={**os.environ,"TZ":"Asia/Kolkata"}).decode().strip(),
           "blackout_dates":black.split(),"runs":rows}, open(out,"w"), indent=2)
PY

#!/data/data/com.termux/files/usr/bin/bash
# Builds the prompt-provenance manifest (master prompt §11). Proves which prompt
# version each scheduled run will use — or records that none was supplied.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
Q="$DIR/queue.tsv"; P="$DIR/prompts"; OUT="$P/MANIFEST.tsv"
{
  printf 'run_id\tlabel\tsource_filename\tsource_purpose\tsha256\tstored_path\tintended_execution\ttimezone\tstatus\n'
  while IFS=$'\t' read -r id due dep pf label sources; do
    case "$id" in \#*|"") continue ;; esac
    if [ -f "$P/$pf" ]; then
      sha="$(sha256sum "$P/$pf" | cut -d' ' -f1)"; sp="$P/$pf"; stt="STORED"
      [ -f "$P/TRUNCATION_NOTICE_${pf}" ] && stt="STORED_TRUNCATED"
    else
      sha="-"; sp="-"; stt="NOT_SUPPLIED"
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$id" "$label" "$pf" "$label measurement prompt" "$sha" "$sp" \
      "$(TZ=Asia/Kolkata date -d "$due" '+%FT%T%z' 2>/dev/null || echo "$due")" "Asia/Kolkata" "$stt"
  done < "$Q"
} > "$OUT"
column -t -s$'\t' "$OUT" 2>/dev/null || cat "$OUT"

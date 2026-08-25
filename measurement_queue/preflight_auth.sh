#!/data/data/com.termux/files/usr/bin/bash
# Authenticated-data-source preflight — standalone API mode.
#
# Replaces the browser-era probe.  The device is unrooted, has no automatable
# browser, and will have no Mac at 01:00 IST, so authenticated access now means
# API credentials on the phone, not a Chrome session.
#
# Still performs NO network requests: it inspects local credential readiness
# only, so it can never generate measurement traffic merely to test access.
#
# Usage: preflight_auth.sh <comma-separated-sources>
# Exit 0 = every CRITICAL source is available; 1 = a critical source is missing.
# Optional sources (bing, linkedin, serp, ai_overview) degrade the run per the
# master prompt's failure-degradation rule; they never block it.
set -u
REQ="${1:-}"
DIR="$(cd "$(dirname "$0")" && pwd)"
rc=0

# One python call reports every credential state; secrets are never printed.
STATES="$(cd "$DIR/api" && python3 - <<'PY' 2>/dev/null
import creds, json
print(json.dumps({k: v["state"] for k, v in creds.report().items()}))
PY
)"
[ -z "$STATES" ] && STATES='{}'
state_of() {
  printf '%s' "$STATES" | python3 -c "import json,sys;print(json.load(sys.stdin).get('$1','MISSING'))" 2>/dev/null || echo MISSING
}

GOOGLE="$(state_of google_sa)"
BING="$(state_of bing)"
LINKEDIN="$(state_of linkedin)"
ANTHROPIC="$(state_of anthropic)"

emit() { # <src> <critical|optional> <state> <reason>
  local src="$1" crit="$2" st="$3" why="$4"
  if [ "$st" = "PRESENT" ]; then
    echo "$src=AVAILABLE (api)"
  elif [ "$crit" = "optional" ]; then
    echo "$src=UNAVAILABLE_OPTIONAL ($why) — run continues, metric reported unavailable"
  else
    echo "$src=UNAVAILABLE ($why)"; rc=1
  fi
}

check() {
  case "$1" in
    gsc)      emit gsc      critical "$GOOGLE"    "Google service-account credential is $GOOGLE" ;;
    ga4)      emit ga4      critical "$GOOGLE"    "Google service-account credential is $GOOGLE" ;;
    bing)     emit bing     optional "$BING"      "Bing Webmaster API key is $BING" ;;
    linkedin) emit linkedin optional "$LINKEDIN"  "LinkedIn member-analytics token is $LINKEDIN" ;;
    serp)         echo "serp=UNAVAILABLE_OPTIONAL (no compliant standalone SERP source) — GSC is the ranking source of truth" ;;
    ai_overview)  echo "ai_overview=UNAVAILABLE_OPTIONAL (GOOGLE_AI_OVERVIEW = NOT AVAILABLE IN STANDALONE API MODE)" ;;
    *)            echo "$1=UNAVAILABLE (unknown source)"; rc=1 ;;
  esac
}

IFS=','; for s in $REQ; do [ -n "$s" ] && check "$s"; done; unset IFS
# The reasoning runtime is required by every gate regardless of the source list.
emit claude critical "$ANTHROPIC" "Anthropic API key is $ANTHROPIC"
exit $rc

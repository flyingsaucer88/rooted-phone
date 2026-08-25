#!/data/data/com.termux/files/usr/bin/bash
# Authenticated-data-source preflight (master prompt §12).
#
# Every one of the four queued measurement prompts needs authenticated,
# browser-or-API access to third-party analytics. This probe decides — at RUN
# time, not install time — whether that access exists. If it does not, the
# runner must emit BLOCKED rather than fabricate data (§12, §22).
#
# It performs NO network requests: it only inspects local capability, so it can
# never generate measurement traffic merely to test access (§12).
#
# Usage: preflight_auth.sh <comma-separated-sources>
# Exit 0 = all requested sources available; 1 = at least one unavailable.
# Prints one "<source>=AVAILABLE|UNAVAILABLE (<reason>)" line per source.
set -u
REQ="${1:-}"
rc=0

has_bin()  { command -v "$1" >/dev/null 2>&1; }
has_py()   { python -c "import $1" >/dev/null 2>&1; }
has_browser() { has_bin chromium || has_bin chromium-browser || has_bin google-chrome || has_bin chrome || has_bin firefox; }
has_driver()  { has_py selenium || has_py playwright || has_bin chromedriver || has_bin geckodriver; }
# A credential store the operator has deliberately provisioned. Never printed.
CRED_DIR="${AMBIMAT_MEASURE_CREDS:-$HOME/.ambimat_measure_creds}"
has_creds() { [ -d "$CRED_DIR" ] && [ -n "$(ls -A "$CRED_DIR" 2>/dev/null)" ]; }

check() {
  local src="$1" ok=1 reason=""
  case "$src" in
    gsc|ga4)
      if has_py googleapiclient && has_py google.oauth2 && has_creds; then ok=0
      elif has_browser && has_driver && has_creds; then ok=0
      else ok=1; reason="no Google API client + credentials, and no automatable authenticated browser"; fi ;;
    bing)
      if has_creds && { has_py requests_oauthlib || { has_browser && has_driver; }; }; then ok=0
      else ok=1; reason="no Bing Webmaster Tools credential path"; fi ;;
    linkedin)
      if has_browser && has_driver && has_creds; then ok=0
      else ok=1; reason="post-level analytics need an authenticated browser session"; fi ;;
    serp|ai_overview)
      if has_browser && has_driver; then ok=0
      else ok=1; reason="browser-visible SERP/AI Overview observation needs a real browser"; fi ;;
    *) ok=1; reason="unknown source" ;;
  esac
  if [ "$ok" -eq 0 ]; then echo "$src=AVAILABLE"; else echo "$src=UNAVAILABLE ($reason)"; rc=1; fi
}

IFS=','; for s in $REQ; do [ -n "$s" ] && check "$s"; done; unset IFS
exit $rc

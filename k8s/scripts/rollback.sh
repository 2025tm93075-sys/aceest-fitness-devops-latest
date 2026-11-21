#!/usr/bin/env bash
# One entry point to revert any strategy to the last stable version.
# Usage: ./rollback.sh <rolling|blue-green|canary|ab-test|shadow|all>
source "$(dirname "$0")/common.sh"
DIR="$(dirname "$0")"

case "${1:?usage: rollback.sh <strategy|all>}" in
  rolling)
    k rollout undo deployment/aceest-rolling
    k rollout status deployment/aceest-rolling --timeout="$ROLLOUT_TIMEOUT"
    ok "Rolling deployment reverted to $(current_tag aceest-rolling)" ;;
  blue-green) "$DIR/blue-green.sh" rollback ;;
  canary)     "$DIR/canary.sh" abort ;;
  ab-test)    "$DIR/ab-test.sh" end ;;
  shadow)     "$DIR/shadow.sh" stop ;;
  all)        for s in rolling blue-green canary ab-test shadow; do "$0" "$s" || true; done ;;
  *) fail "unknown strategy $1"; exit 2 ;;
esac

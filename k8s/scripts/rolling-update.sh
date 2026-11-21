#!/usr/bin/env bash
# Rolling update: replace pods one by one; undo automatically if the new
# version never becomes ready or fails the smoke tests.
# Usage: ./rolling-update.sh <tag>        e.g. ./rolling-update.sh v1.2.0
# Rollback drill: FAULT_INJECTION=health ./rolling-update.sh v1.2.0
#   The new pods report unhealthy, never become ready, the old pods keep
#   serving (maxUnavailable 0) and the script reverts to the stable revision.
source "$(dirname "$0")/common.sh"
require_image_repo
TAG="$(normalize_tag "${1:?usage: rolling-update.sh <tag>}")"
DEPLOY=aceest-rolling

log "Rolling update: $(current_tag $DEPLOY) -> $TAG"
set_image "$DEPLOY" "$TAG"
if [[ "${FAULT_INJECTION:-}" == health ]]; then
  log "FAULT_INJECTION=health: deploying a release whose health checks fail"
  k set env "deployment/$DEPLOY" FAULT_INJECTION=health
fi
rollout_or_undo "$DEPLOY" || exit 1

if ! smoke "http://aceest-rolling" "$TAG" rolling; then
  fail "Smoke tests failed on $TAG - undoing rollout"
  undo "$DEPLOY"
  k rollout status "deployment/$DEPLOY" --timeout="$ROLLOUT_TIMEOUT"
  exit 1
fi
k rollout history "deployment/$DEPLOY" | tail -5
ok "Rolling update to $TAG complete"

#!/usr/bin/env bash
# Rolling update: replace pods one by one; undo automatically if the new
# version never becomes ready or fails the smoke tests.
# Usage: ./rolling-update.sh <tag>        e.g. ./rolling-update.sh v1.2.0
source "$(dirname "$0")/common.sh"
require_image_repo
TAG="$(normalize_tag "${1:?usage: rolling-update.sh <tag>}")"
DEPLOY=aceest-rolling

log "Rolling update: $(current_tag $DEPLOY) -> $TAG"
set_image "$DEPLOY" "$TAG"
rollout_or_undo "$DEPLOY" || exit 1

if ! smoke "http://aceest-rolling" "$TAG" rolling; then
  fail "Smoke tests failed on $TAG - undoing rollout"
  k rollout undo "deployment/$DEPLOY"
  k rollout status "deployment/$DEPLOY" --timeout="$ROLLOUT_TIMEOUT"
  exit 1
fi
k rollout history "deployment/$DEPLOY" | tail -5
ok "Rolling update to $TAG complete"

#!/usr/bin/env bash
# Blue-green: deploy to the idle slot, test it through the preview Service,
# then switch the live Service selector in one step.
# Usage: ./blue-green.sh deploy <tag>   deploy + test idle slot, then switch
#        ./blue-green.sh switch         flip live <-> idle
#        ./blue-green.sh rollback       return live traffic to the previously live slot
#        ./blue-green.sh status
source "$(dirname "$0")/common.sh"

live_slot() { k get service aceest-bluegreen -o jsonpath='{.spec.selector.slot}'; }
previous_slot() { k get service aceest-bluegreen -o jsonpath='{.metadata.annotations.aceest/previous-slot}'; }
idle_slot() { [[ "$(live_slot)" == blue ]] && echo green || echo blue; }

point() {  # point <service> <slot>
  k patch service "$1" --type merge -p "{\"spec\":{\"selector\":{\"strategy\":\"blue-green\",\"slot\":\"$2\"}}}"
}

switch() {
  local from to; from="$(live_slot)"; to="$(idle_slot)"
  point aceest-bluegreen "$to"
  point aceest-bluegreen-preview "$from"
  k annotate service aceest-bluegreen aceest/previous-slot="$from" --overwrite >/dev/null
  ok "Live traffic: $from -> $to  (preview now shows $from)"
}

rollback() {
  local prev; prev="$(previous_slot)"
  if [[ -z "$prev" || "$prev" == "$(live_slot)" ]]; then
    log "No previous slot recorded - live stays on $(live_slot)"
    return 0
  fi
  switch
  ok "Rolled back to $prev ($(current_tag "aceest-$prev"))"
}

case "${1:-status}" in
  deploy)
    require_image_repo
    TAG="$(normalize_tag "${2:?usage: blue-green.sh deploy <tag>}")"
    IDLE="$(idle_slot)"
    log "Live slot: $(live_slot) ($(current_tag "aceest-$(live_slot)")). Deploying $TAG to idle slot: $IDLE"
    point aceest-bluegreen-preview "$IDLE"
    set_image "aceest-$IDLE" "$TAG"
    rollout_or_undo "aceest-$IDLE" || exit 1
    if ! smoke "http://aceest-bluegreen-preview" "$TAG" "$IDLE"; then
      fail "Idle slot $IDLE failed smoke tests - live traffic untouched; reverting $IDLE"
      undo "aceest-$IDLE"
      k rollout status "deployment/aceest-$IDLE" --timeout="$ROLLOUT_TIMEOUT" || true
      exit 1
    fi
    switch
    smoke "http://aceest-bluegreen" "$TAG" "$IDLE" || { fail "Live check failed - switching back"; switch; exit 1; }
    ;;
  switch)   switch ;;
  rollback) rollback ;;
  status) echo "live=$(live_slot) ($(current_tag "aceest-$(live_slot)"))  idle=$(idle_slot) ($(current_tag "aceest-$(idle_slot)"))" ;;
  *) fail "unknown command $1"; exit 2 ;;
esac

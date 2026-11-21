#!/usr/bin/env bash
# Canary release through NGINX ingress weights.
# Usage: ./canary.sh start <tag> [weight]   deploy canary, test it, send weight% (default 20)
#        ./canary.sh weight <0-100>         change the share of traffic
#        ./canary.sh promote                stable := canary version, canary weight 0
#        ./canary.sh abort                  rollback: weight 0, canary scaled to 0
#        ./canary.sh status
source "$(dirname "$0")/common.sh"
ING=aceest-canary-weighted

set_weight() {
  k annotate ingress "$ING" nginx.ingress.kubernetes.io/canary-weight="$1" --overwrite >/dev/null
  ok "Canary weight = $1%"
}

case "${1:-status}" in
  start)
    require_image_repo
    TAG="$(normalize_tag "${2:?usage: canary.sh start <tag> [weight]}")"
    WEIGHT="${3:-20}"
    set_weight 0
    k scale deployment/aceest-canary --replicas=1
    set_image aceest-canary "$TAG"
    rollout_or_undo aceest-canary || exit 1
    smoke "http://aceest-canary" "$TAG" canary || { fail "Canary failed smoke tests - aborting"; "$0" abort; exit 1; }
    set_weight "$WEIGHT"
    ;;
  weight) set_weight "${2:?usage: canary.sh weight <0-100>}" ;;
  promote)
    require_image_repo
    TAG="$(current_tag aceest-canary)"
    log "Promoting canary $TAG to stable"
    set_image aceest-stable "$TAG"
    rollout_or_undo aceest-stable || exit 1
    smoke "http://aceest-stable" "$TAG" stable || { fail "Promotion failed - reverting stable"; k rollout undo deployment/aceest-stable; exit 1; }
    set_weight 0
    ok "Stable now runs $TAG"
    ;;
  abort|rollback)
    set_weight 0
    k scale deployment/aceest-canary --replicas=0
    ok "Canary aborted; 100% of traffic on stable $(current_tag aceest-stable)"
    ;;
  status)
    echo "stable=$(current_tag aceest-stable) canary=$(current_tag aceest-canary)" \
         "weight=$(k get ingress $ING -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}')%"
    ;;
  *) fail "unknown command $1"; exit 2 ;;
esac

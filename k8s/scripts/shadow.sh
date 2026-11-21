#!/usr/bin/env bash
# Shadow deployment: production serves users, NGINX mirrors every request to
# the shadow release and discards its responses.
# Usage: ./shadow.sh deploy <tag>   start shadowing <tag>
#        ./shadow.sh compare        error counts, production vs shadow
#        ./shadow.sh promote        production := shadow version
#        ./shadow.sh stop           rollback: stop mirroring (shadow scaled to 0)
source "$(dirname "$0")/common.sh"

errors() { k logs -l "app=$1" --tail=-1 2>/dev/null | grep -cE '" 5[0-9]{2} ' || true; }
requests() { k logs -l "app=$1" --tail=-1 2>/dev/null | grep -cE '"(GET|POST|PUT|DELETE) ' || true; }

case "${1:-compare}" in
  deploy)
    require_image_repo
    TAG="$(normalize_tag "${2:?usage: shadow.sh deploy <tag>}")"
    k scale deployment/aceest-shadow --replicas=1
    set_image aceest-shadow "$TAG"
    rollout_or_undo aceest-shadow || exit 1
    smoke "http://aceest-shadow" "$TAG" shadow || { fail "Shadow failed smoke tests"; "$0" stop; exit 1; }
    ok "Shadow $TAG is receiving mirrored traffic (users still served by $(current_tag aceest-production))"
    ;;
  compare)
    for d in aceest-production aceest-shadow; do
      echo "$d ($(current_tag $d)): requests=$(requests $d) 5xx=$(errors $d)"
    done
    ;;
  promote)
    require_image_repo
    TAG="$(current_tag aceest-shadow)"
    set_image aceest-production "$TAG"
    rollout_or_undo aceest-production || exit 1
    smoke "http://aceest-production" "$TAG" production || { fail "Promotion failed - reverting production"; undo aceest-production; exit 1; }
    ok "Production now runs $TAG"
    ;;
  stop|rollback)
    k scale deployment/aceest-shadow --replicas=0
    ok "Shadow stopped; production unaffected"
    ;;
  *) fail "unknown command $1"; exit 2 ;;
esac

#!/usr/bin/env bash
# A/B testing: same release, UI variant A vs B, split at the ingress.
# Usage: ./ab-test.sh deploy <tag>        roll both variants to <tag> and test them
#        ./ab-test.sh split <percent-B>   e.g. 50
#        ./ab-test.sh end                 rollback / conclude: 100% variant A
#        ./ab-test.sh results             click-through on the variant B promo
source "$(dirname "$0")/common.sh"
ING=aceest-ab-variant-b

case "${1:-results}" in
  deploy)
    require_image_repo
    TAG="$(normalize_tag "${2:?usage: ab-test.sh deploy <tag>}")"
    for v in a b; do
      set_image "aceest-variant-$v" "$TAG"
      rollout_or_undo "aceest-variant-$v" || exit 1
      smoke "http://aceest-variant-$v" "$TAG" "variant-$v" || { fail "variant $v failed"; "$0" end; exit 1; }
    done
    ;;
  split)
    k annotate ingress "$ING" nginx.ingress.kubernetes.io/canary-weight="${2:?percent}" --overwrite >/dev/null
    ok "Variant B receives ${2}% of new visitors (cookie ab_variant=always forces B)"
    ;;
  end|rollback)
    k annotate ingress "$ING" nginx.ingress.kubernetes.io/canary-weight=0 --overwrite >/dev/null
    ok "A/B test ended - all traffic on variant A"
    ;;
  results)
    for v in a b; do
      views=$(k logs -l "app=aceest-variant-$v" --tail=-1 2>/dev/null | grep -c '"GET / ' || true)
      clicks=$(k logs -l "app=aceest-variant-$v" --tail=-1 2>/dev/null | grep -c 'ref=variant-b' || true)
      echo "variant ${v^^}: dashboard views=$views  promo clicks=$clicks"
    done
    ;;
  *) fail "unknown command $1"; exit 2 ;;
esac

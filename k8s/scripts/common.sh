#!/usr/bin/env bash
# Shared helpers for the ACEest deployment scripts. Source, don't execute.
#
# Required:  IMAGE_REPO   e.g. docker.io/<dockerhub-user>/aceest-fitness
# Optional:  NAMESPACE (aceest), ROLLOUT_TIMEOUT (150s), KUBECTL (kubectl)
set -euo pipefail

NAMESPACE="${NAMESPACE:-aceest}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-150s}"
KUBECTL="${KUBECTL:-kubectl}"
export K8S_DIR; K8S_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log()  { printf '\033[1;33m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
ok()   { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*" >&2; }
k()    { "$KUBECTL" -n "$NAMESPACE" "$@"; }

require_image_repo() {
  if [[ -z "${IMAGE_REPO:-}" ]]; then
    fail "IMAGE_REPO is not set (example: export IMAGE_REPO=docker.io/<dockerhub-user>/aceest-fitness)"
    exit 2
  fi
}

# Tags may be given as 1.2.0 or v1.2.0; images are tagged v1.2.0.
normalize_tag() { local t="$1"; [[ "$t" == v* || "$t" == latest || "$t" == *-* ]] && echo "$t" || echo "v$t"; }
# Version string the app reports (no leading v, no build suffix).
version_of()    { local t="${1#v}"; echo "${t%%-*}"; }

# Render a manifest template: substitute the image repository and tags.
render() {
  local file="$1"
  sed -e "s#__IMAGE_REPO__#${IMAGE_REPO}#g" \
      -e "s#__STABLE_TAG__#${STABLE_TAG:-v1.1.0}#g" \
      -e "s#__NEW_TAG__#${NEW_TAG:-v1.2.0}#g" "$file"
}

revision() { k get deployment "$1" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}'; }

# Remember the last stable revision of a Deployment before changing it.
mark_stable() { STABLE_REVISION="$(revision "$1")"; export STABLE_REVISION; }

# Revert to the remembered stable revision (or the previous one if unknown).
undo() {
  local deploy="$1"
  if [[ -n "${STABLE_REVISION:-}" ]]; then
    k rollout undo "deployment/${deploy}" --to-revision="$STABLE_REVISION"
  else
    k rollout undo "deployment/${deploy}"
  fi
}

# Wait for a Deployment to finish rolling out; on timeout undo it.
rollout_or_undo() {
  local deploy="$1"
  if k rollout status "deployment/${deploy}" --timeout="$ROLLOUT_TIMEOUT"; then
    ok "deployment/${deploy} rolled out"
  else
    fail "deployment/${deploy} did not become ready - rolling back to revision ${STABLE_REVISION:-previous}"
    undo "${deploy}"
    k rollout status "deployment/${deploy}" --timeout="$ROLLOUT_TIMEOUT" || true
    return 1
  fi
}

# Point a Deployment at a new image and record why (shows in rollout history).
set_image() {
  local deploy="$1" tag="$2"
  mark_stable "$deploy"
  k set image "deployment/${deploy}" "web=${IMAGE_REPO}:${tag}"
  k annotate "deployment/${deploy}" kubernetes.io/change-cause="deploy ${tag} (build ${BUILD_NUMBER:-manual})" --overwrite
}

current_tag() { k get deployment "$1" -o jsonpath='{.spec.template.spec.containers[0].image}' | sed 's#.*:##'; }

# Run the containerised Pytest smoke suite against a Service from inside the cluster.
smoke() { "$(dirname "${BASH_SOURCE[0]}")/smoke-test.sh" "$@"; }

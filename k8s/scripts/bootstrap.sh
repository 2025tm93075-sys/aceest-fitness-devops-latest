#!/usr/bin/env bash
# Create the namespace, secret and all five strategy environments.
# Usage: IMAGE_REPO=docker.io/<user>/aceest-fitness STABLE_TAG=v1.1.0 NEW_TAG=v1.2.0 ./bootstrap.sh
source "$(dirname "$0")/common.sh"
require_image_repo
STABLE_TAG="$(normalize_tag "${STABLE_TAG:-v1.1.0}")"
NEW_TAG="$(normalize_tag "${NEW_TAG:-v1.2.0}")"
export STABLE_TAG NEW_TAG

log "Namespace and secret"
render "$K8S_DIR/00-namespace.yaml" | "$KUBECTL" apply -f -
if ! k get secret aceest-secrets >/dev/null 2>&1; then
  k create secret generic aceest-secrets \
    --from-literal=secret-key="$(head -c 32 /dev/urandom | base64 | tr -d '=+/')" \
    --from-literal=admin-password="${ADMIN_PASSWORD:-$(head -c 12 /dev/urandom | base64 | tr -d '=+/')}"
  ok "secret aceest-secrets created"
fi

for f in 10-rolling-update 20-blue-green 30-canary 40-ab-testing 50-shadow; do
  log "Applying $f (stable=$STABLE_TAG new=$NEW_TAG)"
  render "$K8S_DIR/$f.yaml" | k apply -f -
done

for d in aceest-rolling aceest-blue aceest-green aceest-stable aceest-canary \
         aceest-variant-a aceest-variant-b aceest-production aceest-shadow; do
  rollout_or_undo "$d"
done
ok "All strategies are running"
"$(dirname "$0")/status.sh"

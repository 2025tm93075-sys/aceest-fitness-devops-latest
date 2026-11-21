#!/usr/bin/env bash
# Run the Pytest smoke suite INSIDE the cluster as a Job, using the test image.
# Usage: ./smoke-test.sh <service-url> [expected-tag] [expected-track]
#   e.g. ./smoke-test.sh http://aceest-canary v1.2.0 canary
# TEST_IMAGE: the test image of the CURRENT build (Jenkins sets it); defaults to
# ${IMAGE_REPO}-test:latest. The suite only uses endpoints present since v1.1.0,
# so the newest test image can validate older releases during a rollback.
source "$(dirname "$0")/common.sh"
URL="${1:?usage: smoke-test.sh <service-url> [tag] [track]}"
TAG="${2:-}"; TRACK="${3:-}"
VERSION="$( [[ -n "$TAG" ]] && version_of "$TAG" || true )"
TEST_IMAGE="${TEST_IMAGE:-${IMAGE_REPO}-test:latest}"
JOB="smoke-$(date +%s)-$RANDOM"

log "Smoke testing $URL (expect version='${VERSION:-any}' track='${TRACK:-any}') with $TEST_IMAGE"
sed -e "s#__JOB_NAME__#$JOB#" -e "s#__TEST_IMAGE__#$TEST_IMAGE#" -e "s#__TARGET_URL__#$URL#" \
    -e "s#__EXPECT_VERSION__#$VERSION#" -e "s#__EXPECT_TRACK__#$TRACK#" \
    "$K8S_DIR/jobs/smoke-test.yaml" | k apply -f - >/dev/null

# Wait for either completion or failure, whichever comes first.
for _ in $(seq 1 90); do
  succeeded=$(k get job "$JOB" -o jsonpath='{.status.succeeded}' 2>/dev/null || true)
  failed=$(k get job "$JOB" -o jsonpath='{.status.failed}' 2>/dev/null || true)
  [[ "${succeeded:-0}" -ge 1 || "${failed:-0}" -ge 1 ]] && break
  sleep 2
done
k logs "job/$JOB" --tail=40 || true
if [[ "${succeeded:-0}" -ge 1 ]]; then ok "Smoke tests passed for $URL"; else fail "Smoke tests failed for $URL"; exit 1; fi

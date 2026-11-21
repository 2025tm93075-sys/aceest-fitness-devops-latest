#!/usr/bin/env bash
# Build and push an image for every release tag (v1.0.0, v1.1.0, ...), so the
# Docker Hub repository holds all versions of the application.
# Usage: IMAGE_REPO=docker.io/<user>/aceest-fitness ./publish-all-versions.sh
# (run `docker login` first)
set -euo pipefail
: "${IMAGE_REPO:?set IMAGE_REPO=docker.io/<user>/aceest-fitness}"
ROOT="$(git rev-parse --show-toplevel)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
for tag in $(git -C "$ROOT" tag -l 'v*' --sort=v:refname); do
  echo "==> $tag"
  rm -rf "$WORK/src"; mkdir -p "$WORK/src"
  git -C "$ROOT" archive "$tag" | tar -x -C "$WORK/src"
  docker build -t "$IMAGE_REPO:$tag" \
    --build-arg APP_VERSION="${tag#v}" --build-arg VCS_REF="$(git -C "$ROOT" rev-list -n1 "$tag")" \
    --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$WORK/src"
  docker build --target test -t "$IMAGE_REPO-test:$tag" "$WORK/src"
  docker push "$IMAGE_REPO:$tag"
  docker push "$IMAGE_REPO-test:$tag"
done
latest="$(git -C "$ROOT" tag -l 'v*' --sort=v:refname | tail -1)"
docker tag "$IMAGE_REPO:$latest" "$IMAGE_REPO:latest" && docker push "$IMAGE_REPO:latest"
echo "Pushed all versions; latest -> $latest"

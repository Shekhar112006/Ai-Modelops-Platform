#!/usr/bin/env bash

set -Eeuo pipefail

if [[ "${1:-}" == "--help" && "$#" -eq 1 ]]; then
    cat <<'HELP'
Usage:
  ./scripts/check-and-deploy-release.sh
  ./scripts/check-and-deploy-release.sh --dry-run
  ./scripts/check-and-deploy-release.sh --help

Checks GitHub release tags against the image currently deployed to staging.
If a newer versioned GHCR image is available, normal mode delegates deployment
to scripts/deploy-staging.sh, which verifies image metadata, health, and
predictions before promotion.
HELP
    exit 0
fi

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SCRIPT="${PROJECT_ROOT}/scripts/deploy-staging.sh"
STAGING_CONTAINER="modelops-model-server-staging"
EXPECTED_REPOSITORY_URL="https://github.com/Shekhar112006/Ai-Modelops-Platform.git"
IMAGE_PREFIX="ghcr.io/shekhar112006/ai-modelops-model-server"

MODE="${1:-}"

if [[ "$#" -gt 1 || ( -n "$MODE" && "$MODE" != "--dry-run" ) ]]; then
    echo "Usage: $0 [--dry-run]" >&2
    exit 2
fi

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is required."
command -v git >/dev/null 2>&1 || fail "Git is required."
command -v flock >/dev/null 2>&1 || fail "flock is required."

docker info >/dev/null 2>&1 || fail "Docker daemon is not accessible."

REMOTE_URL="$(git -C "$PROJECT_ROOT" remote get-url origin)"
[[ "$REMOTE_URL" == "$EXPECTED_REPOSITORY_URL" ]] \
    || fail "Unexpected origin URL: ${REMOTE_URL}"

[[ -x "$DEPLOY_SCRIPT" ]] || fail "Deployment script is not executable."

# Prevent overlapping timer runs from initiating two deployments.
exec 9>"/tmp/ai-modelops-release-checker-${UID}.lock"
if ! flock -n 9; then
    echo "Another release check is already running; skipping."
    exit 0
fi

if ! docker container inspect "$STAGING_CONTAINER" >/dev/null 2>&1; then
    fail "Staging container is missing. Refusing automatic deployment."
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "$STAGING_CONTAINER")" != "true" ]]; then
    fail "Staging container is not running. Refusing automatic deployment."
fi

CURRENT_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$STAGING_CONTAINER")"
CURRENT_IMAGE_REGEX='^ghcr\.io/shekhar112006/ai-modelops-model-server:v?((0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*))$'

if [[ ! "$CURRENT_IMAGE" =~ $CURRENT_IMAGE_REGEX ]]; then
    fail "Staging image is not a recognized versioned GHCR image: ${CURRENT_IMAGE}"
fi

CURRENT_VERSION="${BASH_REMATCH[1]}"

echo "=== Release checker ==="
echo "Current staging version: ${CURRENT_VERSION}"

REMOTE_TAGS="$(git ls-remote --refs --tags "$REMOTE_URL" 'refs/tags/v*')" \
    || fail "Unable to query remote release tags."

LATEST_VERSION="$(
    printf '%s\n' "$REMOTE_TAGS" |
    while read -r _ ref; do
        if [[ "${ref:-}" =~ ^refs/tags/v((0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*))$ ]]; then
            printf '%s\n' "${BASH_REMATCH[1]}"
        fi
    done |
    sort -V |
    tail -n 1
)"

[[ -n "$LATEST_VERSION" ]] || fail "No valid semantic-version release tags found."

echo "Latest GitHub release:  ${LATEST_VERSION}"

if [[ "$LATEST_VERSION" == "$CURRENT_VERSION" ]]; then
    echo "No newer release. Staging is already current."
    exit 0
fi

HIGHEST_VERSION="$(
    printf '%s\n%s\n' "$CURRENT_VERSION" "$LATEST_VERSION" |
    sort -V |
    tail -n 1
)"

if [[ "$HIGHEST_VERSION" != "$LATEST_VERSION" ]]; then
    echo "Staging is ahead of the latest remote tag. Refusing a downgrade."
    exit 0
fi

RELEASE_IMAGE="${IMAGE_PREFIX}:${LATEST_VERSION}"

# A Git tag can appear before its publishing job finishes. Wait until the
# registry manifest is available; the next timer run can retry safely.
if ! docker buildx imagetools inspect "$RELEASE_IMAGE" >/dev/null 2>&1; then
    echo "Release ${LATEST_VERSION} exists, but its GHCR image is not available yet."
    echo "No deployment performed; a later check can retry."
    exit 0
fi

if [[ "$MODE" == "--dry-run" ]]; then
    echo "DRY RUN: would deploy ${RELEASE_IMAGE}"
    exit 0
fi

echo "Deploying validated release image: ${RELEASE_IMAGE}"
exec "$DEPLOY_SCRIPT" --image "$RELEASE_IMAGE"

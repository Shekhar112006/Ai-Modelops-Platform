#!/usr/bin/env bash

set -Eeuo pipefail

# ---------------------------------------------------------------------------
# AI ModelOps Platform - staging deployment
#
# Builds a versioned model-server image, validates a candidate deployment,
# promotes it to staging, and restores the previous container on failure.
#
# Default configuration can be overridden with environment variables.
# ---------------------------------------------------------------------------

show_help() {
    cat <<'HELP'
Usage:
  ./scripts/deploy-staging.sh
  ./scripts/deploy-staging.sh --image GHCR_IMAGE

Optional environment variables:
  MODEL_NAME              MLflow registered model name (default: demo-classifier)
  MODEL_VERSION           MLflow model version (default: 5)
  MLFLOW_TRACKING_URI     MLflow server URL
  STAGING_PORT            Final staging port (default: 8006)
  CANDIDATE_PORT          Temporary candidate port (default: 8007)
  HEALTH_ATTEMPTS         Health-check attempts (default: 30)

Without --image, the script builds the image specified by VERSION.
With --image, it pulls a semantic-versioned image from this project's
GHCR repository and verifies its version and source metadata.

Both modes validate a candidate's health and prediction before promotion.
The previous staging container is retained for recovery until verification.
HELP
}

IMAGE_OVERRIDE=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --help)
            show_help
            exit 0
            ;;
        --image)
            if [[ "$#" -lt 2 || -z "$2" || -n "$IMAGE_OVERRIDE" ]]; then
                echo "ERROR: --image requires exactly one image reference." >&2
                exit 2
            fi
            IMAGE_OVERRIDE="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unsupported argument: $1" >&2
            echo "Run with --help for usage." >&2
            exit 2
            ;;
    esac
done

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

VERSION="$(tr -d '\r\n' < VERSION)"
RELEASE_VERSION="${VERSION}"
IMAGE="ai-modelops-model-server:${VERSION}"

MODEL_NAME="${MODEL_NAME:-demo-classifier}"
MODEL_VERSION="${MODEL_VERSION:-5}"
MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://host.docker.internal:5000}"

STAGING_CONTAINER="modelops-model-server-staging"
CANDIDATE_CONTAINER="modelops-model-server-staging-candidate"
PREVIOUS_CONTAINER="modelops-model-server-staging-previous"

STAGING_PORT="${STAGING_PORT:-8006}"
CANDIDATE_PORT="${CANDIDATE_PORT:-8007}"
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-30}"

MLRUNS_CONTAINER_PATH="/home/shekhar/ai-modelops-platform/mlruns"

ORIGINAL_EXISTS=0
OLD_RENAMED=0
CUTOVER_STARTED=0
DEPLOY_SUCCEEDED=0

container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

# Only allow version-tagged images from this project's GHCR repository.
if [[ -n "$IMAGE_OVERRIDE" ]]; then
    GHCR_IMAGE_REGEX='^ghcr\.io/shekhar112006/ai-modelops-model-server:v?((0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*))$'

    if [[ ! "$IMAGE_OVERRIDE" =~ $GHCR_IMAGE_REGEX ]]; then
        fail "Unsupported image. Use a semantic-versioned tag from this project's GHCR repository."
    fi

    RELEASE_VERSION="${BASH_REMATCH[1]}"
    IMAGE="$IMAGE_OVERRIDE"
fi


# Restore the old container if promotion fails after cutover begins.
# This cleanup does not modify the original staging container during
# candidate testing.
cleanup() {
    local exit_code=$?
    trap - EXIT

    if container_exists "$CANDIDATE_CONTAINER"; then
        docker rm -f "$CANDIDATE_CONTAINER" >/dev/null 2>&1 || true
    fi

    if [[ "$CUTOVER_STARTED" -eq 1 && "$DEPLOY_SUCCEEDED" -eq 0 ]]; then
        echo "Deployment did not complete. Attempting recovery..." >&2

        if [[ "$OLD_RENAMED" -eq 1 ]]; then
            if container_exists "$STAGING_CONTAINER"; then
                docker rm -f "$STAGING_CONTAINER" >/dev/null 2>&1 || true
            fi

            if container_exists "$PREVIOUS_CONTAINER"; then
                if docker rename "$PREVIOUS_CONTAINER" "$STAGING_CONTAINER"; then
                    docker start "$STAGING_CONTAINER" >/dev/null || true
                    echo "Previous staging container restored." >&2
                else
                    echo "CRITICAL: Could not rename the previous container." >&2
                    echo "Inspect Docker containers manually." >&2
                fi
            else
                echo "CRITICAL: Previous container is missing; inspect Docker." >&2
            fi

        elif [[ "$ORIGINAL_EXISTS" -eq 1 ]]; then
            # The original may have been stopped before it could be renamed.
            if container_exists "$STAGING_CONTAINER"; then
                docker start "$STAGING_CONTAINER" >/dev/null 2>&1 || true
                echo "Checked recovery of the original staging container." >&2
            fi

        else
            # There was no original container to restore.
            if container_exists "$STAGING_CONTAINER"; then
                docker rm -f "$STAGING_CONTAINER" >/dev/null 2>&1 || true
            fi
        fi
    fi

    exit "$exit_code"
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or not on PATH."
command -v curl >/dev/null 2>&1 || fail "curl is required."
command -v python3 >/dev/null 2>&1 || fail "python3 is required."
docker info >/dev/null 2>&1 || fail "Docker daemon is not accessible."

[[ "$VERSION" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] \
    || fail "VERSION must be semantic MAJOR.MINOR.PATCH; found: ${VERSION}"

[[ "$MODEL_NAME" =~ ^[a-zA-Z0-9._-]+$ ]] \
    || fail "MODEL_NAME contains unsupported characters."

[[ "$MODEL_VERSION" =~ ^[1-9][0-9]*$ ]] \
    || fail "MODEL_VERSION must be a positive integer."

[[ "$STAGING_PORT" =~ ^[0-9]+$ ]] \
    && (( STAGING_PORT >= 1 && STAGING_PORT <= 65535 )) \
    || fail "STAGING_PORT must be between 1 and 65535."

[[ "$CANDIDATE_PORT" =~ ^[0-9]+$ ]] \
    && (( CANDIDATE_PORT >= 1 && CANDIDATE_PORT <= 65535 )) \
    || fail "CANDIDATE_PORT must be between 1 and 65535."

(( STAGING_PORT != CANDIDATE_PORT )) \
    || fail "Staging and candidate ports must be different."

[[ "$HEALTH_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] \
    || fail "HEALTH_ATTEMPTS must be a positive integer."

container_exists "$STAGING_CONTAINER" && ORIGINAL_EXISTS=1

# Do not destroy a previous rollback container left behind by an earlier run.
if container_exists "$PREVIOUS_CONTAINER"; then
    fail "Container '$PREVIOUS_CONTAINER' already exists. Inspect it before retrying."
fi

trap cleanup EXIT

echo "=== Staging deployment configuration ==="
echo "Platform version: ${VERSION}"
echo "Docker image:     ${IMAGE}"
echo "Registered model: ${MODEL_NAME}"
echo "Model version:    ${MODEL_VERSION}"
echo "Staging port:     ${STAGING_PORT}"
echo "Candidate port:   ${CANDIDATE_PORT}"

echo
if [[ -n "$IMAGE_OVERRIDE" ]]; then
    echo "=== Pulling requested GHCR image ==="
    docker pull "$IMAGE"
else
    echo "=== Building versioned local image ==="

    docker build \
        --build-arg PLATFORM_VERSION="${VERSION}" \
        -f model_server/Dockerfile \
        -t "${IMAGE}" \
        .
fi

IMAGE_VERSION="$(
    docker image inspect "${IMAGE}" \
        --format '{{ index .Config.Labels "org.opencontainers.image.version" }}'
)"

IMAGE_SOURCE="$(
    docker image inspect "${IMAGE}" \
        --format '{{ index .Config.Labels "org.opencontainers.image.source" }}'
)"

[[ "$IMAGE_VERSION" == "$RELEASE_VERSION" ]] \
    || fail "Image label '${IMAGE_VERSION}' does not match requested version '${RELEASE_VERSION}'."

[[ "$IMAGE_SOURCE" == "https://github.com/Shekhar112006/Ai-Modelops-Platform" ]] \
    || fail "Unexpected image source metadata: '${IMAGE_SOURCE}'."

echo "Image version verified: ${IMAGE_VERSION}"
echo "Image source verified: ${IMAGE_SOURCE}"

verify_health() {
    local port="$1"
    local container="$2"
    local response
    local attempt

    echo "Checking health on port ${port}..."

    for (( attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt++ )); do
        if response="$(
            curl -fsS --max-time 5 \
                "http://127.0.0.1:${port}/health" 2>/dev/null
        )" && printf '%s' "$response" |
            MODEL_NAME="$MODEL_NAME" MODEL_VERSION="$MODEL_VERSION" \
            python3 -c '
import json
import os
import sys

try:
    data = json.load(sys.stdin)
    valid = (
        data.get("status") == "healthy"
        and data.get("model_name") == os.environ["MODEL_NAME"]
        and str(data.get("model_version")) == os.environ["MODEL_VERSION"]
    )
except (json.JSONDecodeError, AttributeError):
    valid = False

sys.exit(0 if valid else 1)
'; then
            echo "Health check passed: ${response}"
            return 0
        fi

        echo "Waiting for health check (${attempt}/${HEALTH_ATTEMPTS})..."
        sleep 2
    done

    echo "Health check failed for container '${container}'." >&2
    docker logs --tail 80 "$container" >&2 || true
    return 1
}

verify_prediction() {
    local port="$1"
    local container="$2"
    local response

    echo "Running prediction smoke test on port ${port}..."

    if ! response="$(
        curl -fsS --connect-timeout 3 --max-time 30 \
            -X POST "http://127.0.0.1:${port}/predict" \
            -H 'Content-Type: application/json' \
            -d '{
                "features": [
                    0.5, 1.2, 3.4, 2.1, 0.8,
                    1.5, 2.7, 3.1, 0.9, 1.8
                ]
            }'
    )"; then
        echo "Prediction request failed for container '${container}'." >&2
        docker logs --tail 80 "$container" >&2 || true
        return 1
    fi

    if ! printf '%s' "$response" |
        MODEL_NAME="$MODEL_NAME" MODEL_VERSION="$MODEL_VERSION" \
        python3 -c '
import json
import os
import sys

try:
    data = json.load(sys.stdin)
    valid = (
        data.get("model_name") == os.environ["MODEL_NAME"]
        and str(data.get("model_version")) == os.environ["MODEL_VERSION"]
        and "prediction" in data
    )
except (json.JSONDecodeError, AttributeError):
    valid = False

sys.exit(0 if valid else 1)
'; then
        echo "Prediction response did not match the expected model." >&2
        echo "Response: ${response}" >&2
        return 1
    fi

    echo "Prediction smoke test passed: ${response}"
}

echo
echo "=== Starting candidate container ==="

# A stale candidate from an interrupted pre-promotion run is disposable.
if container_exists "$CANDIDATE_CONTAINER"; then
    docker rm -f "$CANDIDATE_CONTAINER" >/dev/null
fi

docker run -d \
    --name "$CANDIDATE_CONTAINER" \
    --restart no \
    -p "127.0.0.1:${CANDIDATE_PORT}:8000" \
    --add-host host.docker.internal:host-gateway \
    -e "MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI}" \
    -e "MODEL_NAME=${MODEL_NAME}" \
    -e "MODEL_VERSION=${MODEL_VERSION}" \
    -v "${PROJECT_ROOT}/mlruns:${MLRUNS_CONTAINER_PATH}:ro" \
    "$IMAGE"

verify_health "$CANDIDATE_PORT" "$CANDIDATE_CONTAINER"
verify_prediction "$CANDIDATE_PORT" "$CANDIDATE_CONTAINER"

echo
echo "=== Promoting validated candidate ==="

# The existing staging container is retained as the rollback container
# until the replacement passes health and prediction checks.
CUTOVER_STARTED=1

if [[ "$ORIGINAL_EXISTS" -eq 1 ]]; then
    docker stop --time 20 "$STAGING_CONTAINER" >/dev/null
    docker rename "$STAGING_CONTAINER" "$PREVIOUS_CONTAINER"
    OLD_RENAMED=1
fi

docker rm -f "$CANDIDATE_CONTAINER" >/dev/null

docker run -d \
    --name "$STAGING_CONTAINER" \
    --restart unless-stopped \
    -p "${STAGING_PORT}:8000" \
    --add-host host.docker.internal:host-gateway \
    -e "MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI}" \
    -e "MODEL_NAME=${MODEL_NAME}" \
    -e "MODEL_VERSION=${MODEL_VERSION}" \
    -v "${PROJECT_ROOT}/mlruns:${MLRUNS_CONTAINER_PATH}:ro" \
    "$IMAGE"

verify_health "$STAGING_PORT" "$STAGING_CONTAINER"
verify_prediction "$STAGING_PORT" "$STAGING_CONTAINER"

# The new staging deployment has passed both checks.
DEPLOY_SUCCEEDED=1

if container_exists "$PREVIOUS_CONTAINER"; then
    docker rm -f "$PREVIOUS_CONTAINER" >/dev/null
    echo "Previous container removed after successful verification."
fi

echo
echo "SUCCESS: Staging deployment completed."
echo "Version: ${RELEASE_VERSION}"
echo "Model:   ${MODEL_NAME}"
echo "Model version: ${MODEL_VERSION}"
echo "Endpoint: http://127.0.0.1:${STAGING_PORT}"

# Container Registry and Release Guide

## 1. Overview

The AI ModelOps Platform model-server image is published to GitHub
Container Registry (GHCR).

Registry image:

`ghcr.io/shekhar112006/ai-modelops-model-server`

Verified release: `0.1.1`

Published tags:

- `ghcr.io/shekhar112006/ai-modelops-model-server:0.1.1`
- `ghcr.io/shekhar112006/ai-modelops-model-server:v0.1.1`

Both tags were verified to reference the same image manifest.

## 2. Prerequisites

Running the model server requires Docker, a reachable MLflow tracking
and model registry server, the requested registered model version,
and access to its model artifacts.

The Docker image contains the serving application and its dependencies.
It does not include the MLflow database or all registered model artifacts.

## 3. Pull the release

```bash
docker pull ghcr.io/shekhar112006/ai-modelops-model-server:0.1.1
```

If the package is private, authenticate to GHCR with an account that has
permission to read the package.

## 4. Verify image metadata

```bash
docker image inspect \
  ghcr.io/shekhar112006/ai-modelops-model-server:0.1.1 \
  --format 'Title={{index .Config.Labels "org.opencontainers.image.title"}}
Source={{index .Config.Labels "org.opencontainers.image.source"}}
Version={{index .Config.Labels "org.opencontainers.image.version"}}'
```

Expected metadata:

- Title: `AI ModelOps Model Server`
- Source: `https://github.com/Shekhar112006/Ai-Modelops-Platform`
- Version: `0.1.1`

## 5. Run the release locally

The following example uses the local Ubuntu development environment.
It expects MLflow on port 5000 and model artifacts in `mlruns/`.

```bash
cd ~/ai-modelops-platform

docker run -d \
  --name modelops-model-server-ghcr-doc-test \
  --restart no \
  -p 127.0.0.1:8007:8000 \
  --add-host host.docker.internal:host-gateway \
  -e MLFLOW_TRACKING_URI=http://host.docker.internal:5000 \
  -e MODEL_NAME=demo-classifier \
  -e MODEL_VERSION=5 \
  -v "$PWD/mlruns:/home/shekhar/ai-modelops-platform/mlruns:ro" \
  ghcr.io/shekhar112006/ai-modelops-model-server:0.1.1
```

For another machine, configure the correct MLflow URL, network access,
artifact paths, model name, model version, and required credentials.

## 6. Verify health

```bash
curl -fsS http://127.0.0.1:8007/health
```

Expected response:

```json
{
  "status": "healthy",
  "model_name": "demo-classifier",
  "model_version": "5"
}
```

The health endpoint should return HTTP 200.

## 7. Verify predictions

```bash
curl -sS \
  -w '\nHTTP_STATUS: %{http_code}\n' \
  -X POST http://127.0.0.1:8007/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "features": [0.5, 1.2, 3.4, 2.1, 0.8, 1.5, 2.7, 3.1, 0.9, 1.8]
  }'
```

Verified example response:

```json
{
  "model_name": "demo-classifier",
  "model_version": "5",
  "prediction": [1]
}
```

Expected HTTP status: 200.

Verify both health and prediction before promoting an image.

## 8. Clean up the test container

After testing:

```bash
docker rm -f modelops-model-server-ghcr-doc-test
```

Do not remove the existing staging container as part of this cleanup.

## 9. Future release process

1. Update `VERSION`.
2. Run version and regression tests.
3. Commit and push the version change to `main`.
4. Confirm main-branch CI is green.
5. Create an annotated Git tag matching the version, such as `v0.1.2`.
6. Push the tag.
7. Confirm tag-triggered CI and image publication succeed.
8. Verify the published image tags and metadata.
9. Pull the image and test health and predictions.

For version `0.1.2`, the expected tags are:

- `ghcr.io/shekhar112006/ai-modelops-model-server:0.1.2`
- `ghcr.io/shekhar112006/ai-modelops-model-server:v0.1.2`

Never move or overwrite an existing release tag to publish a new version.

## 10. Verified release status

Release version: `0.1.1`

Release tag: `v0.1.1`

Registry: GitHub Container Registry

Verified checks:

- Both GHCR tags exist and reference the same image manifest.
- OCI source and version metadata match the repository and release.
- The pulled image loaded `demo-classifier` version 5.
- A prediction returned HTTP 200.
- The original staging service was restored and verified healthy.

Remote deployment triggered directly from GitHub Actions to the
staging machine remains a separate capability.

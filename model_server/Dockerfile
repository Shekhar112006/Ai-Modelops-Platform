FROM python:3.14-slim

ARG PLATFORM_VERSION=dev

LABEL org.opencontainers.image.title="AI ModelOps Model Server" \
      org.opencontainers.image.version="${PLATFORM_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY model_server/requirements.txt /app/model_server/requirements.txt

RUN pip install \
    --no-cache-dir \
    -r /app/model_server/requirements.txt

COPY VERSION /app/VERSION
COPY platform_version.py /app/platform_version.py

COPY model_server /app/model_server
COPY ml /app/ml

EXPOSE 8000

CMD ["uvicorn", "model_server.main:app", "--host", "0.0.0.0", "--port", "8000"]

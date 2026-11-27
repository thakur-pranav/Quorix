# syntax=docker/dockerfile:1
# Quorix API. Two stages: the builder has pip and the build cache; the runtime image only gets
# the finished virtualenv, the embedding model and the app code.

ARG PYTHON_VERSION=3.13

# --- builder ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# Requirements before code: this layer (the slow one) is reused until requirements.txt changes.
COPY requirements.txt .
# CPU-only torch first (~200 MB instead of ~2 GB of CUDA); sentence-transformers then reuses it.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# Bake the embedding model into the image: containers start without downloading 90 MB, and
# work with no network access to Hugging Face at all.
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# --- runtime ------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    ENVIRONMENT=production \
    UPLOAD_DIR=/app/data/uploads \
    PORT=8000

# A non-root user: if the app is ever compromised, it can't modify the image or the system.
# uid 1000 because Hugging Face Spaces runs containers as uid 1000; it owns /app/data.
RUN useradd --uid 1000 --home /app quorix

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf
WORKDIR /app
COPY --chown=quorix:quorix . .
RUN mkdir -p /app/data/uploads && chown -R quorix:quorix /app/data && chmod +x docker-start.sh

USER quorix
EXPOSE 8000

# No curl in slim images: the health check uses Python itself.
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"

CMD ["./docker-start.sh"]

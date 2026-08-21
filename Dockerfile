# --- stage 1: build the frontend ------------------------------------------
FROM node:22-alpine AS web

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- stage 2: runtime ------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VERBATIM_STORAGE_DIR=/data

WORKDIR /app

# Requirements first so a code change does not invalidate the dependency layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt chromadb

COPY verbatim/ ./verbatim/
COPY pyproject.toml README.md ./
COPY --from=web /web/dist ./web/dist

# The default embedding provider downloads a model on first use. Baking it into
# the image costs ~120MB and saves every container that cold start.
ARG PRELOAD_EMBEDDINGS=false
RUN if [ "$PRELOAD_EMBEDDINGS" = "true" ]; then \
      pip install --no-cache-dir sentence-transformers && \
      python -c "from sentence_transformers import SentenceTransformer; \
                 SentenceTransformer('BAAI/bge-small-en-v1.5')"; \
    fi

RUN useradd --create-home --uid 1001 verbatim && mkdir -p /data && chown -R verbatim /data /app
USER verbatim

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uvicorn", "verbatim.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

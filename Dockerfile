# ── Stage 1: build the React frontend ───────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --legacy-peer-deps
COPY frontend/ ./
# Outputs to /build/../frontend-dist = /frontend-dist relative to repo root.
# vite.config.ts sets build.outDir: '../frontend-dist'.
RUN npm run build

# ── Stage 2: Python application ─────────────────────────────────────────────
# Single image; the API and the worker run it with different commands.
# Builds for the host arch locally (x86) and is built for linux/arm64 in CI
# for the Oracle A1 (ARM) target via `docker buildx --platform linux/arm64`.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # InsightFace writes model files here; mount a volume to persist across restarts.
    INSIGHTFACE_HOME=/models

# libGL + libglib2.0 are required by OpenCV (opencv-python-headless).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Copy the built frontend from stage 1.
COPY --from=frontend-builder /frontend-dist ./frontend-dist

# Default command runs the API; compose overrides it for the worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

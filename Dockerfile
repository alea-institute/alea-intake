# Stage 1: Frontend build
FROM node:22-slim AS frontend-build
# Pin pnpm (lockfile is v9.0) so builds are reproducible — @latest drifts and can
# break a frozen install when a new pnpm major lands.
RUN corepack enable && corepack prepare pnpm@10.28.2 --activate
WORKDIR /app
# This is a pnpm workspace: the lockfile lives at the repo ROOT, not in frontend/.
# Copy the workspace manifests first so the frozen install layer is cacheable.
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY frontend/package.json ./frontend/
RUN pnpm install --frozen-lockfile
COPY frontend/ ./frontend/
RUN pnpm --filter alea-intake-frontend run build

# Stage 2: Backend
FROM python:3.12-slim AS backend

LABEL org.opencontainers.image.title="alea-intake" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="ALEA Intake - AI-powered legal intake system" \
      org.opencontainers.image.source="https://github.com/alea/alea-intake" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install system deps (curl for healthcheck, WeasyPrint C libs, Tesseract OCR)
# WeasyPrint needs: pango, cairo, gdk-pixbuf, gobject, glib, fontconfig
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpango-1.0-0 libharfbuzz0b libfontconfig1 \
    libcairo2 libgdk-pixbuf-2.0-0 \
    libglib2.0-0 libffi8 \
    tesseract-ocr \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install uv via the official binary installer (bypasses flaky PyPI on
# constrained build networks; pip-install of uv has timed out repeatedly).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
RUN uv sync --no-dev
COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create data directory for SQLite and uploads
RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

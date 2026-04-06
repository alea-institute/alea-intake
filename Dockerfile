# Stage 1: Frontend build
FROM node:22-slim AS frontend-build
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY frontend/ ./
RUN pnpm build

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

RUN pip install uv
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

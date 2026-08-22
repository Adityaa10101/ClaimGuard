# ──────────────────────────────────────────────────────────
# ClaimGuard — Unified Container Image
# ──────────────────────────────────────────────────────────
# Single image used by both the FastAPI API and Streamlit UI
# services. The entrypoint/command is set per-service in
# docker-compose.yml.
#
# Build:  docker compose build
# Run:    docker compose up -d
# ──────────────────────────────────────────────────────────

FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ src/
COPY api/ api/
COPY data/ data/
COPY app.py .
COPY .streamlit/ .streamlit/
COPY assets/ assets/

# Create non-root user for runtime
RUN useradd --create-home --shell /bin/bash claimguard
USER claimguard

# Expose both service ports (informational)
EXPOSE 8000 8501

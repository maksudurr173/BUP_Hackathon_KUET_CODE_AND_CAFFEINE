# ==============================================================================
# GridWise Backend - Production Multi-Stage Containerfile
# Runs securely as a non-privileged system user with healthcheck enabled
# ==============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

# Create non-root user and group
RUN groupadd -r gridwise && useradd -r -g gridwise -d /app -s /sbin/nologin gridwise

# Copy installed wheels from builder
COPY --from=builder /root/.local /home/gridwise/.local
COPY . /app

# Ensure correct file permissions
RUN chown -R gridwise:gridwise /app /home/gridwise

ENV PATH="/home/gridwise/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8000

USER gridwise

EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Start production server
CMD ["uvicorn", "gridwise.app.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]

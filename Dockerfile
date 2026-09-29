# syntax=docker/dockerfile:1

# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Install the package with postgres and tracing extras into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[postgres,tracing]"

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd --system dcc && useradd --system --gid dcc --home /app dcc

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
WORKDIR /app
COPY --chown=dcc:dcc src ./src
COPY --chown=dcc:dcc ui ./ui
COPY --chown=dcc:dcc database ./database
COPY --chown=dcc:dcc scripts ./scripts
COPY --chown=dcc:dcc tracing ./tracing
COPY --chown=dcc:dcc pyproject.toml ./

# Switch to non-root user
USER dcc

# Environment configuration
ENV DCC_DATABASE_URL="" \
    DCC_TRACING_ENABLED="false" \
    DCC_OTLP_ENDPOINT="http://localhost:4317" \
    DCC_JAEGER_ENDPOINT="http://localhost:14250" \
    DCC_SERVICE_NAME="data-center-commander" \
    DCC_TRACE_SAMPLE_RATE="1.0" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose the application port
EXPOSE 8790

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://127.0.0.1:8790/healthz || exit 1

# Run the application
ENTRYPOINT ["python", "scripts/run-local.py"]
CMD ["--host", "0.0.0.0", "--port", "8790"]

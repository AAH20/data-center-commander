# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir psycopg[binary,pool]

# Copy source
COPY src/ src/
COPY scripts/ scripts/
COPY ui/ ui/

EXPOSE 8790

CMD ["python", "scripts/run-local.py", "--host", "127.0.0.1", "--port", "8790"]

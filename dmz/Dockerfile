# DMZ Dockerfile
# ============================================================================
# Runs: uvicorn dmz.main:app --host 0.0.0.0 --port 8001
# Secrets: injected via Doppler at runtime.
# ============================================================================

FROM python:3.12.3-slim-bookworm

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy DMZ source
COPY dmz/ ./dmz/

# Copy src/ modules used by DMZ (instantly_client)
COPY src/ ./src/

# Non-root user
RUN useradd -m -u 1001 dmzuser
USER dmzuser

EXPOSE 8001

CMD ["uvicorn", "dmz.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]

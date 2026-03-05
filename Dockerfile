# Agency-in-a-Box — Main Worker Dockerfile
# ============================================================================
# Runs: python -m src  (starts worker + alert poller)
# Secrets: injected via Doppler at runtime — no .env files in this image.
# ============================================================================

FROM python:3.12.3-slim-bookworm

WORKDIR /app

# Install OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (pinned in requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/

# Non-root user for principle of least privilege
RUN useradd -m -u 1001 worker
USER worker

# Entry point: runs __main__.py (worker loop + alert poller)
CMD ["python", "-m", "src"]

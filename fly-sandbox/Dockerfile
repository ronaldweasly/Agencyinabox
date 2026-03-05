# fly-sandbox/Dockerfile
# ============================================================================
# Disposable Firecracker microVM image for AI-generated code QA.
#
# P-14 fix: Pin base image to bookworm (not just slim) so system package
#           versions are reproducible. Don't pin wget itself (system tool).
# ============================================================================

FROM python:3.12.3-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Pre-install testing tools with pinned versions
RUN pip install --no-cache-dir \
    pytest==8.2.2 \
    pytest-cov==5.0.0 \
    pytest-json-report==1.5.0 \
    bandit==1.7.9 \
    ruff==0.4.9 \
    mypy==1.10.0

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Non-root user for additional isolation
RUN useradd -m -u 1001 sandbox
USER sandbox

ENTRYPOINT ["/entrypoint.sh"]

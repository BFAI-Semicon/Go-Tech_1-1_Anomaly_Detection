# LeadersBoard API Dockerfile (Multi-stage)

# =============================================================================
# Base Stage - Common dependencies
# =============================================================================
FROM python:3.13-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Development Stage - Additional dev tools
# =============================================================================
FROM base AS dev

# Create vscode user (UID 1000 for host compatibility)
# Note: python:3.13-slim is based on Debian Bookworm, no default UID 1000 user
RUN useradd --create-home --shell /bin/bash --uid 1000 --gid 0 vscode && \
    mkdir -p /app && \
    chown -R vscode:root /app

# Install development system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    git \
    openssh-client \
    sudo \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add vscode to sudoers (passwordless)
RUN echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Install development Python dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Source code is mounted via volume in development
# Working directory for development
WORKDIR /app/LeadersBoard

# Switch to vscode user
USER vscode

# =============================================================================
# Production Stage - Minimal runtime
# =============================================================================
FROM base AS prod

# Copy application code
COPY src/ ./src/

# Run as non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Expose API port
EXPOSE 8010

# Start API server
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8010"]

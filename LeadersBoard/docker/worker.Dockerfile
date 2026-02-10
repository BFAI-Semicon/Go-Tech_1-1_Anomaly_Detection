# LeadersBoard Worker Dockerfile (GPU)
# Uses CUDA 12.6 (compatible with anomalib cu124 extra)

FROM nvcr.io/nvidia/pytorch:25.11-py3

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    	git \
        libgl1 \
        libglib2.0-0 \
        git-lfs && \
    git lfs install --system && \
    rm -rf /var/lib/apt/lists/*

# Configure matplotlib cache directory
ENV MPLCONFIGDIR=/tmp/mplconfig
# Ensure our local src is first on module search path
ENV PYTHONPATH=/app/src

# Install Python dependencies
COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt

# Build arguments for user ID/GID (for mounted volume permissions)
ARG APP_UID=1000
ARG APP_GID=1000

# Copy application code
COPY src/ ./src/

# Run as non-root user with configurable UID/GID
# Use existing group/user if GID/UID already exists in base image
RUN (getent group ${APP_GID} || groupadd --gid ${APP_GID} appgroup) && \
    (getent passwd ${APP_UID} || useradd --create-home --shell /bin/bash --uid ${APP_UID} --gid ${APP_GID} appuser) && \
    mkdir -p /tmp/mplconfig && \
    chmod 777 /tmp/mplconfig
USER ${APP_UID}

# Start worker
CMD ["python", "-m", "src.worker.main"]

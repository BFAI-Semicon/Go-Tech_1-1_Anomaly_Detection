# LeadersBoard Worker Dockerfile (GPU)
# Uses CUDA 12.6 (compatible with anomalib cu124 extra)

FROM nvcr.io/nvidia/pytorch:24.12-py3

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
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

# Copy application code
COPY src/ ./src/

# Run as non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /tmp/mplconfig && \
    chmod 777 /tmp/mplconfig
USER appuser

# Start worker
CMD ["python", "-m", "src.worker.main"]

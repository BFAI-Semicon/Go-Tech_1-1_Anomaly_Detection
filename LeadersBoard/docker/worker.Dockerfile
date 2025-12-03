# LeadersBoard Worker Dockerfile (GPU)

FROM nvcr.io/nvidia/pytorch:25.11-py3

WORKDIR /app

# Install Python dependencies
COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt

# Copy application code
COPY src/ ./src/

# Run as non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Start worker
CMD ["python", "-m", "src.worker.main"]

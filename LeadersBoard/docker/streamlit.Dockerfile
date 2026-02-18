FROM python:3.13-slim

WORKDIR /app

# Build arguments for user ID/GID (for mounted volume permissions)
ARG APP_UID=1000
ARG APP_GID=1000

# Streamlit UI dependencies
RUN pip install --no-cache-dir streamlit>=1.40.0 requests>=2.32.0

COPY src/ ./src/

# Run as non-root user with configurable UID/GID
# Use existing group/user if GID/UID already exists in base image
RUN (getent group ${APP_GID} || groupadd --gid ${APP_GID} appgroup) && \
    (getent passwd ${APP_UID} || useradd --create-home --shell /bin/bash --uid ${APP_UID} --gid ${APP_GID} appuser)
USER ${APP_UID}

ENV API_URL=http://api:8010 \
    MLFLOW_URL=/mlflow

EXPOSE 8501

CMD ["streamlit", "run", "src/streamlit/app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.baseUrlPath", "/streamlit/"]

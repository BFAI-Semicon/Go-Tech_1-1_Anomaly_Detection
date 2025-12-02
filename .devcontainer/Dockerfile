FROM mcr.microsoft.com/devcontainers/python:2.0.2-3.13-bookworm
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm

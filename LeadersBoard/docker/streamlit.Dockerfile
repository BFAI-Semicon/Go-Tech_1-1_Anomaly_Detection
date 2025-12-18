FROM python:3.13-slim

WORKDIR /app

# Streamlit UI dependencies
RUN pip install --no-cache-dir streamlit>=1.40.0 requests>=2.32.0

COPY src/ ./src/

ENV API_URL=http://api:8010 \
    MLFLOW_URL=http://mlflow:5010

EXPOSE 8501

CMD ["streamlit", "run", "src/streamlit/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]

# Multi-stage Dockerfile for cloud deployment
# Deploys the full chatbot (backend + frontend) as a single container
# Works on Railway, Render, Fly.io, or any container platform
#
# The frontend is served by FastAPI on the same port, so you only
# need one container and one URL. No separate frontend deployment needed.

FROM python:3.11-slim

WORKDIR /app

# Install system deps for faiss-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY frontend/ frontend/

# The app reads .env but also supports OS-level env vars,
# which is how Railway/Render inject secrets
ENV PYTHONPATH=/app

EXPOSE 8000

# Uvicorn with 0.0.0.0 binding for container networking
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

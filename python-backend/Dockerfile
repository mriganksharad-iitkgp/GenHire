FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies (if you add OS-level deps later, extend this)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY python-backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY python-backend/ /app

# Cloud Run listens on $PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

# Use gunicorn with eventlet for Flask-SocketIO
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app", "--worker-class", "eventlet", "--workers", "1"]


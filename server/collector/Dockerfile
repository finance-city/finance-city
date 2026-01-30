# Dockerfile - Data Collector Service  
FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd --create-home --shell /bin/bash collector

# Copy application code
COPY . .
RUN chown -R collector:collector /app

USER collector

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import redis; r=redis.Redis(host='redis'); r.ping()" || exit 1

CMD ["python", "src/collector.py"]

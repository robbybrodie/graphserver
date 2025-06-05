FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY github_etl.py .
COPY config/ ./config/

# Create non-root user
RUN useradd -m -u 1001 etl-user && chown -R etl-user:etl-user /app
USER etl-user

CMD ["python", "github_etl.py"]

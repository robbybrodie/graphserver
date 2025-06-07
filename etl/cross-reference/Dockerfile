FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the ETL script
COPY cross_ref_etl.py .

# Create config directory
RUN mkdir -p /app/config

# Run as non-root user
RUN useradd -m -u 1001 etluser
USER etluser

CMD ["python", "cross_ref_etl.py"]

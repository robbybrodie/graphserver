FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY jira_github_etl.py .
COPY config.yaml .

# Create log directory
RUN mkdir -p /var/log

# Create non-root user
RUN useradd -m -u 1000 etluser && chown -R etluser:etluser /app /var/log
USER etluser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "jira_github_etl.py", "config.yaml"]

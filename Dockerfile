# Use Python 3.11+ as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

ENV TZ=Asia/Jakarta

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python source code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Expose the default MCP HTTP port
EXPOSE 48080

# Set default environment variables
ENV MCP_PORT=48080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:48080/health').read()" || exit 1

# Run the Python MCP HTTP server
CMD ["python", "server.py"]

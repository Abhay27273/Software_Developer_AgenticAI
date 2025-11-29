# Dockerfile for WebSocket Handler
# Optimized for ECS Fargate deployment with Corporate Proxy Support

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# 1. Install system dependencies including ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. COPY the cert to the system store location
COPY trusted_certs.crt /usr/local/share/ca-certificates/corporate.crt

# 3. RUN the update command to merge certificates
RUN update-ca-certificates

# 4. Point Python/Pip to the MERGED system bundle (not just the single file)
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .

# Create non-root user
RUN useradd -m -u 1000 wsuser && \
    chown -R wsuser:wsuser /app

# Switch to non-root user
USER wsuser

# Expose WebSocket port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 8080)); s.close()" || exit 1

# Run the server
CMD ["python", "server.py"]
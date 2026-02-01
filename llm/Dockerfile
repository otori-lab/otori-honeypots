FROM python:3.11-slim

WORKDIR /app

# Copy source code and config
COPY src/ /app/src/
COPY config/ /app/config/
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create logs directory
RUN mkdir -p /app/logs

# Port SSH
EXPOSE 2222

# Default environment variables
ENV OLLAMA_URL="http://host.docker.internal:11434/api/generate"
ENV OLLAMA_MODEL="mistral:latest"
ENV SSH_PORT="2222"
ENV FAKE_USER="admin"
ENV FAKE_PASS="admin123"
ENV FAKE_HOSTNAME="srv-prod-01"
ENV LOG_DIR="/app/logs"
ENV HOSTKEY_PATH="/app/hostkey_rsa"

# Working directory for src
WORKDIR /app/src

# Start the honeypot
CMD ["python", "honeypot_ssh.py"]

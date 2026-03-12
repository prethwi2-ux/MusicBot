FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libavformat-dev \
    libavdevice-dev \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirement files first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure directory for database/downloads exists
RUN mkdir -p /app/downloads

# Environment defaults (can be overridden by Railway)
ENV DOWNLOAD_DIR=/app/downloads
ENV PYTHONUNBUFFERED=1

# Final command to run the bot
CMD ["python", "main.py"]

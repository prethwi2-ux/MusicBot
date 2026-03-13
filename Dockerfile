# Use Python 3.13 (Railway/Linux compatible)
FROM python:3.13-slim-bookworm

# Install system dependencies
# ffmpeg is REQUIRED for PyTgCalls to stream audio/video
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Run the bot
CMD ["python", "main.py"]

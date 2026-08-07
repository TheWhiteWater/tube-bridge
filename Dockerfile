FROM python:3.12-slim

WORKDIR /app

# Install system deps for yt-dlp
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
RUN pip install --no-cache-dir \
    mcp==1.28.1 \
    yt-dlp \
    youtube-transcript-api \
    starlette \
    uvicorn

# Copy server
COPY server.py .

# Run as HTTP/SSE server
CMD ["python3", "server.py", "--http", "--port", "8080", "--host", "0.0.0.0"]

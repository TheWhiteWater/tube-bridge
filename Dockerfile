FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir mcp==1.28.1 yt-dlp youtube-transcript-api starlette uvicorn sqlite-vec fastembed

COPY . .

CMD ["python3", "server.py", "--http", "--port", "8080"]

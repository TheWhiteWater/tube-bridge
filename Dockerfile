FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-release.txt /app/requirements-release.txt
RUN pip install --no-cache-dir --require-hashes -r /app/requirements-release.txt

COPY . .
RUN pip install --no-cache-dir --no-deps .

CMD ["tube-bridge", "--http", "--host", "0.0.0.0", "--port", "8080"]

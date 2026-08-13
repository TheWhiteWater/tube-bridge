FROM python:3.12-slim

LABEL io.modelcontextprotocol.server.name="io.github.TheWhiteWater/tube-bridge"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-release.txt /app/requirements-release.txt
RUN pip install --no-cache-dir --require-hashes -r /app/requirements-release.txt

COPY LICENSE README.md pyproject.toml /app/
COPY tube_bridge /app/tube_bridge
RUN pip install --no-cache-dir --no-deps . \
    && rm -rf /app/build /app/tube_bridge.egg-info

CMD ["tube-bridge", "--http", "--host", "0.0.0.0", "--port", "8080"]

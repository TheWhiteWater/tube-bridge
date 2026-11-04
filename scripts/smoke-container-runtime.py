"""Run through stdin inside the built image, never COPY into /app."""

import io
import math
import platform
import sqlite3
import subprocess
import sys
import tempfile

import numpy as np
import onnxruntime as ort
import sqlite_vec
from fastembed import TextEmbedding
from PIL import Image

expected = {"amd64": "x86_64", "arm64": "aarch64"}[sys.argv[1]]
assert platform.machine() == expected, (platform.machine(), expected)
assert "CPUExecutionProvider" in ort.get_available_providers()

with tempfile.TemporaryDirectory(prefix="tube-bridge-native-smoke-") as cache:
    # Exercise real ONNX CPU inference; importing fastembed alone is insufficient.
    model = TextEmbedding(
        model_name="BAAI/bge-small-en-v1.5",
        cache_dir=cache,
        threads=2,
        providers=["CPUExecutionProvider"],
    )
    vectors = list(model.embed(["Raspberry Pi ARM64 compatibility check"]))
    assert len(vectors) == 1 and len(vectors[0]) == 384
    vector = [float(v) for v in vectors[0]]
    assert all(math.isfinite(v) for v in vector)
    assert np.linalg.norm(vector) > 0

    # Load and execute the architecture-specific SQLite extension.
    with sqlite3.connect(":memory:") as conn:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("CREATE VIRTUAL TABLE smoke USING vec0(embedding float[384])")
        packed = sqlite_vec.serialize_float32(vector)
        conn.execute("INSERT INTO smoke(rowid, embedding) VALUES (1, ?)", (packed,))
        row = conn.execute(
            "SELECT rowid, distance FROM smoke WHERE embedding MATCH ? AND k=1",
            (packed,),
        ).fetchone()
        assert row is not None and row[0] == 1 and abs(row[1]) < 1e-4, row

    # Generate H.264 locally, then decode and scale to a JPEG: no YouTube dependency.
    clip = f"{cache}/clip.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=128x96:r=5",
        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", clip,
    ], check=True, timeout=60)
    jpeg = subprocess.run([
        "ffmpeg", "-v", "error", "-i", clip, "-frames:v", "1",
        "-vf", "scale=64:-1", "-f", "image2pipe", "-vcodec", "mjpeg", "-",
    ], check=True, capture_output=True, timeout=60).stdout
    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.format == "JPEG" and image.size == (64, 48)
        image.load()

print(f"Native runtime smoke passed: {expected}")

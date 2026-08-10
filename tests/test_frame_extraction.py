"""Frozen contract for bounded timestamp-based YouTube frame extraction."""

import hashlib
import os
import signal
import subprocess
from pathlib import Path

import pytest

from tube_bridge.youtube import frame as frame_module
from tube_bridge.youtube.frame import FrameExtractionError, extract_frame


JPEG = b"\xff\xd8frame-bytes\xff\xd9"


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group contract")
def test_process_timeout_kills_the_entire_process_group(monkeypatch):
    class TimedOutProcess:
        pid = 4242
        returncode = -signal.SIGKILL

        def __init__(self):
            self.communicate_calls = 0

        def communicate(self, _input=None, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(["yt-dlp"], timeout)
            return "", ""

    process = TimedOutProcess()
    popen_kwargs = {}
    killed = []

    def fake_popen(_command, **kwargs):
        popen_kwargs.update(kwargs)
        return process

    monkeypatch.setattr(frame_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(frame_module.os, "killpg", lambda pid, sig: killed.append((pid, sig)))

    with pytest.raises(subprocess.TimeoutExpired):
        frame_module._run_process(
            ["yt-dlp"], capture_output=True, check=False, text=True, timeout=0.1
        )

    assert popen_kwargs["start_new_session"] is True
    assert killed == [(4242, signal.SIGKILL)]
    assert process.communicate_calls == 2


def test_windows_timeout_uses_bounded_taskkill_tree(monkeypatch):
    class TimedOutProcess:
        pid = 5252
        returncode = 1

        def __init__(self):
            self.communicate_calls = 0

        def communicate(self, _input=None, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(["yt-dlp"], timeout)
            assert timeout == 5.0
            return b"", b""

    process = TimedOutProcess()
    popen_kwargs = {}
    tree_kills = []

    def fake_popen(_command, **kwargs):
        popen_kwargs.update(kwargs)
        return process

    def fake_taskkill(command, **kwargs):
        tree_kills.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(frame_module, "os", type("FakeOS", (), {"name": "nt"})())
    monkeypatch.setattr(frame_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(frame_module.subprocess, "run", fake_taskkill)

    with pytest.raises(subprocess.TimeoutExpired):
        frame_module._run_process(
            ["yt-dlp"], capture_output=True, check=False, timeout=0.1
        )

    assert popen_kwargs["creationflags"] == 0x00000200
    assert tree_kills[0][0] == ["taskkill", "/PID", "5252", "/T", "/F"]
    assert tree_kills[0][1]["timeout"] == 5.0
    assert process.communicate_calls == 2


def test_extract_frame_downloads_bounded_clip_and_returns_hashed_jpeg(monkeypatch):
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        if command[0] == "yt-dlp":
            output_template = Path(command[command.index("--output") + 1])
            clip = Path(str(output_template).replace("%(ext)s", "mp4"))
            clip.write_bytes(b"video")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=JPEG, stderr=b"")

    monkeypatch.setattr(frame_module, "_run_process", fake_run)

    frame = extract_frame(
        "https://youtu.be/H6lZ182QaVk", timestamp_ms=12_345, max_width=640
    )

    assert frame.video_id == "H6lZ182QaVk"
    assert frame.requested_timestamp_ms == 12_345
    assert frame.mime_type == "image/jpeg"
    assert frame.data == JPEG
    assert frame.sha256 == hashlib.sha256(JPEG).hexdigest()

    download, render = commands
    assert download[0] == "yt-dlp"
    assert download[download.index("--download-sections") + 1] == "*10.845-14.845"
    assert download[-1] == "https://www.youtube.com/watch?v=H6lZ182QaVk"
    assert render[0] == "ffmpeg"
    assert render[render.index("-ss") + 1] == "1.500"
    assert "min(640,iw)" in render[render.index("-vf") + 1]
    assert "pipe:1" == render[-1]


@pytest.mark.parametrize(
    ("video", "timestamp_ms", "max_width"),
    [
        ("not-a-video!", 1_000, 640),
        ("H6lZ182QaVk", -1, 640),
        ("H6lZ182QaVk", True, 640),
        ("H6lZ182QaVk", 1.5, 640),
        ("H6lZ182QaVk", 1_000, 63),
        ("H6lZ182QaVk", 1_000, 3_841),
    ],
)
def test_extract_frame_rejects_invalid_input_before_subprocess(
    monkeypatch, video, timestamp_ms, max_width
):
    def forbidden_run(*_args, **_kwargs):
        raise AssertionError("subprocess must not run for invalid input")

    monkeypatch.setattr(frame_module, "_run_process", forbidden_run)

    with pytest.raises(ValueError):
        extract_frame(video, timestamp_ms=timestamp_ms, max_width=max_width)


def test_extract_frame_does_not_expose_proxy_credentials_on_download_failure(
    monkeypatch,
):
    secret_proxy = "http://private-user:private-password@proxy.example:8080"
    monkeypatch.setenv("TUBE_BRIDGE_PROXY", secret_proxy)

    def failed_run(command, **kwargs):
        assert secret_proxy not in command
        assert "--proxy" not in command
        assert kwargs["env"]["HTTPS_PROXY"] == secret_proxy
        assert kwargs["env"]["HTTP_PROXY"] == secret_proxy
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr=f"unable to connect through {secret_proxy}",
        )

    monkeypatch.setattr(frame_module, "_run_process", failed_run)

    with pytest.raises(FrameExtractionError) as error:
        extract_frame("H6lZ182QaVk", timestamp_ms=5_000)

    assert "private-user" not in str(error.value)
    assert "private-password" not in str(error.value)


def test_extract_frame_rejects_non_jpeg_renderer_output(monkeypatch):
    def fake_run(command, **_kwargs):
        if command[0] == "yt-dlp":
            output_template = Path(command[command.index("--output") + 1])
            Path(str(output_template).replace("%(ext)s", "webm")).write_bytes(b"video")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout=b"not-jpeg", stderr=b"")

    monkeypatch.setattr(frame_module, "_run_process", fake_run)

    with pytest.raises(FrameExtractionError, match="valid JPEG"):
        extract_frame("H6lZ182QaVk", timestamp_ms=5_000)

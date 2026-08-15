"""Bounded timestamp-based frame extraction from YouTube videos."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from ..errors import ErrorCode, ErrorSource, TubeBridgeError
from .client import extract_video_id, get_proxy, ytdlp_failure


class FrameExtractionError(TubeBridgeError):
    """Typed frame extraction failure with sanitized public text."""

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.UPSTREAM_UNAVAILABLE,
        source: ErrorSource = ErrorSource.TUBE_BRIDGE,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            source=source,
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
        )


@dataclass(frozen=True)
class ExtractedFrame:
    video_id: str
    requested_timestamp_ms: int
    mime_type: str
    data: bytes
    sha256: str


def _format_ms(milliseconds: int) -> str:
    return f"{milliseconds // 1000}.{milliseconds % 1000:03d}"


def _run_process(
    command: list[str],
    *,
    capture_output: bool,
    check: bool,
    timeout: float,
    text: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run one isolated process and kill its descendant tree on timeout."""
    if not capture_output:
        raise ValueError("frame subprocess output must be captured")
    process_options: dict = {}
    if os.name == "posix":
        process_options["start_new_session"] = True
    elif os.name == "nt":
        process_options["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
        )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        env=env,
        **process_options,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif os.name == "nt":
            try:
                terminated = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=5.0,
                )
                if terminated.returncode != 0:
                    process.kill()
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
        else:
            process.kill()
        try:
            process.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.communicate(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        raise

    completed = subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout=stdout,
        stderr=stderr,
    )
    if check and completed.returncode:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=stdout,
            stderr=stderr,
        )
    return completed


def extract_frame(
    video: str,
    *,
    timestamp_ms: int,
    max_width: int = 640,
    timeout: int = 90,
) -> ExtractedFrame:
    """Extract one bounded JPEG frame without retaining downloaded media."""
    video_id = extract_video_id(video)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("timeout must be a positive number")
    deadline = time.monotonic() + timeout

    def remaining_timeout() -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("frame extraction", timeout)
        return remaining

    if isinstance(timestamp_ms, bool) or not isinstance(timestamp_ms, int):
        raise ValueError("timestamp_ms must be an integer")
    if timestamp_ms < 0:
        raise ValueError("timestamp_ms must be non-negative")
    if isinstance(max_width, bool) or not isinstance(max_width, int):
        raise ValueError("max_width must be an integer")
    if not 64 <= max_width <= 3840:
        raise ValueError("max_width must be between 64 and 3840")

    clip_start_ms = max(0, timestamp_ms - 1500)
    clip_end_ms = timestamp_ms + 2500
    local_seek_ms = timestamp_ms - clip_start_ms
    watch_url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory(prefix="tube-bridge-frame-") as temporary:
        workdir = Path(temporary)
        output_template = workdir / "clip.%(ext)s"
        download_command = [
            "yt-dlp",
            "--no-warnings",
            "--no-playlist",
            "--no-part",
        ]
        proxy = get_proxy()
        download_environment = os.environ.copy()
        if proxy:
            download_environment["HTTP_PROXY"] = proxy
            download_environment["HTTPS_PROXY"] = proxy
        download_command.extend(
            [
                "--download-sections",
                f"*{_format_ms(clip_start_ms)}-{_format_ms(clip_end_ms)}",
                "--force-keyframes-at-cuts",
                "--format",
                "bestvideo[height<=1080]/best[height<=1080]/best",
                "--max-filesize",
                "100M",
                "--output",
                str(output_template),
                watch_url,
            ]
        )

        try:
            downloaded = _run_process(
                download_command,
                capture_output=True,
                check=False,
                text=True,
                timeout=remaining_timeout(),
                env=download_environment,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise FrameExtractionError(
                "yt-dlp could not extract the requested clip",
                source=ErrorSource.YT_DLP,
                retryable=isinstance(error, subprocess.TimeoutExpired),
            ) from error
        if downloaded.returncode != 0:
            classified = ytdlp_failure(
                "yt-dlp could not extract the requested clip",
                downloaded.stderr or "",
            )
            raise FrameExtractionError(
                f"yt-dlp could not extract the requested clip "
                f"(exit {downloaded.returncode})",
                code=classified.code,
                source=classified.source,
                retryable=classified.retryable,
                retry_after_seconds=classified.retry_after_seconds,
            )

        clips = [
            path
            for path in sorted(workdir.glob("clip.*"))
            if path.is_file() and path.suffix not in {".part", ".ytdl"}
        ]
        if len(clips) != 1:
            raise FrameExtractionError(
                "yt-dlp did not produce exactly one bounded clip",
                source=ErrorSource.YT_DLP,
            )

        render_command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(clips[0]),
            "-ss",
            _format_ms(local_seek_ms),
            "-frames:v",
            "1",
            "-vf",
            f"scale=w='min({max_width},iw)':h=-2",
            "-q:v",
            "2",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
        try:
            rendered = _run_process(
                render_command,
                capture_output=True,
                check=False,
                timeout=remaining_timeout(),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise FrameExtractionError("ffmpeg could not render the requested frame") from error
        if rendered.returncode != 0:
            raise FrameExtractionError(
                f"ffmpeg could not render the requested frame (exit {rendered.returncode})"
            )

        jpeg = rendered.stdout
        if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
            raise FrameExtractionError("ffmpeg did not return a valid JPEG")

    return ExtractedFrame(
        video_id=video_id,
        requested_timestamp_ms=timestamp_ms,
        mime_type="image/jpeg",
        data=jpeg,
        sha256=hashlib.sha256(jpeg).hexdigest(),
    )

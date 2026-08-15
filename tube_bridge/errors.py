"""Stable typed errors for tube-bridge tool failures."""

from __future__ import annotations

from enum import StrEnum


class ErrorSource(StrEnum):
    """Component whose failure is surfaced to the MCP client."""

    TUBE_BRIDGE = "tube_bridge"
    YOUTUBE_DATA_API = "youtube_data_api"
    YT_DLP = "yt_dlp"
    YOUTUBE_TRANSCRIPT_API = "youtube_transcript_api"
    LOCAL_CORPUS = "local_corpus"


class ErrorCode(StrEnum):
    """Provider-independent failure category."""

    INVALID_ARGUMENT = "invalid_argument"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    TRANSCRIPT_UNAVAILABLE = "transcript_unavailable"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    INTERNAL_ERROR = "internal_error"


class TubeBridgeError(RuntimeError):
    """Base class for controlled failures exposed through MCP."""

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode,
        source: ErrorSource,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        normalized_message = str(message).strip()
        if not normalized_message:
            raise ValueError("error message must not be empty")
        if (
            retry_after_seconds is not None
            and (
                isinstance(retry_after_seconds, bool)
                or not isinstance(retry_after_seconds, int)
                or retry_after_seconds < 1
            )
        ):
            raise ValueError("retry_after_seconds must be a positive integer")
        if retry_after_seconds is not None and not retryable:
            raise ValueError("retry_after_seconds requires retryable=True")

        super().__init__(normalized_message)
        self.code = ErrorCode(code)
        self.source = ErrorSource(source)
        self.retryable = bool(retryable)
        self.retry_after_seconds = retry_after_seconds

    def to_payload(self) -> dict:
        payload = {
            "error": str(self),
            "code": self.code.value,
            "source": self.source.value,
            "retryable": self.retryable,
        }
        if self.retry_after_seconds is not None:
            payload["retry_after_seconds"] = self.retry_after_seconds
        return payload


class InvalidArgumentError(TubeBridgeError):
    def __init__(
        self,
        message: str,
        *,
        source: ErrorSource = ErrorSource.TUBE_BRIDGE,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.INVALID_ARGUMENT,
            source=source,
            retryable=False,
        )


class NotFoundError(TubeBridgeError):
    def __init__(self, message: str, *, source: ErrorSource) -> None:
        super().__init__(
            message,
            code=ErrorCode.NOT_FOUND,
            source=source,
            retryable=False,
        )


class RateLimitedError(TubeBridgeError):
    def __init__(
        self,
        message: str,
        *,
        source: ErrorSource,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.RATE_LIMITED,
            source=source,
            retryable=True,
            retry_after_seconds=retry_after_seconds,
        )


class QuotaExceededError(TubeBridgeError):
    def __init__(
        self,
        message: str,
        *,
        source: ErrorSource = ErrorSource.YOUTUBE_DATA_API,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.QUOTA_EXCEEDED,
            source=source,
            retryable=False,
        )


class TranscriptUnavailableError(TubeBridgeError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code=ErrorCode.TRANSCRIPT_UNAVAILABLE,
            source=ErrorSource.YOUTUBE_TRANSCRIPT_API,
            retryable=False,
        )


class UpstreamUnavailableError(TubeBridgeError):
    def __init__(
        self,
        message: str,
        *,
        source: ErrorSource,
        retryable: bool = True,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            source=source,
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
        )


class InternalError(TubeBridgeError):
    def __init__(self, message: str = "Unexpected error") -> None:
        super().__init__(
            message,
            code=ErrorCode.INTERNAL_ERROR,
            source=ErrorSource.TUBE_BRIDGE,
            retryable=False,
        )

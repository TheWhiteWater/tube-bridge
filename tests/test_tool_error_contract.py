"""Frozen offline contract for typed MCP tool errors.

The public text payload remains backward compatible while the MCP envelope must
mark failures with ``CallToolResult.isError=True``.  No test in this module may
contact YouTube, start an embedding model, or use a persistent user database.
"""

from __future__ import annotations

import io
import json
from email.message import Message
import subprocess
from unittest.mock import AsyncMock
import urllib.error

import jsonschema
from mcp.types import (
    CallToolRequest,
    CallToolRequestParams,
    CallToolResult,
    TextContent,
)
import pytest
from youtube_transcript_api._errors import (
    AgeRestricted,
    TranscriptsDisabled,
    VideoUnavailable,
)

from tube_bridge.errors import (
    ErrorCode,
    ErrorSource,
    NotFoundError,
    QuotaExceededError,
    TubeBridgeError,
)


EXPECTED_ERROR_SOURCES = {
    "tube_bridge",
    "youtube_data_api",
    "yt_dlp",
    "youtube_transcript_api",
    "local_corpus",
}
EXPECTED_ERROR_CODES = {
    "invalid_argument",
    "not_found",
    "rate_limited",
    "quota_exceeded",
    "transcript_unavailable",
    "upstream_unavailable",
    "internal_error",
}
EXPECTED_ERROR_PAYLOAD_SCHEMA = {
    "type": "object",
    "properties": {
        "error": {"type": "string", "minLength": 1},
        "code": {"enum": sorted(EXPECTED_ERROR_CODES)},
        "source": {"enum": sorted(EXPECTED_ERROR_SOURCES)},
        "retryable": {"type": "boolean"},
        "retry_after_seconds": {"type": "integer", "minimum": 1},
    },
    "required": ["error", "code", "source", "retryable"],
    "additionalProperties": False,
}


def _payload(result: CallToolResult) -> dict:
    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    payload = json.loads(result.content[0].text)
    jsonschema.validate(payload, EXPECTED_ERROR_PAYLOAD_SCHEMA)
    if "retry_after_seconds" in payload:
        assert payload["retryable"] is True
        assert payload["retry_after_seconds"] >= 1
    return payload


def _http_error(status: int, payload: dict, retry_after: str | None = None):
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        "https://www.googleapis.com/youtube/v3/videos",
        status,
        "upstream failure",
        headers,
        io.BytesIO(json.dumps(payload).encode("utf-8")),
    )


def _raise(error: Exception):
    def raiser(*_args, **_kwargs):
        raise error

    return raiser


def test_error_enum_values_are_exactly_frozen():
    assert {member.value for member in ErrorSource} == EXPECTED_ERROR_SOURCES
    assert {member.value for member in ErrorCode} == EXPECTED_ERROR_CODES


@pytest.mark.asyncio
async def test_invalid_video_url_is_structured_mcp_error():
    from tube_bridge.server import call_tool

    result = await call_tool("youtube_get_video_info", {"url": "invalid"})

    payload = _payload(result)
    assert payload == {
        "error": "Cannot extract video ID from: invalid",
        "code": "invalid_argument",
        "source": "tube_bridge",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_typed_error_preserves_semantics_at_tool_boundary(mocker):
    from tube_bridge.server import call_tool

    mocker.patch(
        "tube_bridge.server.corpus_list",
        new_callable=AsyncMock,
        side_effect=NotFoundError(
            "Corpus 'missing' not found.", source=ErrorSource.LOCAL_CORPUS
        ),
    )

    payload = _payload(await call_tool("corpus_list", {}))
    assert payload == {
        "error": "Corpus 'missing' not found.",
        "code": "not_found",
        "source": "local_corpus",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_unexpected_error_is_sanitized_and_marked_as_error(mocker):
    from tube_bridge.server import call_tool

    mocker.patch(
        "tube_bridge.server.corpus_list",
        new_callable=AsyncMock,
        side_effect=Exception("private crash details"),
    )

    payload = _payload(await call_tool("corpus_list", {}))
    assert payload == {
        "error": "Unexpected error",
        "code": "internal_error",
        "source": "tube_bridge",
        "retryable": False,
    }
    assert "private crash details" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_mcp_request_handler_preserves_is_error_true():
    from tube_bridge.server import server

    handler = server.request_handlers[CallToolRequest]
    response = await handler(
        CallToolRequest(
            params=CallToolRequestParams(
                name="youtube_get_video_info",
                arguments={"url": "invalid"},
            )
        )
    )

    payload = _payload(response.root)
    assert payload["code"] == "invalid_argument"


@pytest.mark.asyncio
async def test_mcp_schema_validation_uses_typed_error_envelope():
    from tube_bridge.server import server

    handler = server.request_handlers[CallToolRequest]
    response = await handler(
        CallToolRequest(
            params=CallToolRequestParams(
                name="youtube_get_video_info",
                arguments={},
            )
        )
    )

    payload = _payload(response.root)
    assert payload["code"] == "invalid_argument"
    assert payload["source"] == "tube_bridge"
    assert payload["retryable"] is False
    assert "Input validation error" in payload["error"]


@pytest.mark.asyncio
async def test_mcp_request_handler_keeps_success_non_error_and_schema(mocker):
    from tube_bridge.server import server

    success = {"corpora": [], "total": 0}
    mocker.patch(
        "tube_bridge.server.corpus_list",
        new_callable=AsyncMock,
        return_value=success,
    )
    handler = server.request_handlers[CallToolRequest]
    response = await handler(
        CallToolRequest(
            params=CallToolRequestParams(name="corpus_list", arguments={})
        )
    )

    assert isinstance(response.root, CallToolResult)
    assert response.root.isError is False
    assert len(response.root.content) == 1
    assert json.loads(response.root.content[0].text) == success


def test_youtube_api_429_uses_real_retry_after(monkeypatch):
    from tube_bridge.youtube import api

    monkeypatch.setenv("YOUTUBE_API_KEY", "offline-test-key")
    error = _http_error(
        429,
        {"error": {"code": 429, "message": "Too many requests"}},
        retry_after="60",
    )
    monkeypatch.setattr(api.urllib.request, "urlopen", _raise(error))

    with pytest.raises(TubeBridgeError) as raised:
        api.api_call("videos", {"id": "abcdefghijk"})

    assert raised.value.code is ErrorCode.RATE_LIMITED
    assert raised.value.source is ErrorSource.YOUTUBE_DATA_API
    assert raised.value.retryable is True
    assert raised.value.retry_after_seconds == 60


def test_youtube_api_429_without_retry_after_does_not_invent_delay(monkeypatch):
    from tube_bridge.youtube import api

    monkeypatch.setenv("YOUTUBE_API_KEY", "offline-test-key")
    error = _http_error(
        429,
        {"error": {"code": 429, "message": "Too many requests"}},
    )
    monkeypatch.setattr(api.urllib.request, "urlopen", _raise(error))

    with pytest.raises(TubeBridgeError) as raised:
        api.api_call("videos", {"id": "abcdefghijk"})

    assert raised.value.code is ErrorCode.RATE_LIMITED
    assert raised.value.retryable is True
    assert raised.value.retry_after_seconds is None
    assert "retry_after_seconds" not in raised.value.to_payload()


def test_youtube_api_quota_reason_is_not_automatic_retry(monkeypatch):
    from tube_bridge.youtube import api

    monkeypatch.setenv("YOUTUBE_API_KEY", "offline-test-key")
    error = _http_error(
        403,
        {
            "error": {
                "code": 403,
                "message": "Daily quota exhausted",
                "errors": [{"reason": "quotaExceeded"}],
            }
        },
    )
    monkeypatch.setattr(api.urllib.request, "urlopen", _raise(error))

    with pytest.raises(QuotaExceededError) as raised:
        api.api_call("videos", {"id": "abcdefghijk"})

    assert raised.value.source is ErrorSource.YOUTUBE_DATA_API
    assert raised.value.retryable is False
    assert raised.value.retry_after_seconds is None


def test_youtube_api_rate_limit_reason_is_distinct_from_quota(monkeypatch):
    from tube_bridge.youtube import api

    monkeypatch.setenv("YOUTUBE_API_KEY", "offline-test-key")
    error = _http_error(
        403,
        {
            "error": {
                "code": 403,
                "message": "Per-user request rate exceeded",
                "errors": [{"reason": "userRateLimitExceeded"}],
            }
        },
    )
    monkeypatch.setattr(api.urllib.request, "urlopen", _raise(error))

    with pytest.raises(TubeBridgeError) as raised:
        api.api_call("videos", {"id": "abcdefghijk"})

    assert raised.value.code is ErrorCode.RATE_LIMITED
    assert raised.value.retryable is True


def test_youtube_api_503_preserves_real_retry_after(monkeypatch):
    from tube_bridge.youtube import api

    monkeypatch.setenv("YOUTUBE_API_KEY", "offline-test-key")
    error = _http_error(
        503,
        {"error": {"code": 503, "message": "Temporarily unavailable"}},
        retry_after="120",
    )
    monkeypatch.setattr(api.urllib.request, "urlopen", _raise(error))

    with pytest.raises(TubeBridgeError) as raised:
        api.api_call("videos", {"id": "abcdefghijk"})

    assert raised.value.code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert raised.value.retryable is True
    assert raised.value.retry_after_seconds == 120


@pytest.mark.parametrize(
    ("status", "expected_retryable", "expected_delay"),
    [
        (408, True, 45),
        (501, False, None),
    ],
)
def test_youtube_api_uses_explicit_transient_statuses(
    monkeypatch, status, expected_retryable, expected_delay
):
    from tube_bridge.youtube import api

    monkeypatch.setenv("YOUTUBE_API_KEY", "offline-test-key")
    error = _http_error(
        status,
        {"error": {"code": status, "message": "HTTP failure"}},
        retry_after="45",
    )
    monkeypatch.setattr(api.urllib.request, "urlopen", _raise(error))

    with pytest.raises(TubeBridgeError) as raised:
        api.api_call("videos", {"id": "abcdefghijk"})

    assert raised.value.code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert raised.value.retryable is expected_retryable
    assert raised.value.retry_after_seconds == expected_delay


def test_youtube_api_missing_video_is_typed_not_found(monkeypatch):
    from tube_bridge.youtube import api

    monkeypatch.setattr(api, "api_call", lambda *_args, **_kwargs: {"items": []})

    with pytest.raises(NotFoundError) as raised:
        api.get_video_info("abcdefghijk")

    assert raised.value.source is ErrorSource.YOUTUBE_DATA_API
    assert raised.value.retryable is False


@pytest.mark.asyncio
async def test_quota_fallback_success_remains_normal_success(monkeypatch):
    from tube_bridge import tools

    monkeypatch.setattr(tools.api, "get_api_key", lambda: "offline-test-key")
    monkeypatch.setattr(
        tools.api,
        "search_videos",
        _raise(QuotaExceededError("Daily quota exhausted")),
    )
    monkeypatch.setattr(
        tools.yt,
        "run_ytdlp_multi",
        lambda *_args, **_kwargs: (
            [{"id": "abcdefghijk", "title": "Offline result"}],
            "",
        ),
    )

    result = await tools.search("offline", 1, {"query": "offline"})

    assert result == {
        "query": "offline",
        "source": "yt-dlp (anonymous)",
        "total_results": 1,
        "videos": [
            {
                "id": "abcdefghijk",
                "title": "Offline result",
                "url": "https://youtube.com/watch?v=abcdefghijk",
                "duration": None,
                "view_count": None,
                "channel": None,
                "channel_url": None,
                "upload_date": None,
            }
        ],
    }


@pytest.mark.asyncio
async def test_failed_quota_fallback_surfaces_final_ytdlp_error(monkeypatch):
    from tube_bridge import tools

    monkeypatch.setattr(tools.api, "get_api_key", lambda: "offline-test-key")
    monkeypatch.setattr(
        tools.api,
        "search_videos",
        _raise(QuotaExceededError("Daily quota exhausted")),
    )
    monkeypatch.setattr(
        tools.yt,
        "run_ytdlp_multi",
        lambda *_args, **_kwargs: (
            [],
            "ERROR: HTTP Error 429: Too Many Requests",
        ),
    )

    with pytest.raises(TubeBridgeError) as raised:
        await tools.search("offline", 1, {"query": "offline"})

    assert raised.value.code is ErrorCode.RATE_LIMITED
    assert raised.value.source is ErrorSource.YT_DLP
    assert raised.value.retryable is True


def test_failed_trending_fallback_surfaces_final_ytdlp_error(monkeypatch):
    from tube_bridge import tools

    monkeypatch.setattr(tools.api, "get_api_key", lambda: "offline-test-key")
    monkeypatch.setattr(
        tools.api,
        "get_trending",
        _raise(QuotaExceededError("Daily quota exhausted")),
    )
    monkeypatch.setattr(
        tools.yt,
        "run_ytdlp_multi",
        lambda *_args, **_kwargs: ([], "ERROR: upstream connection failed"),
    )

    with pytest.raises(TubeBridgeError) as raised:
        tools._trending_sync(1)

    assert raised.value.code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert raised.value.source is ErrorSource.YT_DLP
    assert raised.value.retryable is True


def test_transcripts_disabled_is_typed_unavailable(monkeypatch):
    from tube_bridge.youtube import transcript

    class DisabledApi:
        def list(self, video_id):
            raise TranscriptsDisabled(video_id)

    monkeypatch.setattr(transcript, "_api", DisabledApi())

    with pytest.raises(TubeBridgeError) as raised:
        transcript.get_transcript("abcdefghijk")

    assert raised.value.code is ErrorCode.TRANSCRIPT_UNAVAILABLE
    assert raised.value.source is ErrorSource.YOUTUBE_TRANSCRIPT_API
    assert raised.value.retryable is False


def test_age_restricted_transcript_is_non_retryable_unavailable(monkeypatch):
    from tube_bridge.youtube import transcript

    class RestrictedApi:
        def list(self, video_id):
            raise AgeRestricted(video_id)

    monkeypatch.setattr(transcript, "_api", RestrictedApi())

    with pytest.raises(TubeBridgeError) as raised:
        transcript.get_transcript("abcdefghijk")
    assert raised.value.code is ErrorCode.TRANSCRIPT_UNAVAILABLE
    assert raised.value.source is ErrorSource.YOUTUBE_TRANSCRIPT_API
    assert raised.value.retryable is False


def test_deleted_transcript_video_is_non_retryable_not_found(monkeypatch):
    from tube_bridge.youtube import transcript

    class MissingVideoApi:
        def list(self, video_id):
            raise VideoUnavailable(video_id)

    monkeypatch.setattr(transcript, "_api", MissingVideoApi())

    with pytest.raises(NotFoundError) as raised:
        transcript.get_transcript("abcdefghijk")
    assert raised.value.source is ErrorSource.YOUTUBE_TRANSCRIPT_API
    assert raised.value.retryable is False

    with pytest.raises(NotFoundError):
        transcript.get_available_languages("abcdefghijk")


@pytest.mark.parametrize(
    ("stderr", "expected_code", "expected_retryable"),
    [
        ("ERROR: Private video", ErrorCode.NOT_FOUND, False),
        ("ERROR: Unsupported URL: example://bad", ErrorCode.INVALID_ARGUMENT, False),
        ("ERROR: 'not-a-url' is not a valid URL", ErrorCode.INVALID_ARGUMENT, False),
    ],
)
def test_ytdlp_deterministic_failures_are_not_retryable(
    stderr, expected_code, expected_retryable
):
    from tube_bridge.youtube.client import ytdlp_failure

    error = ytdlp_failure("Could not fetch video", stderr)

    assert error.code is expected_code
    assert error.source is ErrorSource.YT_DLP
    assert error.retryable is expected_retryable


@pytest.mark.parametrize(
    "stderr",
    [
        "ERROR: HTTP Error 429 via https://proxy-user:proxy-password@proxy.example:8080",
        "ERROR: Private video referenced from /var/tmp/private-user/request.txt",
        "ERROR: Unsupported URL: https://example.invalid/?token=private-token",
        "ERROR: Sign in to confirm your age for private-account@example.invalid",
        "ERROR: extractor crashed at /var/tmp/private-user/cache.db",
    ],
)
def test_ytdlp_failure_classifies_without_exposing_raw_stderr(stderr):
    from tube_bridge.youtube.client import ytdlp_failure

    public_message = "Could not fetch video"
    error = ytdlp_failure(public_message, stderr)

    assert str(error) == public_message
    assert stderr not in str(error)


def test_frame_ytdlp_exit_preserves_classification_without_stderr_leak(monkeypatch):
    from tube_bridge.youtube import frame

    secret = "private-user:private-password"

    def failed_run(command, **_kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr=f"HTTP Error 429: Too Many Requests via {secret}",
        )

    monkeypatch.setattr(frame, "_run_process", failed_run)

    with pytest.raises(frame.FrameExtractionError) as raised:
        frame.extract_frame("abcdefghijk", timestamp_ms=1000)

    assert raised.value.code is ErrorCode.RATE_LIMITED
    assert raised.value.source is ErrorSource.YT_DLP
    assert raised.value.retryable is True
    assert secret not in str(raised.value)


@pytest.mark.asyncio
async def test_frame_timeout_preserves_ytdlp_source_and_retryability(mocker):
    from tube_bridge.server import call_tool
    from tube_bridge.youtube import frame

    mocker.patch(
        "tube_bridge.youtube.frame._run_process",
        side_effect=subprocess.TimeoutExpired("yt-dlp", 90),
    )
    with pytest.raises(frame.FrameExtractionError) as extracted:
        frame.extract_frame("abcdefghijk", timestamp_ms=1000)
    error = extracted.value
    assert error.source is ErrorSource.YT_DLP
    assert error.retryable is True

    mocker.patch(
        "tube_bridge.server.video_frame",
        new_callable=AsyncMock,
        side_effect=error,
    )

    payload = _payload(
        await call_tool(
            "youtube_get_frame",
            {"url": "abcdefghijk", "timestamp_ms": 1000},
        )
    )
    assert payload["code"] == "upstream_unavailable"
    assert payload["source"] == "yt_dlp"
    assert payload["retryable"] is True


@pytest.mark.asyncio
async def test_ytdlp_rate_limit_is_typed_when_fallback_fails(monkeypatch):
    from tube_bridge import cache, tools

    tools._video_info_cached.cache_clear()
    monkeypatch.setattr(tools.api, "get_api_key", lambda: None)
    monkeypatch.setattr(cache, "get_video_info", lambda _video_id: None)
    monkeypatch.setattr(
        tools.yt,
        "run_ytdlp",
        lambda *_args, **_kwargs: (None, "ERROR: HTTP Error 429: Too Many Requests"),
    )

    with pytest.raises(TubeBridgeError) as raised:
        await tools.video_info("abcdefghijk")

    assert raised.value.code is ErrorCode.RATE_LIMITED
    assert raised.value.source is ErrorSource.YT_DLP
    assert raised.value.retryable is True
    assert raised.value.retry_after_seconds is None
    tools._video_info_cached.cache_clear()


def test_local_corpus_model_mismatch_is_non_retryable(monkeypatch, tmp_path):
    from tube_bridge import corpus

    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")
    monkeypatch.setenv("TUBE_BRIDGE_EMBEDDING_MODEL", "new-model")
    with corpus._connection() as connection:
        connection.execute(
            "INSERT INTO corpora "
            "(corpus_id,label,embedding_model,created_at,expires_at) "
            "VALUES ('mismatch','Mismatch','old-model',0,NULL)"
        )
        connection.commit()

    with pytest.raises(TubeBridgeError) as raised:
        corpus.corpus_search("mismatch", "query")

    assert raised.value.code is ErrorCode.INVALID_ARGUMENT
    assert raised.value.source is ErrorSource.LOCAL_CORPUS
    assert raised.value.retryable is False


def test_missing_local_corpus_is_typed_for_search_and_add(monkeypatch, tmp_path):
    from tube_bridge import corpus

    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")

    with pytest.raises(NotFoundError) as search_error:
        corpus.corpus_search("missing", "query")
    assert search_error.value.source is ErrorSource.LOCAL_CORPUS

    with pytest.raises(NotFoundError) as add_error:
        corpus.corpus_add(
            "missing",
            "abcdefghijk",
            [{"text": "offline", "start": 0.0, "duration": 1.0}],
        )
    assert add_error.value.source is ErrorSource.LOCAL_CORPUS

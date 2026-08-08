"""Disposable-demo request identity and process-local Data API allowance."""

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import hmac
import ipaddress
import os
import secrets
import threading
from typing import Iterator

DEMO_DATA_API_LIMIT = 5
DEMO_CORPUS_TTL_SECONDS = 600

_current_client_ip: ContextVar[str | None] = ContextVar(
    "tube_bridge_demo_client_ip", default=None,
)


class DemoPolicyError(RuntimeError):
    """Base class for stable, user-visible disposable-demo policy errors."""

    def __init__(self, payload: dict):
        self._payload = dict(payload)
        super().__init__(self._payload["message"])

    def to_payload(self) -> dict:
        return dict(self._payload)


class DemoDataApiLimitExceeded(DemoPolicyError):
    def __init__(self):
        super().__init__({
            "error": "demo_data_api_limit_exceeded",
            "message": "Disposable demo allowance exhausted for this process lifetime.",
            "limit": DEMO_DATA_API_LIMIT,
            "reset": "process_restart",
        })


class DemoClientIdentityUnavailable(DemoPolicyError):
    def __init__(self):
        super().__init__({
            "error": "demo_client_identity_unavailable",
            "message": "Disposable demo could not determine the observed client identity.",
            "limit": DEMO_DATA_API_LIMIT,
            "reset": "send_request_through_demo_http_transport",
        })


def is_demo_mode() -> bool:
    """Return true only for the explicit disposable-demo opt-in."""
    return os.environ.get("TUBE_BRIDGE_DEMO_MODE") == "1"


def _normalize_client_ip(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except (ValueError, AttributeError):
        return None


def _headers(scope) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        try:
            result[raw_name.decode("latin-1").lower()] = raw_value.decode("latin-1")
        except (AttributeError, UnicodeDecodeError):
            continue
    return result


def extract_client_ip(scope) -> str | None:
    """Extract one normalized observed address from an ASGI request scope.

    Proxy mode is explicit.  The selected X-Forwarded-For entry is counted
    from the right so an untrusted prefix cannot create fresh identities.
    """
    if os.environ.get("TUBE_BRIDGE_TRUST_PROXY_HEADERS") == "1":
        forwarded = _headers(scope).get("x-forwarded-for")
        if not forwarded:
            return None
        try:
            trusted_hops = int(os.environ.get("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "1"))
        except ValueError:
            return None
        if trusted_hops < 1:
            return None
        chain = [item.strip() for item in forwarded.split(",") if item.strip()]
        if len(chain) < trusted_hops:
            return None
        return _normalize_client_ip(chain[-trusted_hops])

    client = scope.get("client")
    if not client or not isinstance(client, (tuple, list)) or not client:
        return None
    return _normalize_client_ip(client[0])


@contextmanager
def bind_client_ip(client_ip: str | None) -> Iterator[None]:
    """Bind a transient request identity to the current async/thread context."""
    normalized = _normalize_client_ip(client_ip)
    token = _current_client_ip.set(normalized)
    try:
        yield
    finally:
        _current_client_ip.reset(token)


@contextmanager
def bind_request_identity(scope) -> Iterator[None]:
    """Bind identity extracted from one ASGI request scope."""
    with bind_client_ip(extract_client_ip(scope)):
        yield


def get_current_client_ip() -> str | None:
    return _current_client_ip.get()


class DemoAllowance:
    """Thread-safe process-lifetime allowance keyed by opaque IP digests."""

    def __init__(self, salt: bytes | None = None):
        self._salt = salt if salt is not None else secrets.token_bytes(32)
        self._buckets: dict[str, int] = {}
        self._allowed_total = 0
        self._rejected_total = 0
        self._lock = threading.Lock()

    def _identity_digest(self, client_ip: str) -> str:
        normalized = _normalize_client_ip(client_ip)
        if normalized is None:
            raise DemoClientIdentityUnavailable()
        return hmac.new(
            self._salt,
            normalized.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    def consume(self, client_ip: str) -> int:
        digest = self._identity_digest(client_ip)
        with self._lock:
            used = self._buckets.get(digest, 0)
            if used >= DEMO_DATA_API_LIMIT:
                self._rejected_total += 1
                raise DemoDataApiLimitExceeded()
            used += 1
            self._buckets[digest] = used
            self._allowed_total += 1
            return DEMO_DATA_API_LIMIT - used

    def metrics(self) -> dict:
        with self._lock:
            return {
                "limit": DEMO_DATA_API_LIMIT,
                "allowed_total": self._allowed_total,
                "rejected_total": self._rejected_total,
                "client_buckets": len(self._buckets),
            }


_allowance = DemoAllowance()


def consume_data_api_operation() -> int | None:
    """Consume one attempted official Data API operation in demo mode."""
    if not is_demo_mode():
        return None
    client_ip = get_current_client_ip()
    if client_ip is None:
        raise DemoClientIdentityUnavailable()
    return _allowance.consume(client_ip)


def demo_metrics() -> dict:
    return _allowance.metrics()

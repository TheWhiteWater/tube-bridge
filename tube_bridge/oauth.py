"""Invite-gated OAuth adapter for controlled remote MCP test deployments."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

ENV_NAMES = (
    "TUBE_BRIDGE_PUBLIC_BASE_URL",
    "TUBE_BRIDGE_OAUTH_SIGNING_KEY",
    "TUBE_BRIDGE_OAUTH_INVITES_JSON",
)
SCOPE = "mcp:tools"
MAX_BODY = 16 * 1024
MAX_REDIRECTS = 8
MAX_REDIRECT_LENGTH = 2048
MAX_CLIENT_NAME = 128
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")


@dataclass(frozen=True)
class InviteRecord:
    id: str
    role: str
    secret_sha256: str


@dataclass(frozen=True)
class AuthPrincipal:
    role: str
    subject: str | None
    method: str


@dataclass(frozen=True)
class OAuthConfig:
    enabled: bool
    issuer: str = ""
    resource: str = ""
    signing_key: bytes = b""
    invites: tuple[InviteRecord, ...] = ()
    access_token_ttl_seconds: int = 28800
    authorization_ttl_seconds: int = 300

    @classmethod
    def from_env(cls):
        values = {n: os.environ.get(n) for n in ENV_NAMES}
        if all(v is None for v in values.values()):
            return cls(False)
        if any(v is None or v == "" for v in values.values()):
            raise ValueError(
                "OAuth configuration requires all three OAuth environment variables"
            )
        origin = values[ENV_NAMES[0]]
        assert origin is not None
        try:
            p = urlsplit(origin)
            _ = p.port
        except ValueError as exc:
            raise ValueError(
                "TUBE_BRIDGE_PUBLIC_BASE_URL must be an exact HTTPS origin"
            ) from exc
        if (
            p.scheme != "https"
            or not p.netloc
            or p.path
            or p.query
            or p.fragment
            or p.username is not None
            or p.password is not None
            or p.hostname is None
            or "*" in p.hostname
            or any(c.isspace() or ord(c) < 32 for c in origin)
        ):
            raise ValueError(
                "TUBE_BRIDGE_PUBLIC_BASE_URL must be an exact HTTPS origin"
            )
        key_text = values[ENV_NAMES[1]]
        assert key_text is not None
        key = key_text.encode()
        if len(key) < 32:
            raise ValueError(
                "TUBE_BRIDGE_OAUTH_SIGNING_KEY must contain at least 32 bytes"
            )
        raw = values[ENV_NAMES[2]]
        assert raw is not None
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("OAuth invite configuration is invalid JSON") from exc
        if not isinstance(items, list) or not 1 <= len(items) <= 64:
            raise ValueError("OAuth invite configuration must contain 1 to 64 records")
        result = []
        ids = set()
        digests = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {
                "id",
                "role",
                "secret_sha256",
            }:
                raise ValueError(
                    "Each OAuth invite must contain only id, role, and secret_sha256"
                )
            iid = item["id"]
            role = item["role"]
            digest = item["secret_sha256"]
            if not isinstance(iid, str) or not ID_RE.fullmatch(iid):
                raise ValueError("OAuth invite id is invalid")
            if role not in ("operator", "tester"):
                raise ValueError("OAuth invite role is invalid")
            if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
                raise ValueError("OAuth invite secret_sha256 is invalid")
            if iid in ids or digest in digests:
                raise ValueError("OAuth invite ids and digests must be unique")
            ids.add(iid)
            digests.add(digest)
            result.append(InviteRecord(iid, role, digest))
        return cls(True, origin, f"{origin}/mcp", key, tuple(result))


class BodyTooLarge(ValueError):
    pass


class OAuthService:
    PUBLIC_PATHS = frozenset(
        {
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
            "/.well-known/oauth-authorization-server",
            "/oauth/register",
            "/oauth/authorize",
            "/oauth/token",
        }
    )

    def __init__(
        self,
        config: OAuthConfig,
        *,
        clock: Callable[[], float] | None = None,
        token_factory: Callable[[int], str] | None = None,
    ):
        self.config = config
        self.enabled = config.enabled
        self._clock = clock or time.time
        self._token_factory = token_factory or secrets.token_urlsafe
        self._pending = {}
        self._codes = {}
        self._operator_requests = 0
        self._tester_requests = 0
        self._subjects = set()
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls):
        return cls(OAuthConfig.from_env())

    @property
    def resource_metadata_url(self):
        return f"{self.config.issuer}/.well-known/oauth-protected-resource"

    def challenge(self):
        return (
            f'Bearer resource_metadata="{self.resource_metadata_url}", scope="{SCOPE}"'
        )

    @staticmethod
    def _b64(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    @staticmethod
    def _unb64(value):
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _sign(self, prefix, payload):
        encoded = self._b64(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
        )
        msg = f"{prefix}.{encoded}".encode()
        sig = self._b64(hmac.new(self.config.signing_key, msg, hashlib.sha256).digest())
        return f"{prefix}.{encoded}.{sig}"

    def _verify(self, value, prefix):
        try:
            actual, encoded, sig = value.split(".")
            if actual != prefix:
                raise ValueError()
            expected = self._b64(
                hmac.new(
                    self.config.signing_key,
                    f"{prefix}.{encoded}".encode(),
                    hashlib.sha256,
                ).digest()
            )
            if not hmac.compare_digest(sig, expected):
                raise ValueError()
            payload = json.loads(self._unb64(encoded))
            if not isinstance(payload, dict):
                raise ValueError()
            return payload
        except Exception as exc:
            raise ValueError("invalid signed OAuth value") from exc

    @staticmethod
    def _validate_redirect(uri):
        if (
            not isinstance(uri, str)
            or not 1 <= len(uri) <= MAX_REDIRECT_LENGTH
            or uri != uri.strip()
            or "\\" in uri
            or any(c.isspace() or ord(c) < 32 for c in uri)
        ):
            raise ValueError("invalid redirect")
        try:
            p = urlsplit(uri)
            _ = p.port
        except ValueError as exc:
            raise ValueError("invalid redirect") from exc
        host = p.hostname
        if (
            p.scheme not in ("https", "http")
            or not p.netloc
            or host is None
            or p.username is not None
            or p.password is not None
            or p.fragment
            or "*" in host
        ):
            raise ValueError("invalid redirect")
        if p.scheme == "http":
            loopback = host.lower() == "localhost"
            if not loopback:
                try:
                    loopback = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    loopback = False
            if not loopback:
                raise ValueError("invalid redirect")
        return uri

    def validate_client(self, client_id):
        p = self._verify(client_id, "tbmc1")
        rs = p.get("redirect_uris")
        if (
            p.get("v") != 1
            or not isinstance(rs, list)
            or not 1 <= len(rs) <= MAX_REDIRECTS
            or len(set(rs)) != len(rs)
        ):
            raise ValueError("invalid client")
        for r in rs:
            self._validate_redirect(r)
        return p

    def _subject(self, iid):
        return hmac.new(
            self.config.signing_key, f"subject:{iid}".encode(), hashlib.sha256
        ).hexdigest()

    def _match_invite(self, value):
        digest = hashlib.sha256(value.encode()).hexdigest()
        match = None
        for invite in self.config.invites:
            if hmac.compare_digest(digest, invite.secret_sha256):
                match = invite
        return match

    @staticmethod
    def _headers(scope, name):
        result = []
        for n, v in scope.get("headers", []):
            try:
                if n.decode("latin-1").lower() == name.lower():
                    result.append(v.decode("latin-1"))
            except (AttributeError, UnicodeDecodeError):
                pass
        return result

    def authenticate_bearer(self, token):
        if not self.enabled:
            return None
        try:
            c = self._verify(token, "tbma1")
        except ValueError:
            return None
        now = int(self._clock())
        if (
            c.get("v") != 1
            or c.get("iss") != self.config.issuer
            or c.get("aud") != self.config.resource
            or c.get("scope") != SCOPE
            or c.get("role") not in ("operator", "tester")
            or not isinstance(c.get("sub"), str)
            or not isinstance(c.get("iat"), int)
            or not isinstance(c.get("exp"), int)
            or c["iat"] > now
            or now >= c["exp"]
        ):
            return None
        return AuthPrincipal(c["role"], c["sub"], "oauth")

    def authenticate_request(self, scope, *, static_key):
        values = self._headers(scope, "authorization")
        if len(values) != 1 or not values[0].startswith("Bearer "):
            return None
        bearer = values[0][7:]
        if static_key and hmac.compare_digest(bearer, static_key):
            return AuthPrincipal("operator", None, "static_bearer")
        return self.authenticate_bearer(bearer)

    def record_authenticated(self, principal):
        if principal is None:
            return
        with self._lock:
            if principal.role == "operator":
                self._operator_requests += 1
            elif principal.role == "tester":
                self._tester_requests += 1
            if principal.method == "oauth" and principal.subject:
                self._subjects.add(principal.subject)

    def metrics(self):
        with self._lock:
            return {
                "operator_requests": self._operator_requests,
                "tester_requests": self._tester_requests,
                "unique_oauth_subjects": len(self._subjects),
            }

    def _purge_expired_locked(self, now: int) -> None:
        """Remove expired process-memory authorization state while holding the lock."""
        for store in (self._pending, self._codes):
            expired = [key for key, value in store.items() if now >= value["exp"]]
            for key in expired:
                store.pop(key, None)

    @staticmethod
    async def _body(receive):
        chunks = []
        size = 0
        while True:
            m = await receive()
            if m["type"] == "http.disconnect":
                break
            if m["type"] != "http.request":
                continue
            chunk = m.get("body", b"")
            size += len(chunk)
            if size > MAX_BODY:
                raise BodyTooLarge()
            chunks.append(chunk)
            if not m.get("more_body", False):
                break
        return b"".join(chunks)

    @staticmethod
    def _query(scope):
        try:
            return parse_qs(
                scope.get("query_string", b"").decode(), keep_blank_values=True
            )
        except UnicodeDecodeError:
            return {}

    @staticmethod
    def _one(values, name):
        items = values.get(name, [])
        if len(items) != 1:
            raise ValueError(name)
        return items[0]

    @staticmethod
    def _with_query(uri, fields):
        p = urlsplit(uri)
        addition = urlencode(fields)
        query = f"{p.query}&{addition}" if p.query else addition
        return urlunsplit((p.scheme, p.netloc, p.path, query, ""))

    async def _json(self, scope, receive, send, payload, status=200, headers=None):
        await JSONResponse(payload, status_code=status, headers=headers)(
            scope, receive, send
        )

    async def _metadata(self, scope, receive, send, authorization_server):
        if authorization_server:
            p = {
                "issuer": self.config.issuer,
                "authorization_endpoint": f"{self.config.issuer}/oauth/authorize",
                "token_endpoint": f"{self.config.issuer}/oauth/token",
                "registration_endpoint": f"{self.config.issuer}/oauth/register",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
                "scopes_supported": [SCOPE],
                "authorization_response_iss_parameter_supported": True,
            }
        else:
            p = {
                "resource": self.config.resource,
                "authorization_servers": [self.config.issuer],
                "bearer_methods_supported": ["header"],
                "scopes_supported": [SCOPE],
            }
        await self._json(scope, receive, send, p, headers={"cache-control": "no-store"})

    async def _register(self, scope, receive, send):
        types = self._headers(scope, "content-type")
        if (
            len(types) != 1
            or types[0].split(";", 1)[0].strip().lower() != "application/json"
        ):
            await self._json(
                scope, receive, send, {"error": "invalid_client_metadata"}, 415
            )
            return
        try:
            body = await self._body(receive)
        except BodyTooLarge:
            await self._json(
                scope, receive, send, {"error": "invalid_client_metadata"}, 413
            )
            return
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError()
            redirects = data.get("redirect_uris")
            if (
                not isinstance(redirects, list)
                or not 1 <= len(redirects) <= MAX_REDIRECTS
                or len(set(redirects)) != len(redirects)
            ):
                raise ValueError()
            redirects = [self._validate_redirect(r) for r in redirects]
            name = data.get("client_name", "MCP client")
            if (
                not isinstance(name, str)
                or len(name) > MAX_CLIENT_NAME
                or data.get("token_endpoint_auth_method", "none") != "none"
                or data.get("grant_types", ["authorization_code"])
                != ["authorization_code"]
                or data.get("response_types", ["code"]) != ["code"]
            ):
                raise ValueError()
        except (ValueError, TypeError, json.JSONDecodeError):
            await self._json(
                scope, receive, send, {"error": "invalid_redirect_uri"}, 400
            )
            return
        now = int(self._clock())
        cid = self._sign("tbmc1", {"v": 1, "iat": now, "redirect_uris": redirects})
        await self._json(
            scope,
            receive,
            send,
            {
                "client_id": cid,
                "client_id_issued_at": now,
                "redirect_uris": redirects,
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
            },
            201,
            {"cache-control": "no-store"},
        )

    async def _error_redirect(self, scope, receive, send, redirect, state):
        location = self._with_query(
            redirect,
            [
                ("error", "invalid_request"),
                ("state", state),
                ("iss", self.config.issuer),
            ],
        )
        await RedirectResponse(
            location, status_code=302, headers={"cache-control": "no-store"}
        )(scope, receive, send)

    async def _authorize_get(self, scope, receive, send):
        q = self._query(scope)
        try:
            cid = self._one(q, "client_id")
            client = self.validate_client(cid)
            redirect = self._one(q, "redirect_uri")
            if redirect not in client["redirect_uris"]:
                raise ValueError()
        except ValueError:
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_request"},
                400,
                {"cache-control": "no-store"},
            )
            return
        try:
            state = self._one(q, "state")
            if (
                not state
                or len(state) > 512
                or self._one(q, "response_type") != "code"
                or self._one(q, "resource") != self.config.resource
                or self._one(q, "code_challenge_method") != "S256"
            ):
                raise ValueError()
            challenge = self._one(q, "code_challenge")
            if not CHALLENGE_RE.fullmatch(challenge):
                raise ValueError()
        except ValueError:
            safe = q.get("state", [""])[0] if len(q.get("state", [])) == 1 else ""
            await self._error_redirect(scope, receive, send, redirect, safe)
            return
        now = int(self._clock())
        rid = self._token_factory(24)
        csrf = self._token_factory(24)
        with self._lock:
            self._purge_expired_locked(now)
            self._pending[rid] = {
                "exp": now + self.config.authorization_ttl_seconds,
                "iss": self.config.issuer,
                "client_id": cid,
                "redirect_uri": redirect,
                "state": state,
                "resource": self.config.resource,
                "challenge": challenge,
                "csrf": csrf,
            }
        page = f'''<!doctype html><html><head><meta charset="utf-8"><title>Authorize tube-bridge</title></head><body><main><h1>Authorize tube-bridge</h1><p>Enter the invite code provided for this controlled test.</p><form method="post" action="/oauth/authorize"><input type="hidden" name="request_id" value="{
            html.escape(rid, quote=True)
        }"><label>Invite code <input type="password" name="access_code" required autocomplete="one-time-code"></label><button type="submit">Authorize</button></form></main></body></html>'''
        r = HTMLResponse(
            page,
            headers={
                "cache-control": "no-store",
                "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
                "referrer-policy": "no-referrer",
                "x-content-type-options": "nosniff",
            },
        )
        r.set_cookie(
            "tb_oauth_csrf",
            csrf,
            max_age=self.config.authorization_ttl_seconds,
            secure=True,
            httponly=True,
            samesite="lax",
            path="/oauth/authorize",
        )
        await r(scope, receive, send)

    async def _authorize_post(self, scope, receive, send):
        types = self._headers(scope, "content-type")
        if (
            len(types) != 1
            or types[0].split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_request"},
                415,
                {"cache-control": "no-store"},
            )
            return
        try:
            body = await self._body(receive)
        except BodyTooLarge:
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_request"},
                413,
                {"cache-control": "no-store"},
            )
            return
        try:
            form = parse_qs(body.decode(), keep_blank_values=True)
            rid = self._one(form, "request_id")
            access = self._one(form, "access_code")
        except (ValueError, UnicodeDecodeError):
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_request"},
                400,
                {"cache-control": "no-store"},
            )
            return
        cookie_values = []
        for header in self._headers(scope, "cookie"):
            c = SimpleCookie()
            try:
                c.load(header)
            except Exception:
                continue
            if "tb_oauth_csrf" in c:
                cookie_values.append(c["tb_oauth_csrf"].value)
        now = int(self._clock())
        with self._lock:
            self._purge_expired_locked(now)
            pending = self._pending.get(rid)
        if pending is None:
            await self._json(
                scope,
                receive,
                send,
                {
                    "error": "access_denied",
                    "message": "Invalid or expired authorization request.",
                },
                401,
                {"cache-control": "no-store"},
            )
            return
        if len(cookie_values) != 1 or not hmac.compare_digest(
            cookie_values[0], pending["csrf"]
        ):
            await self._json(
                scope,
                receive,
                send,
                {
                    "error": "access_denied",
                    "message": "Invalid or expired authorization request.",
                },
                401,
                {"cache-control": "no-store"},
            )
            return
        invite = self._match_invite(access)
        if invite is None:
            await self._json(
                scope,
                receive,
                send,
                {
                    "error": "access_denied",
                    "message": "Invalid or expired authorization request.",
                },
                401,
                {"cache-control": "no-store"},
            )
            return
        with self._lock:
            pending = self._pending.pop(rid, None)
            if pending is not None:
                code = self._token_factory(32)
                self._codes[code] = {
                    **pending,
                    "exp": now + self.config.authorization_ttl_seconds,
                    "role": invite.role,
                    "sub": self._subject(invite.id),
                }
        if pending is None:
            await self._json(
                scope,
                receive,
                send,
                {
                    "error": "access_denied",
                    "message": "Invalid or expired authorization request.",
                },
                401,
                {"cache-control": "no-store"},
            )
            return
        location = self._with_query(
            pending["redirect_uri"],
            [("code", code), ("state", pending["state"]), ("iss", self.config.issuer)],
        )
        r = RedirectResponse(
            location, status_code=302, headers={"cache-control": "no-store"}
        )
        r.delete_cookie("tb_oauth_csrf", path="/oauth/authorize")
        await r(scope, receive, send)

    async def _token(self, scope, receive, send):
        types = self._headers(scope, "content-type")
        if (
            len(types) != 1
            or types[0].split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_request"},
                415,
                {"cache-control": "no-store"},
            )
            return
        try:
            body = await self._body(receive)
        except BodyTooLarge:
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_request"},
                413,
                {"cache-control": "no-store"},
            )
            return
        try:
            form = parse_qs(body.decode(), keep_blank_values=True)
            if self._one(form, "grant_type") != "authorization_code":
                raise ValueError()
            code = self._one(form, "code")
            cid = self._one(form, "client_id")
            redirect = self._one(form, "redirect_uri")
            verifier = self._one(form, "code_verifier")
            resource = self._one(form, "resource")
        except (ValueError, UnicodeDecodeError):
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_grant"},
                400,
                {"cache-control": "no-store"},
            )
            return
        now = int(self._clock())
        with self._lock:
            self._purge_expired_locked(now)
            record = self._codes.pop(code, None)
        valid = (
            record is not None
            and record["iss"] == self.config.issuer
            and cid == record["client_id"]
            and redirect == record["redirect_uri"]
            and resource == record["resource"]
            and bool(VERIFIER_RE.fullmatch(verifier))
        )
        if valid:
            valid = hmac.compare_digest(
                self._b64(hashlib.sha256(verifier.encode()).digest()),
                record["challenge"],
            )
        if not valid:
            await self._json(
                scope,
                receive,
                send,
                {"error": "invalid_grant"},
                400,
                {"cache-control": "no-store"},
            )
            return
        exp = now + self.config.access_token_ttl_seconds
        token = self._sign(
            "tbma1",
            {
                "v": 1,
                "iss": self.config.issuer,
                "aud": self.config.resource,
                "sub": record["sub"],
                "role": record["role"],
                "scope": SCOPE,
                "iat": now,
                "exp": exp,
                "jti": self._token_factory(16),
            },
        )
        await self._json(
            scope,
            receive,
            send,
            {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": self.config.access_token_ttl_seconds,
                "scope": SCOPE,
                "resource": self.config.resource,
            },
            200,
            {"cache-control": "no-store", "pragma": "no-cache"},
        )

    async def handle(self, scope, receive, send):
        if not self.enabled or scope.get("type") != "http":
            return False
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        if (
            path
            in (
                "/.well-known/oauth-protected-resource",
                "/.well-known/oauth-protected-resource/mcp",
            )
            and method == "GET"
        ):
            await self._metadata(scope, receive, send, False)
            return True
        if path == "/.well-known/oauth-authorization-server" and method == "GET":
            await self._metadata(scope, receive, send, True)
            return True
        if path == "/oauth/register" and method == "POST":
            await self._register(scope, receive, send)
            return True
        if path == "/oauth/authorize" and method == "GET":
            await self._authorize_get(scope, receive, send)
            return True
        if path == "/oauth/authorize" and method == "POST":
            await self._authorize_post(scope, receive, send)
            return True
        if path == "/oauth/token" and method == "POST":
            await self._token(scope, receive, send)
            return True
        if path in self.PUBLIC_PATHS:
            await self._json(scope, receive, send, {"error": "method_not_allowed"}, 405)
            return True
        return False

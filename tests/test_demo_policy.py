"""Frozen RED contracts for disposable-demo Data API allowance and privacy.

No live network calls.  Production module is intentionally absent at RED time.
"""

from concurrent.futures import ThreadPoolExecutor
import importlib
import ipaddress

import pytest


def policy_module():
    return importlib.import_module("tube_bridge.demo_policy")


def install_global_allowance(monkeypatch, policy):
    allowance = policy.DemoAllowance(salt=b"frozen-demo-policy-test-salt-32b")
    monkeypatch.setattr(policy, "_allowance", allowance)
    return allowance


def test_demo_policy_constants_are_fixed():
    policy = policy_module()
    assert policy.DEMO_DATA_API_LIMIT == 5
    assert policy.DEMO_CORPUS_TTL_SECONDS == 600


def test_demo_mode_is_disabled_by_default(monkeypatch):
    policy = policy_module()
    monkeypatch.delenv("TUBE_BRIDGE_DEMO_MODE", raising=False)
    assert policy.is_demo_mode() is False


def test_demo_mode_requires_exact_opt_in(monkeypatch):
    policy = policy_module()
    for value in ("", "0", "false", "yes"):
        monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", value)
        assert policy.is_demo_mode() is False
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    assert policy.is_demo_mode() is True


def test_first_five_operations_allowed_and_sixth_rejected():
    policy = policy_module()
    allowance = policy.DemoAllowance(salt=b"a" * 32)
    remaining = [allowance.consume("203.0.113.10") for _ in range(5)]
    assert remaining == [4, 3, 2, 1, 0]
    with pytest.raises(policy.DemoDataApiLimitExceeded) as exc:
        allowance.consume("203.0.113.10")
    assert exc.value.to_payload() == {
        "error": "demo_data_api_limit_exceeded",
        "message": "Disposable demo allowance exhausted for this process lifetime.",
        "limit": 5,
        "reset": "process_restart",
    }


def test_different_ips_have_independent_allowances():
    policy = policy_module()
    allowance = policy.DemoAllowance(salt=b"b" * 32)
    for _ in range(5):
        allowance.consume("203.0.113.1")
    with pytest.raises(policy.DemoDataApiLimitExceeded):
        allowance.consume("203.0.113.1")
    assert allowance.consume("203.0.113.2") == 4


def test_no_time_reset(monkeypatch):
    policy = policy_module()
    allowance = policy.DemoAllowance(salt=b"c" * 32)
    for _ in range(5):
        allowance.consume("198.51.100.8")
    # Advancing wall time cannot reset a clock-free process-lifetime allowance.
    monkeypatch.setattr("time.time", lambda: 10**12)
    with pytest.raises(policy.DemoDataApiLimitExceeded):
        allowance.consume("198.51.100.8")


def test_new_process_policy_instance_starts_empty():
    policy = policy_module()
    old = policy.DemoAllowance(salt=b"d" * 32)
    for _ in range(5):
        old.consume("2001:db8::1")
    fresh = policy.DemoAllowance(salt=b"e" * 32)
    assert fresh.metrics() == {
        "limit": 5,
        "allowed_total": 0,
        "rejected_total": 0,
        "client_buckets": 0,
    }
    assert fresh.consume("2001:db8::1") == 4


def test_concurrent_attempts_are_atomic_exactly_five_allowed():
    policy = policy_module()
    allowance = policy.DemoAllowance(salt=b"f" * 32)

    def attempt():
        try:
            allowance.consume("198.51.100.77")
            return "allowed"
        except policy.DemoDataApiLimitExceeded:
            return "rejected"

    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(10)))
    assert outcomes.count("allowed") == 5
    assert outcomes.count("rejected") == 5
    assert allowance.metrics()["allowed_total"] == 5
    assert allowance.metrics()["rejected_total"] == 5


def test_allowance_object_retains_no_raw_ipv4_or_ipv6():
    policy = policy_module()
    allowance = policy.DemoAllowance(salt=b"g" * 32)
    raw_values = ["203.0.113.99", "2001:db8::99"]
    for value in raw_values:
        allowance.consume(value)
    # Privacy contract without prescribing a private field name or layout.
    retained_state = repr(vars(allowance))
    for raw in raw_values:
        assert raw not in retained_state
        assert ipaddress.ip_address(raw).exploded not in retained_state
    assert allowance.metrics()["client_buckets"] == 2


def test_missing_identity_fails_closed_in_demo_mode(monkeypatch):
    policy = policy_module()
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    install_global_allowance(monkeypatch, policy)
    with policy.bind_client_ip(None):
        with pytest.raises(policy.DemoClientIdentityUnavailable) as exc:
            policy.consume_data_api_operation()
    assert exc.value.to_payload()["error"] == "demo_client_identity_unavailable"


def test_demo_disabled_requires_no_identity_and_does_not_count(monkeypatch):
    policy = policy_module()
    monkeypatch.delenv("TUBE_BRIDGE_DEMO_MODE", raising=False)
    allowance = install_global_allowance(monkeypatch, policy)
    with policy.bind_client_ip(None):
        assert policy.consume_data_api_operation() is None
    assert allowance.metrics()["allowed_total"] == 0


def test_missing_api_key_does_not_consume_allowance(monkeypatch):
    policy = policy_module()
    api = importlib.import_module("tube_bridge.youtube.api")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    allowance = install_global_allowance(monkeypatch, policy)
    with policy.bind_client_ip("203.0.113.12"):
        with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY not set"):
            api.api_call("videos", {"part": "snippet"})
    assert allowance.metrics()["allowed_total"] == 0


def test_attempted_network_failures_still_consume(monkeypatch):
    policy = policy_module()
    api = importlib.import_module("tube_bridge.youtube.api")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")
    allowance = install_global_allowance(monkeypatch, policy)

    def network_failure(*args, **kwargs):
        raise OSError("deterministic offline failure")

    monkeypatch.setattr(api.urllib.request, "urlopen", network_failure)
    with policy.bind_client_ip("203.0.113.13"):
        for _ in range(5):
            with pytest.raises(RuntimeError, match="NETWORK_ERROR"):
                api.api_call("videos", {"part": "snippet"})
        with pytest.raises(policy.DemoDataApiLimitExceeded):
            api.api_call("videos", {"part": "snippet"})
    assert allowance.metrics()["allowed_total"] == 5
    assert allowance.metrics()["rejected_total"] == 1


def test_keyless_tool_path_does_not_consume(monkeypatch):
    policy = policy_module()
    tools = importlib.import_module("tube_bridge.tools")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    allowance = install_global_allowance(monkeypatch, policy)
    monkeypatch.setattr(tools.yt, "run_ytdlp_multi", lambda *a, **k: ([], ""))
    with policy.bind_client_ip("203.0.113.14"):
        result = tools._channel_videos_sync("@offline", 1)
    assert result["total_videos"] == 0
    assert allowance.metrics()["allowed_total"] == 0


def test_channel_search_does_not_swallow_limit_exception(monkeypatch):
    policy = policy_module()
    api = importlib.import_module("tube_bridge.youtube.api")
    calls = []

    def fake_api_call(endpoint, params):
        calls.append(endpoint)
        if endpoint == "search":
            return {"items": [{"id": {"channelId": "UC1"}, "snippet": {"title": "A"}}]}
        raise policy.DemoDataApiLimitExceeded()

    monkeypatch.setattr(api, "api_call", fake_api_call)
    with pytest.raises(policy.DemoDataApiLimitExceeded):
        api.search_channels("test", 1)
    assert calls == ["search", "channels"]


def test_metrics_expose_aggregates_only():
    policy = policy_module()
    allowance = policy.DemoAllowance(salt=b"h" * 32)
    allowance.consume("203.0.113.31")
    metrics = allowance.metrics()
    assert metrics == {
        "limit": 5,
        "allowed_total": 1,
        "rejected_total": 0,
        "client_buckets": 1,
    }
    serialized = repr(metrics)
    assert "203.0.113.31" not in serialized

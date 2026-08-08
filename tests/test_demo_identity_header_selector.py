"""Frozen RED contracts for a Railway-safe identity-header selector."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest


def policy():
    return importlib.import_module("tube_bridge.demo_policy")


def scope(client="10.0.0.2", headers=()):
    return {
        "type": "http",
        "path": "/mcp",
        "client": (client, 43123),
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers],
    }


@pytest.mark.parametrize("selected", [
    "x-real-ip",
    "cf-connecting-ip",
    "true-client-ip",
    "x-client-ip",
])
def test_allowlisted_single_value_header_is_selected(monkeypatch, selected):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", selected)
    observed = module.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "192.0.2.200"),
        (selected, "198.51.100.42"),
    )))
    assert observed == "198.51.100.42"


def test_header_name_configuration_is_case_and_space_normalized(monkeypatch):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", "  X-Real-IP  ")
    assert module.extract_client_ip(scope(headers=(
        ("x-real-ip", "2001:0db8:0:0:0:0:0:1"),
    ))) == "2001:db8::1"


def test_unselected_xff_cannot_replace_selected_single_header(monkeypatch):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", "x-real-ip")
    assert module.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "192.0.2.10, 192.0.2.11"),
        ("x-real-ip", "198.51.100.50"),
    ))) == "198.51.100.50"


@pytest.mark.parametrize("bad_value", [
    "198.51.100.1, 198.51.100.2",
    "not-an-ip",
    "",
])
def test_selected_single_header_chain_or_invalid_value_fails_closed(monkeypatch, bad_value):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", "x-real-ip")
    assert module.extract_client_ip(scope(headers=(
        ("x-real-ip", bad_value),
        ("x-forwarded-for", "198.51.100.99"),
    ))) is None


def test_missing_selected_single_header_does_not_fall_back_to_xff(monkeypatch):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", "x-real-ip")
    assert module.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "198.51.100.99"),
    ))) is None


def test_duplicate_selected_single_header_fails_closed(monkeypatch):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", "x-real-ip")
    assert module.extract_client_ip(scope(headers=(
        ("x-real-ip", "198.51.100.1"),
        ("x-real-ip", "198.51.100.2"),
        ("x-forwarded-for", "198.51.100.99"),
    ))) is None


@pytest.mark.parametrize("selected", ["forwarded", "x-railway-client-ip", "host", ""])
def test_unknown_or_empty_header_configuration_fails_closed(monkeypatch, selected):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", selected)
    assert module.extract_client_ip(scope(headers=(
        (selected or "x-real-ip", "198.51.100.2"),
        ("x-forwarded-for", "198.51.100.3"),
    ))) is None


def test_default_selector_preserves_xff_right_hop_contract(monkeypatch):
    module = policy()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.delenv("TUBE_BRIDGE_CLIENT_IP_HEADER", raising=False)
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "2")
    assert module.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "192.0.2.1, 198.51.100.5, 203.0.113.9"),
    ))) == "198.51.100.5"


def test_selector_is_ignored_when_proxy_trust_is_off(monkeypatch):
    module = policy()
    monkeypatch.delenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.setenv("TUBE_BRIDGE_CLIENT_IP_HEADER", "x-real-ip")
    assert module.extract_client_ip(scope(
        client="192.0.2.77",
        headers=(("x-real-ip", "198.51.100.77"),),
    )) == "192.0.2.77"


def test_all_prior_python_freezes_remain_byte_identical():
    expected = {
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json":
            "c2e2278f3f802abcbca107491f79e3ccd5eac1a71a2ccb970d01b37ba1a60fa9",
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00029-demo-hardening-001-python.json":
            "32456b9c43cbb11b6eebe210ee1d42c4328c6175e79441fe74a15538728baa81",
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00037-ttl-race-addendum-001-python.json":
            "653a9e82e4f4910a069eac0a1ada145b38337fedc072038a14d990c4e5036dac",
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00039-ttl-atomic-selection-001-python.json":
            "0cdb5d70b028f67eaf1992b5529b53cc595b070198270f97ce83bfb7873a984b",
    }
    for path, expected_hash in expected.items():
        manifest_path = Path(path)
        assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == expected_hash
        manifest = json.loads(manifest_path.read_text())
        for item in manifest["test_files"]:
            assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"]

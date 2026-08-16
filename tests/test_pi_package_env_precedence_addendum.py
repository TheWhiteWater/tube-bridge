"""User storage overrides must retain the public tube-bridge environment contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_explicit_user_cache_overrides_the_pi_managed_default() -> None:
    source = (ROOT / "extensions" / "pi.ts").read_text(encoding="utf-8")

    assert "env: { ...server.env, ...buildSafeEnvironment() }" in source


def test_pi_data_root_override_is_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "TUBE_BRIDGE_PI_DATA" in readme
    assert "TUBE_BRIDGE_CACHE still takes precedence" in readme

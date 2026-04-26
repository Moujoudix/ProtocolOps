from pathlib import Path

from app.core.config import Settings
from consensus_bridge.main import consensus_auth_cached


def test_consensus_auth_cached_detects_nested_auth_artifacts(tmp_path: Path):
    auth_root = tmp_path / ".consensus-home" / ".mcp-auth" / "mcp-remote-0.1.37"
    auth_root.mkdir(parents=True)
    (auth_root / "session_tokens.json").write_text("{}", encoding="utf-8")

    settings = Settings(consensus_bridge_home=str(tmp_path / ".consensus-home"))

    assert consensus_auth_cached(settings) is True

"""tube-bridge — YouTube MCP server for AI agents.

17 tools: YouTube discovery, transcripts, timestamped frames, comments, help, and semantic corpora.
Zero API keys for core features. Optional Data API v3 upgrade.
"""

from .server import server
from .transport import create_app

__all__ = ["server", "create_app"]

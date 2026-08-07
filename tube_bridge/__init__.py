"""tube-bridge — YouTube MCP server for AI agents.

10 tools: search, discovery, transcripts, comments.
Zero API keys for core features. Optional Data API v3 upgrade.
"""

from .server import server
from .transport import create_app

__all__ = ["server", "create_app"]

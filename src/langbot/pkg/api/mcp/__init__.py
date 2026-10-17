"""LangBot MCP (Model Context Protocol) server.

This package exposes a subset of LangBot's HTTP service API as MCP tools so
that external AI agents can manage a LangBot instance through the MCP
protocol. The MCP server reuses the same API-key authentication as the HTTP
API, with permissions granted to the key.

See ``server.py`` for the tool surface and ``mount.py`` for the ASGI
integration with the Quart HTTP app.
"""

from .server import LangBotMCPServer

__all__ = ['LangBotMCPServer']

"""Compatibility shim across MCP Python SDK major versions.

`mcp` 2.0 removed `mcp.server.fastmcp` and renamed the high-level server
class to `MCPServer`. Everything the package needs is re-exported from here so
no other module imports `mcp.server.*` directly.
"""

from __future__ import annotations

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as FastMCP

    MCP_MAJOR = 2
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

    MCP_MAJOR = 1

__all__ = ["MCP_MAJOR", "FastMCP"]

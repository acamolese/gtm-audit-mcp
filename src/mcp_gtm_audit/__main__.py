"""Entry point for the mcp-gtm-audit CLI.

Usage:
    mcp-gtm-audit            # start MCP server (stdio)
    mcp-gtm-audit auth       # run interactive OAuth flow
"""

from __future__ import annotations

import sys


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "auth":
        from .authorize import run_oauth_flow

        run_oauth_flow()
        return 0

    from .server import mcp

    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Entry point for the mcp-gtm-audit CLI.

Usage:
    mcp-gtm-audit            start the MCP server (stdio)
    mcp-gtm-audit auth       run the OAuth flow (read-only, or read+edit with GTM_ALLOW_WRITE=1)
    mcp-gtm-audit doctor     check credentials, scopes and API access
    mcp-gtm-audit version    print the version
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    args = sys.argv[1:]
    command = args[0] if args else "serve"

    if command == "auth":
        from .authorize import run_oauth_flow

        run_oauth_flow()
        return 0

    if command == "doctor":
        from .diagnostics import doctor_report

        report = doctor_report()
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1

    if command == "version":
        from . import __version__

        print(__version__)
        return 0

    if command not in ("serve",):
        print(__doc__, file=sys.stderr)
        return 2

    from .server import mcp

    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""OAuth2 authorization flow for Google Tag Manager.

Runs a loopback flow: opens the system browser, listens on a localhost port for
the callback, exchanges the code for a refresh token and saves it to the XDG
token file. The scopes requested follow the mode: read-only by default, read
plus `tagmanager.edit.containers` when GTM_ALLOW_WRITE is set.

On a headless machine, export GTM_REFRESH_TOKEN instead and skip this.
"""

from __future__ import annotations

import contextlib
import http.server
import json
import socket
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone

from . import config

PREFERRED_PORT = 8080


def _free_port() -> int:
    with socket.socket() as probe:
        try:
            probe.bind(("localhost", PREFERRED_PORT))
            return PREFERRED_PORT
        except OSError:
            probe.bind(("localhost", 0))
            return probe.getsockname()[1]


def run_oauth_flow() -> None:
    oauth = config.load_oauth_client()
    client_id = oauth["client_id"]
    client_secret = oauth["client_secret"]
    scopes = config.required_scopes()
    port = _free_port()
    redirect_uri = f"http://localhost:{port}"

    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
        }
    )

    authorization_code: str | None = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            nonlocal authorization_code
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            authorization_code = params.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization complete</h1><p>You can close this window.</p>")

        def log_message(self, format, *args):  # noqa: A002
            pass

    mode = "read + edit containers (write mode)" if config.write_enabled() else "read-only"
    print(f"Requesting scopes: {mode}")
    print(f"Open this URL in your browser to authorize:\n\n{auth_url}\n")
    with contextlib.suppress(webbrowser.Error):
        webbrowser.open(auth_url)
    print(f"Waiting for the callback on {redirect_uri} ...")

    server = http.server.HTTPServer(("localhost", port), Handler)
    server.handle_request()

    if not authorization_code:
        print("Error: no authorization code received.")
        return

    print("Code received, exchanging it for a refresh token...")
    token_data = urllib.parse.urlencode(
        {
            "code": authorization_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()

    req = urllib.request.Request(  # noqa: S310 - fixed https endpoint
        "https://oauth2.googleapis.com/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        token_response = json.loads(resp.read())

    expires_in = int(token_response.get("expires_in", 3599))
    token_response["expiry"] = (
        (datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)).replace(tzinfo=None).isoformat()
    )
    token_response["client_id"] = client_id
    token_response["client_secret"] = client_secret
    token_response["token_uri"] = oauth.get("token_uri", "https://oauth2.googleapis.com/token")
    # What Google actually granted, not what was asked for.
    token_response["scopes"] = (token_response.get("scope") or " ".join(scopes)).split()

    config.save_token(token_response)

    print(f"\nToken saved to {config.token_file_path()}")
    print(f"Granted scopes: {' '.join(token_response['scopes'])}")
    print("\nYou can now run `mcp-gtm-audit` to start the MCP server.")


if __name__ == "__main__":
    run_oauth_flow()

"""Configuration and credential resolution for the GTM audit MCP server.

Credentials are resolved in this order (highest priority first):

1. Environment variables
   - GTM_CLIENT_ID, GTM_CLIENT_SECRET, GTM_REFRESH_TOKEN (required together)
2. XDG config directory
   - $XDG_CONFIG_HOME/mcp-gtm-audit/oauth_credentials.json
   - $XDG_CONFIG_HOME/mcp-gtm-audit/token.json
   - Defaults to ~/.config/mcp-gtm-audit/ on Linux/macOS
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

APP_NAME = "mcp-gtm-audit"

SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.readonly",
]


def xdg_config_home() -> Path:
    env = os.environ.get("XDG_CONFIG_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config"


def config_dir() -> Path:
    path = xdg_config_home() / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _credential_paths(filename: str) -> list[Path]:
    return [config_dir() / filename]


# ---------------------------------------------------------------------------
# OAuth client (client_id + client_secret)
# ---------------------------------------------------------------------------

def _oauth_from_env() -> dict | None:
    cid = os.environ.get("GTM_CLIENT_ID")
    secret = os.environ.get("GTM_CLIENT_SECRET")
    if cid and secret:
        return {
            "client_id": cid,
            "client_secret": secret,
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        }
    return None


def _oauth_from_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if "installed" in data:
        return data["installed"]
    if "web" in data:
        return data["web"]
    return data


def load_oauth_client() -> dict:
    env_data = _oauth_from_env()
    if env_data:
        return env_data
    for candidate in _credential_paths("oauth_credentials.json"):
        data = _oauth_from_file(candidate)
        if data:
            return data
    raise FileNotFoundError(
        "No OAuth client credentials found. Set GTM_CLIENT_ID and GTM_CLIENT_SECRET "
        f"environment variables, or place oauth_credentials.json in {config_dir()}/."
    )


# ---------------------------------------------------------------------------
# Token (access_token + refresh_token + expiry)
# ---------------------------------------------------------------------------

def _token_from_env() -> dict | None:
    refresh = os.environ.get("GTM_REFRESH_TOKEN")
    if refresh:
        return {
            "refresh_token": refresh,
            "access_token": os.environ.get("GTM_ACCESS_TOKEN"),
            "expiry": os.environ.get("GTM_TOKEN_EXPIRY"),
            "__source__": "env",
        }
    return None


def _token_from_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    data["__source__"] = str(path)
    return data


def token_file_path() -> Path:
    for candidate in _credential_paths("token.json"):
        if candidate.exists():
            return candidate
    return config_dir() / "token.json"


def load_token() -> dict:
    env_data = _token_from_env()
    if env_data:
        return env_data
    for candidate in _credential_paths("token.json"):
        data = _token_from_file(candidate)
        if data:
            return data
    raise FileNotFoundError(
        "No OAuth token found. Set GTM_REFRESH_TOKEN environment variable, or run "
        "`mcp-gtm-audit auth` to authorize the app and generate one."
    )


def save_token(token: dict) -> None:
    if token.get("__source__") == "env":
        return
    path = token_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    to_write = {k: v for k, v in token.items() if not k.startswith("__")}
    path.write_text(json.dumps(to_write, indent=2), encoding="utf-8")


def update_saved_token(access_token: str, expiry: datetime | None) -> None:
    token = load_token()
    if token.get("__source__") == "env":
        return
    token["access_token"] = access_token
    if expiry:
        token["expiry"] = expiry.isoformat()
    save_token(token)

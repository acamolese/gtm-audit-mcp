"""Configuration, credential resolution and the read/write mode switch.

Credentials are resolved in this order (highest priority first):

1. Environment variables: GTM_CLIENT_ID, GTM_CLIENT_SECRET, GTM_REFRESH_TOKEN
2. $XDG_CONFIG_HOME/mcp-gtm-audit/oauth_credentials.json and token.json
   (defaults to ~/.config/mcp-gtm-audit/)

The server is read-only unless GTM_ALLOW_WRITE is set to 1/true/yes. In write
mode it asks for `tagmanager.edit.containers` on top of `tagmanager.readonly`,
which allows changes inside workspaces. It never asks for the version or
publish scopes: creating a version and publishing stay in the GTM UI, after a
human has looked at the workspace in Preview.
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime
from pathlib import Path

APP_NAME = "mcp-gtm-audit"

READ_SCOPE = "https://www.googleapis.com/auth/tagmanager.readonly"
EDIT_SCOPE = "https://www.googleapis.com/auth/tagmanager.edit.containers"

_TRUE = {"1", "true", "yes", "on"}


def write_enabled() -> bool:
    """True when GTM_ALLOW_WRITE opts the server into workspace writes."""
    return os.environ.get("GTM_ALLOW_WRITE", "").strip().lower() in _TRUE


def required_scopes() -> list[str]:
    """Scopes the current mode needs: read-only, or read plus container edit."""
    scopes = [READ_SCOPE]
    if write_enabled():
        scopes.append(EDIT_SCOPE)
    return scopes


def reports_dir() -> Path:
    """Where gtm_audit and gtm_export write by default (GTM_REPORTS_DIR or ~/Reports)."""
    env = os.environ.get("GTM_REPORTS_DIR")
    return Path(env).expanduser() if env else Path.home() / "Reports"


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
        "No OAuth client credentials found. Set GTM_CLIENT_ID and GTM_CLIENT_SECRET, "
        f"or place oauth_credentials.json in {config_dir()}/."
    )


# ---------------------------------------------------------------------------
# Token (access_token + refresh_token + expiry + scopes)
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
        "No OAuth token found. Set GTM_REFRESH_TOKEN, or run `mcp-gtm-audit auth` "
        "to authorize the app and create one."
    )


def granted_scopes(token: dict) -> list[str]:
    """Scopes recorded with the token; empty when unknown (env tokens)."""
    scopes = token.get("scopes") or token.get("scope") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    return list(scopes)


def save_token(token: dict) -> None:
    if token.get("__source__") == "env":
        return
    path = token_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    to_write = {k: v for k, v in token.items() if not k.startswith("__")}
    path.write_text(json.dumps(to_write, indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):  # platform dependent
        path.chmod(0o600)


def update_saved_token(access_token: str, expiry: datetime | None) -> None:
    token = load_token()
    if token.get("__source__") == "env":
        return
    token["access_token"] = access_token
    if expiry:
        token["expiry"] = expiry.isoformat()
    save_token(token)

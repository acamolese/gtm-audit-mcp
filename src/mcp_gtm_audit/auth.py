"""Build google-auth Credentials from the resolved configuration."""

from __future__ import annotations

from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from . import config


class ScopeError(RuntimeError):
    """The saved token does not carry a scope the current mode needs."""


def _parse_expiry(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except (TypeError, ValueError):
        return None


def check_scopes(token: dict) -> None:
    """Fail early, with a fix, when write mode is on but the token is read-only.

    Tokens from environment variables carry no scope list, so they are trusted;
    Google answers 403 on the first write if the scope is really missing.
    """
    if not config.write_enabled():
        return
    granted = config.granted_scopes(token)
    if granted and config.EDIT_SCOPE not in granted:
        raise ScopeError(
            "GTM_ALLOW_WRITE is set but the saved token only has the read-only scope. "
            "Run `GTM_ALLOW_WRITE=1 mcp-gtm-audit auth` once to grant tagmanager.edit.containers."
        )


def load_credentials() -> Credentials:
    oauth = config.load_oauth_client()
    token = config.load_token()
    check_scopes(token)

    creds = Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri=oauth.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
        scopes=config.granted_scopes(token) or config.required_scopes(),
        expiry=_parse_expiry(token.get("expiry")),
    )
    if not creds.valid:
        creds.refresh(Request())
        config.update_saved_token(creds.token, creds.expiry)
    return creds

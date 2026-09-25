"""Build google-auth Credentials from the resolved config."""

from __future__ import annotations

from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from . import config


def _parse_expiry(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except (TypeError, ValueError):
        return None


def load_credentials() -> Credentials:
    oauth = config.load_oauth_client()
    token = config.load_token()

    creds = Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri=oauth.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
        scopes=token.get("scopes") or config.SCOPES,
        expiry=_parse_expiry(token.get("expiry")),
    )
    if not creds.valid:
        creds.refresh(Request())
        config.update_saved_token(creds.token, creds.expiry)
    return creds

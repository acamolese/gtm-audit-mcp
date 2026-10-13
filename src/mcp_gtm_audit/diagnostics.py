"""`doctor`: say in one call whether the setup can work, and in which mode."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from . import __version__, config
from .auth import ScopeError, load_credentials
from .client import GTMClient


def _sdk_version() -> str:
    try:
        return version("mcp")
    except PackageNotFoundError:  # pragma: no cover
        return "unknown"


def doctor_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "package": f"mcp-gtm-audit {__version__}",
        "mcp_sdk": _sdk_version(),
        "write_mode": config.write_enabled(),
        "scopes_required": config.required_scopes(),
        "config_dir": str(config.config_dir()),
        "reports_dir": str(config.reports_dir()),
        "ok": False,
    }
    try:
        token = config.load_token()
        report["token_source"] = token.get("__source__")
        report["scopes_granted"] = config.granted_scopes(token) or ["(unknown: token from environment)"]
    except FileNotFoundError as exc:
        report["error"] = str(exc)
        return report
    try:
        creds = load_credentials()
    except ScopeError as exc:
        report["error"] = str(exc)
        return report
    except Exception as exc:  # noqa: BLE001 - any auth failure is the diagnosis
        report["error"] = f"Credentials could not be refreshed: {exc}"
        return report
    try:
        accounts = GTMClient(creds).list_accounts()
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"Tag Manager API call failed: {exc}"
        return report
    report["accounts_visible"] = len(accounts)
    report["ok"] = True
    if config.write_enabled() and config.EDIT_SCOPE not in (report.get("scopes_granted") or []):
        report["note"] = (
            "Write mode is on but the token's scopes are unknown; the first write will tell "
            "if tagmanager.edit.containers was granted."
        )
    return report

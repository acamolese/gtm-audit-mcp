"""Server FastMCP per audit Google Tag Manager."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .auth import load_credentials
from .audit import run_audit
from .client import GTMClient
from .diff import diff_snapshots
from .report import render_audit_html
from .tracking import validate_tracking

mcp = FastMCP("gtm-audit")

REPORTS_BASE = Path.home() / "Reports"


def _client() -> GTMClient:
    return GTMClient(load_credentials())


def _slug(text: str) -> str:
    text = re.sub(r"[^a-z0-9-]+", "-", text.lower())
    return re.sub(r"-+", "-", text).strip("-") or "report"


def _resolve_workspace(client: GTMClient, account_id: str, container_id: str, workspace_id: str | None) -> str:
    if workspace_id:
        return workspace_id
    workspaces = client.list_workspaces(account_id, container_id)
    if not workspaces:
        raise RuntimeError("Nessun workspace trovato per il container.")
    # Default workspace si chiama "Default Workspace"
    for w in workspaces:
        if w.get("name", "").lower().startswith("default"):
            return w["workspaceId"]
    return workspaces[0]["workspaceId"]


# ===========================================================================
# Inventario
# ===========================================================================


@mcp.tool()
def list_accounts() -> str:
    """Elenca gli account GTM accessibili con l'utente OAuth corrente."""
    client = _client()
    accounts = [
        {"accountId": a.get("accountId"), "name": a.get("name"), "path": a.get("path")}
        for a in client.list_accounts()
    ]
    return json.dumps(accounts, indent=2, ensure_ascii=False)


@mcp.tool()
def list_containers(account_id: str) -> str:
    """Elenca i container GTM di un account.

    Args:
        account_id: ID account GTM (numerico).
    """
    containers = [
        {
            "containerId": c.get("containerId"),
            "name": c.get("name"),
            "publicId": c.get("publicId"),
            "usageContext": c.get("usageContext", []),
            "domainName": c.get("domainName", []),
        }
        for c in _client().list_containers(account_id)
    ]
    return json.dumps(containers, indent=2, ensure_ascii=False)


@mcp.tool()
def list_workspaces(account_id: str, container_id: str) -> str:
    """Elenca i workspace di un container."""
    items = [
        {"workspaceId": w.get("workspaceId"), "name": w.get("name"), "description": w.get("description", "")}
        for w in _client().list_workspaces(account_id, container_id)
    ]
    return json.dumps(items, indent=2, ensure_ascii=False)


@mcp.tool()
def list_versions(account_id: str, container_id: str) -> str:
    """Elenca gli header delle versioni pubblicate del container."""
    items = [
        {
            "containerVersionId": v.get("containerVersionId"),
            "name": v.get("name"),
            "deleted": v.get("deleted", False),
            "numTags": v.get("numTags"),
            "numTriggers": v.get("numTriggers"),
            "numVariables": v.get("numVariables"),
        }
        for v in _client().list_versions(account_id, container_id)
    ]
    return json.dumps(items, indent=2, ensure_ascii=False)


@mcp.tool()
def list_tags(account_id: str, container_id: str, workspace_id: str = "") -> str:
    """Elenca i tag di un workspace (default: Default Workspace)."""
    client = _client()
    wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
    items = [
        {
            "tagId": t.get("tagId"),
            "name": t.get("name"),
            "type": t.get("type"),
            "paused": t.get("paused", False),
            "firingTriggerId": t.get("firingTriggerId", []),
            "blockingTriggerId": t.get("blockingTriggerId", []),
        }
        for t in client.list_tags(account_id, container_id, wid)
    ]
    return json.dumps(items, indent=2, ensure_ascii=False)


@mcp.tool()
def list_triggers(account_id: str, container_id: str, workspace_id: str = "") -> str:
    """Elenca i trigger di un workspace."""
    client = _client()
    wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
    items = [
        {"triggerId": t.get("triggerId"), "name": t.get("name"), "type": t.get("type")}
        for t in client.list_triggers(account_id, container_id, wid)
    ]
    return json.dumps(items, indent=2, ensure_ascii=False)


@mcp.tool()
def list_variables(account_id: str, container_id: str, workspace_id: str = "") -> str:
    """Elenca le variabili custom di un workspace."""
    client = _client()
    wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
    items = [
        {"variableId": v.get("variableId"), "name": v.get("name"), "type": v.get("type")}
        for v in client.list_variables(account_id, container_id, wid)
    ]
    return json.dumps(items, indent=2, ensure_ascii=False)


# ===========================================================================
# Audit completo
# ===========================================================================


@mcp.tool()
def gtm_audit(
    account_id: str,
    container_id: str,
    workspace_id: str = "",
    use_live_version: bool = False,
    output_dir: str = "",
    client_slug: str = "",
) -> str:
    """Esegue l'audit completo del container e genera report HTML + JSON.

    Args:
        account_id: ID account GTM.
        container_id: ID container GTM (numerico interno, NON il GTM-XXXX).
        workspace_id: ID workspace; vuoto = Default Workspace.
        use_live_version: Se True ignora il workspace e analizza la versione pubblicata.
        output_dir: Directory destinazione; default ~/Reports/<client_slug or container>/.
        client_slug: Slug cliente per cartella report; default = nome container.
    """
    client = _client()
    container_meta = next(
        (c for c in client.list_containers(account_id) if c.get("containerId") == container_id),
        {"name": container_id, "publicId": container_id},
    )
    label = f"{container_meta.get('name','?')} ({container_meta.get('publicId','')})"

    if use_live_version:
        snapshot = client.version_snapshot(account_id, container_id, "live")
    else:
        wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
        snapshot = client.workspace_snapshot(account_id, container_id, wid)

    audit = run_audit(snapshot)
    tracking = validate_tracking(snapshot)

    slug = _slug(client_slug or container_meta.get("name") or container_id)
    base = Path(output_dir) if output_dir else REPORTS_BASE / slug
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")

    html_path = base / f"gtm-audit-{stamp}.html"
    json_path = base / f"gtm-audit-{stamp}.json"
    html_path.write_text(render_audit_html(audit.to_dict(), label, tracking), encoding="utf-8")
    json_path.write_text(
        json.dumps({"audit": audit.to_dict(), "tracking": tracking}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return json.dumps({
        "container": label,
        "stats": audit.stats,
        "tracking_findings": len(tracking.get("findings", [])),
        "html_report": str(html_path),
        "json_report": str(json_path),
    }, indent=2, ensure_ascii=False)


# ===========================================================================
# Diff
# ===========================================================================


@mcp.tool()
def gtm_diff(
    account_id: str,
    container_id: str,
    base_ref: str = "live",
    head_ref: str = "workspace",
    workspace_id: str = "",
) -> str:
    """Confronta due snapshot del container.

    Args:
        account_id: ID account GTM.
        container_id: ID container.
        base_ref: 'live' oppure ID di una versione pubblicata.
        head_ref: 'workspace' (usa workspace_id) oppure ID di una versione.
        workspace_id: ID workspace per head_ref='workspace' (default: Default Workspace).
    """
    client = _client()
    base = (
        client.version_snapshot(account_id, container_id, base_ref)
        if base_ref != "workspace"
        else client.workspace_snapshot(
            account_id, container_id,
            _resolve_workspace(client, account_id, container_id, workspace_id or None),
        )
    )
    head = (
        client.workspace_snapshot(
            account_id, container_id,
            _resolve_workspace(client, account_id, container_id, workspace_id or None),
        )
        if head_ref == "workspace"
        else client.version_snapshot(account_id, container_id, head_ref)
    )
    return json.dumps(diff_snapshots(base, head), indent=2, ensure_ascii=False)


# ===========================================================================
# Validazione tracciamento standalone
# ===========================================================================


@mcp.tool()
def gtm_tracking_validation(
    account_id: str,
    container_id: str,
    workspace_id: str = "",
    use_live_version: bool = False,
) -> str:
    """Restituisce la mappa eventi GA4/Ads/Meta e i finding di tracciamento."""
    client = _client()
    snapshot = (
        client.version_snapshot(account_id, container_id, "live")
        if use_live_version
        else client.workspace_snapshot(
            account_id, container_id,
            _resolve_workspace(client, account_id, container_id, workspace_id or None),
        )
    )
    return json.dumps(validate_tracking(snapshot), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()

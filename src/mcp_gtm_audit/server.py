"""MCP surface: argument handling, JSON formatting and the read/write split.

Read tools are always registered. Write tools exist only when the process was
started with GTM_ALLOW_WRITE set, and even then they only touch workspaces: no
tool creates a version or publishes, so every change goes through GTM Preview
and a human click before it reaches a site.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from ._compat import FastMCP
from .audit import run_audit
from .auth import load_credentials
from .client import GTMClient
from .diagnostics import doctor_report
from .diff import diff_snapshots
from .export import build_export, export_counts
from .i18n import normalize_language
from .report import render_audit_html
from .tracking import validate_tracking

mcp = FastMCP("gtm-audit")

REVIEW_NEXT_STEP = (
    "Review the workspace in GTM Preview, then create a version and publish from the GTM UI. "
    "This server never publishes."
)


def _client() -> GTMClient:
    return GTMClient(load_credentials())


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _slug(text: str) -> str:
    text = re.sub(r"[^a-z0-9-]+", "-", text.lower())
    return re.sub(r"-+", "-", text).strip("-") or "report"


def _stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M")


def _resolve_workspace(client: GTMClient, account_id: str, container_id: str, workspace_id: str | None) -> str:
    if workspace_id:
        return workspace_id
    workspaces = client.list_workspaces(account_id, container_id)
    if not workspaces:
        raise RuntimeError("The container has no workspace.")
    for w in workspaces:
        if w.get("name", "").lower().startswith("default"):
            return w["workspaceId"]
    return workspaces[0]["workspaceId"]


def _container_label(client: GTMClient, account_id: str, container_id: str) -> tuple[dict, str]:
    meta = next(
        (c for c in client.list_containers(account_id) if c.get("containerId") == container_id),
        {"name": container_id, "publicId": container_id, "accountId": account_id, "containerId": container_id},
    )
    return meta, f"{meta.get('name', '?')} ({meta.get('publicId', '')})"


def _snapshot(client: GTMClient, account_id: str, container_id: str, workspace_id: str, use_live: bool) -> dict:
    if use_live:
        return client.version_snapshot(account_id, container_id, "live")
    wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
    return client.workspace_snapshot(account_id, container_id, wid)


def _parse_body(raw: str, what: str) -> dict:
    try:
        body = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ValueError(f"{what} must be a JSON object: {exc}") from exc
    if not isinstance(body, dict):
        raise ValueError(f"{what} must be a JSON object, got {type(body).__name__}.")
    return body


def _entity_summary(kind: str, entity: dict) -> dict:
    return {
        "kind": kind,
        "id": entity.get(f"{kind}Id") or entity.get("workspaceId"),
        "name": entity.get("name"),
        "type": entity.get("type"),
        "fingerprint": entity.get("fingerprint"),
        "paused": entity.get("paused"),
        "firingTriggerId": entity.get("firingTriggerId"),
    }


# ===========================================================================
# Inventory (always available)
# ===========================================================================


@mcp.tool()
def gtm_doctor() -> str:
    """Check credentials, granted scopes, write mode and API access. Call this first when something fails."""
    return _dump(doctor_report())


@mcp.tool()
def list_accounts() -> str:
    """List the GTM accounts visible to the authorized Google user."""
    accounts = [
        {"accountId": a.get("accountId"), "name": a.get("name"), "path": a.get("path")}
        for a in _client().list_accounts()
    ]
    return _dump(accounts)


@mcp.tool()
def list_containers(account_id: str) -> str:
    """List the containers of an account, with the numeric containerId the other tools need.

    Args:
        account_id: numeric GTM account id.
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
    return _dump(containers)


@mcp.tool()
def list_workspaces(account_id: str, container_id: str) -> str:
    """List the workspaces of a container (id, name, description)."""
    items = [
        {"workspaceId": w.get("workspaceId"), "name": w.get("name"), "description": w.get("description", "")}
        for w in _client().list_workspaces(account_id, container_id)
    ]
    return _dump(items)


@mcp.tool()
def list_versions(account_id: str, container_id: str) -> str:
    """List the published version headers of a container (id, name, entity counts)."""
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
    return _dump(items)


@mcp.tool()
def list_tags(account_id: str, container_id: str, workspace_id: str = "") -> str:
    """List the tags of a workspace (default: Default Workspace) with type, paused state and trigger ids."""
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
    return _dump(items)


@mcp.tool()
def list_triggers(account_id: str, container_id: str, workspace_id: str = "") -> str:
    """List the triggers of a workspace (id, name, type)."""
    client = _client()
    wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
    items = [
        {"triggerId": t.get("triggerId"), "name": t.get("name"), "type": t.get("type")}
        for t in client.list_triggers(account_id, container_id, wid)
    ]
    return _dump(items)


@mcp.tool()
def list_variables(account_id: str, container_id: str, workspace_id: str = "") -> str:
    """List the user-defined variables of a workspace (id, name, type)."""
    client = _client()
    wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
    items = [
        {"variableId": v.get("variableId"), "name": v.get("name"), "type": v.get("type")}
        for v in client.list_variables(account_id, container_id, wid)
    ]
    return _dump(items)


@mcp.tool()
def get_entity(account_id: str, container_id: str, kind: str, entity_id: str, workspace_id: str = "") -> str:
    """Return one tag, trigger, variable or folder in full (parameters, triggers, consent settings).

    Use it before update_* to see the exact resource shape, and to copy an
    existing entity as the starting point for a new one.

    Args:
        kind: tag, trigger, variable or folder.
        entity_id: the tagId / triggerId / variableId / folderId.
    """
    client = _client()
    wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
    return _dump(client.get_entity(account_id, container_id, wid, kind, entity_id))


# ===========================================================================
# Analysis (always available)
# ===========================================================================


@mcp.tool()
def gtm_audit(
    account_id: str,
    container_id: str,
    workspace_id: str = "",
    use_live_version: bool = False,
    output_dir: str = "",
    client_slug: str = "",
    language: str = "en",
) -> str:
    """Run the full audit and write an HTML plus a JSON report; returns stats and the file paths.

    Args:
        account_id: numeric GTM account id.
        container_id: numeric container id (not the GTM-XXXX public id).
        workspace_id: workspace to audit; empty = Default Workspace.
        use_live_version: audit the published version instead of a workspace.
        output_dir: where to write; default <reports dir>/<client_slug or container name>/.
        client_slug: folder name under the reports dir; default = container name.
        language: en or it, for the report and the issue wording.
    """
    client = _client()
    lang = normalize_language(language)
    meta, label = _container_label(client, account_id, container_id)
    snapshot = _snapshot(client, account_id, container_id, workspace_id, use_live_version)

    audit = run_audit(snapshot).to_dict(lang)
    tracking = validate_tracking(snapshot, lang)

    slug = _slug(client_slug or meta.get("name") or container_id)
    base = Path(output_dir).expanduser() if output_dir else config.reports_dir() / slug
    base.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    html_path = base / f"gtm-audit-{stamp}.html"
    json_path = base / f"gtm-audit-{stamp}.json"
    html_path.write_text(render_audit_html(audit, label, tracking, lang), encoding="utf-8")
    json_path.write_text(_dump({"audit": audit, "tracking": tracking}), encoding="utf-8")

    return _dump(
        {
            "container": label,
            "snapshot": audit["snapshot"],
            "stats": audit["stats"],
            "issues": audit["issues"],
            "tracking_findings": tracking["findings"],
            "html_report": str(html_path),
            "json_report": str(json_path),
        }
    )


@mcp.tool()
def gtm_diff(
    account_id: str,
    container_id: str,
    base_ref: str = "live",
    head_ref: str = "workspace",
    workspace_id: str = "",
) -> str:
    """Compare two snapshots: added, removed and modified entities with the fields that changed.

    Args:
        base_ref: 'live', a published version id, or 'workspace'.
        head_ref: 'workspace' (uses workspace_id) or a version id.
        workspace_id: workspace for 'workspace' refs; empty = Default Workspace.
    """
    client = _client()

    def load(ref: str) -> dict:
        if ref == "workspace":
            wid = _resolve_workspace(client, account_id, container_id, workspace_id or None)
            return client.workspace_snapshot(account_id, container_id, wid)
        return client.version_snapshot(account_id, container_id, ref)

    return _dump(diff_snapshots(load(base_ref), load(head_ref)))


@mcp.tool()
def gtm_tracking_validation(
    account_id: str,
    container_id: str,
    workspace_id: str = "",
    use_live_version: bool = False,
    language: str = "en",
) -> str:
    """Map GA4 events per Measurement ID, Google Ads conversions, Meta pixels and server-side hints, with findings."""
    client = _client()
    snapshot = _snapshot(client, account_id, container_id, workspace_id, use_live_version)
    return _dump(validate_tracking(snapshot, normalize_language(language)))


@mcp.tool()
def gtm_export(
    account_id: str,
    container_id: str,
    workspace_id: str = "",
    use_live_version: bool = False,
    output_path: str = "",
) -> str:
    """Write a container export JSON in GTM's own import format and return its path.

    The file can be imported from Admin > Import container (merge or overwrite,
    always into a workspace), which is the safe path when write mode is off.

    Args:
        output_path: file to write; default <reports dir>/<container>/gtm-export-<stamp>.json.
    """
    client = _client()
    meta, label = _container_label(client, account_id, container_id)
    container = client.get_container(account_id, container_id)
    snapshot = _snapshot(client, account_id, container_id, workspace_id, use_live_version)
    if snapshot.get("source") == "workspace":
        snapshot["customTemplates"] = client.list_templates(account_id, container_id, snapshot["workspaceId"])
    export = build_export(container, snapshot)

    path = (
        Path(output_path).expanduser()
        if output_path
        else config.reports_dir() / _slug(meta.get("name") or container_id) / f"gtm-export-{_stamp()}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(export), encoding="utf-8")
    return _dump(
        {"container": label, "source": snapshot.get("source"), "path": str(path), "counts": export_counts(export)}
    )


# ===========================================================================
# Writes (registered only with GTM_ALLOW_WRITE)
# ===========================================================================


def _assert_writable(
    client: GTMClient, account_id: str, container_id: str, workspace_id: str, allow_default: bool
) -> dict:
    if not workspace_id:
        raise ValueError("workspace_id is required for writes. Create a dedicated workspace with create_workspace.")
    workspace = client.get_workspace(account_id, container_id, workspace_id)
    if workspace.get("name", "").lower().startswith("default") and not allow_default:
        raise ValueError(
            "Refusing to write into the Default Workspace: other people's unpublished work lives there. "
            "Create a dedicated workspace, or pass allow_default_workspace=true if you really mean it."
        )
    return workspace


def _write_result(status: str, kind: str, entity: dict, workspace: dict) -> str:
    return _dump(
        {
            "status": status,
            "entity": _entity_summary(kind, entity),
            "workspace": {"workspaceId": workspace.get("workspaceId"), "name": workspace.get("name")},
            "next": REVIEW_NEXT_STEP,
        }
    )


def create_workspace(account_id: str, container_id: str, name: str, description: str = "") -> str:
    """Create a workspace to hold a reviewed change set. Writes should go there, never into the Default Workspace."""
    workspace = _client().create_workspace(account_id, container_id, name, description)
    return _dump(
        {
            "status": "created",
            "workspace": {
                "workspaceId": workspace.get("workspaceId"),
                "name": workspace.get("name"),
                "description": workspace.get("description", ""),
            },
            "next": "Pass this workspaceId to create_* / update_* tools.",
        }
    )


def _create(kind: str, account_id: str, container_id: str, workspace_id: str, raw: str, allow_default: bool) -> str:
    client = _client()
    workspace = _assert_writable(client, account_id, container_id, workspace_id, allow_default)
    body = _parse_body(raw, f"{kind}_json")
    for required in ("name", "type"):
        if not body.get(required):
            raise ValueError(f"{kind}_json needs a '{required}' field.")
    created = client.create_entity(account_id, container_id, workspace_id, kind, body)
    return _write_result("created", kind, created, workspace)


def _update(
    kind: str, account_id: str, container_id: str, workspace_id: str, entity_id: str, raw: str, allow_default: bool
) -> str:
    client = _client()
    workspace = _assert_writable(client, account_id, container_id, workspace_id, allow_default)
    patch = _parse_body(raw, f"{kind}_json")
    if not patch:
        raise ValueError(f"{kind}_json is empty: nothing to update.")
    updated = client.update_entity(account_id, container_id, workspace_id, kind, entity_id, patch)
    return _write_result("updated", kind, updated, workspace)


def create_tag(
    account_id: str, container_id: str, workspace_id: str, tag_json: str, allow_default_workspace: bool = False
) -> str:
    """Create a tag from a JSON Tag resource (name, type, parameter[], firingTriggerId[], consentSettings...).

    Copy the shape from get_entity on a similar tag. Triggers are referenced by
    triggerId, variables as {{Variable Name}} inside parameter values.
    """
    return _create("tag", account_id, container_id, workspace_id, tag_json, allow_default_workspace)


def update_tag(
    account_id: str,
    container_id: str,
    workspace_id: str,
    tag_id: str,
    tag_json: str,
    allow_default_workspace: bool = False,
) -> str:
    """Update a tag: tag_json holds only the fields to change; the rest is read first and kept.

    A list field such as parameter or firingTriggerId is replaced whole, so pass the complete list.
    """
    return _update("tag", account_id, container_id, workspace_id, tag_id, tag_json, allow_default_workspace)


def create_trigger(
    account_id: str, container_id: str, workspace_id: str, trigger_json: str, allow_default_workspace: bool = False
) -> str:
    """Create a trigger from a JSON Trigger resource (name, type, filter[] / customEventFilter[] ...)."""
    return _create("trigger", account_id, container_id, workspace_id, trigger_json, allow_default_workspace)


def update_trigger(
    account_id: str,
    container_id: str,
    workspace_id: str,
    trigger_id: str,
    trigger_json: str,
    allow_default_workspace: bool = False,
) -> str:
    """Update a trigger: trigger_json holds only the fields to change."""
    return _update(
        "trigger", account_id, container_id, workspace_id, trigger_id, trigger_json, allow_default_workspace
    )


def create_variable(
    account_id: str, container_id: str, workspace_id: str, variable_json: str, allow_default_workspace: bool = False
) -> str:
    """Create a variable from a JSON Variable resource (name, type, parameter[] ...)."""
    return _create("variable", account_id, container_id, workspace_id, variable_json, allow_default_workspace)


def update_variable(
    account_id: str,
    container_id: str,
    workspace_id: str,
    variable_id: str,
    variable_json: str,
    allow_default_workspace: bool = False,
) -> str:
    """Update a variable: variable_json holds only the fields to change."""
    return _update(
        "variable", account_id, container_id, workspace_id, variable_id, variable_json, allow_default_workspace
    )


def delete_entity(
    account_id: str,
    container_id: str,
    workspace_id: str,
    kind: str,
    entity_id: str,
    allow_default_workspace: bool = False,
) -> str:
    """Delete a tag, trigger, variable or folder from a workspace. Reversible until the workspace is published."""
    client = _client()
    workspace = _assert_writable(client, account_id, container_id, workspace_id, allow_default_workspace)
    entity = client.get_entity(account_id, container_id, workspace_id, kind, entity_id)
    client.delete_entity(account_id, container_id, workspace_id, kind, entity_id)
    return _write_result("deleted", kind.rstrip("s"), entity, workspace)


def delete_workspace(
    account_id: str, container_id: str, workspace_id: str, allow_default_workspace: bool = False
) -> str:
    """Delete a workspace with its unpublished changes: clean-up after a change set was published or dropped."""
    client = _client()
    workspace = _assert_writable(client, account_id, container_id, workspace_id, allow_default_workspace)
    client.delete_workspace(account_id, container_id, workspace_id)
    return _dump(
        {
            "status": "deleted",
            "workspace": {"workspaceId": workspace.get("workspaceId"), "name": workspace.get("name")},
        }
    )


WRITE_TOOLS = (
    create_workspace,
    delete_workspace,
    create_tag,
    update_tag,
    create_trigger,
    update_trigger,
    create_variable,
    update_variable,
    delete_entity,
)

if config.write_enabled():
    for _tool in WRITE_TOOLS:
        mcp.tool()(_tool)

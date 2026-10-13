"""Build a container export in the format GTM's own "Export container" produces.

The file imports cleanly from Admin > Import container, which is the safest
way to move a reviewed change set into a container: GTM shows the diff before
anything is merged, and nothing is published.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EXPORT_FORMAT_VERSION = 2

_CONTAINER_FIELDS = (
    "path",
    "accountId",
    "containerId",
    "name",
    "publicId",
    "usageContext",
    "fingerprint",
    "tagManagerUrl",
    "features",
    "tagIds",
    "domainName",
    "notes",
)


def build_export(container: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Wrap a snapshot (workspace or version) as an importable container JSON."""
    account_id = snapshot.get("accountId") or container.get("accountId", "")
    container_id = snapshot.get("containerId") or container.get("containerId", "")
    version_id = str(snapshot.get("versionId") or "0")
    container_meta = {k: container[k] for k in _CONTAINER_FIELDS if k in container}
    container_meta.setdefault("accountId", account_id)
    container_meta.setdefault("containerId", container_id)
    container_meta.setdefault("path", f"accounts/{account_id}/containers/{container_id}")

    return {
        "exportFormatVersion": EXPORT_FORMAT_VERSION,
        "exportTime": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "containerVersion": {
            "path": f"accounts/{account_id}/containers/{container_id}/versions/{version_id}",
            "accountId": account_id,
            "containerId": container_id,
            "containerVersionId": version_id,
            "container": container_meta,
            "tag": list(snapshot.get("tags") or []),
            "trigger": list(snapshot.get("triggers") or []),
            "variable": list(snapshot.get("variables") or []),
            "folder": list(snapshot.get("folders") or []),
            "builtInVariable": list(snapshot.get("builtInVariables") or []),
            "customTemplate": list(snapshot.get("customTemplates") or []),
        },
    }


def export_counts(export: dict[str, Any]) -> dict[str, int]:
    version = export["containerVersion"]
    return {
        key: len(version.get(key) or [])
        for key in ("tag", "trigger", "variable", "folder", "builtInVariable", "customTemplate")
    }

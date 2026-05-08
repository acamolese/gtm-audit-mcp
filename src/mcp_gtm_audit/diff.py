"""Diff fra due snapshot GTM (workspace o version)."""

from __future__ import annotations

from typing import Any


_KIND_KEYS = {
    "tags": "tagId",
    "triggers": "triggerId",
    "variables": "variableId",
}


def _index(items: list[dict], key: str) -> dict[str, dict]:
    return {i.get(key): i for i in items if i.get(key)}


def _stable_payload(item: dict) -> dict:
    """Rimuove campi volatili (fingerprint, parentFolderId, accountId, containerId)."""
    skip = {"fingerprint", "parentFolderId", "accountId", "containerId", "workspaceId", "path"}
    return {k: v for k, v in item.items() if k not in skip}


def diff_snapshots(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """Confronta due snapshot e restituisce le differenze per kind."""
    out: dict[str, Any] = {
        "base": {
            "source": base.get("source"),
            "versionId": base.get("versionId"),
            "workspaceId": base.get("workspaceId"),
        },
        "head": {
            "source": head.get("source"),
            "versionId": head.get("versionId"),
            "workspaceId": head.get("workspaceId"),
        },
        "changes": {},
    }
    summary = {"added": 0, "removed": 0, "modified": 0}

    for kind, key in _KIND_KEYS.items():
        base_idx = _index(base.get(kind, []) or [], key)
        head_idx = _index(head.get(kind, []) or [], key)

        added_ids = head_idx.keys() - base_idx.keys()
        removed_ids = base_idx.keys() - head_idx.keys()
        common_ids = base_idx.keys() & head_idx.keys()

        modified = []
        for cid in common_ids:
            b = _stable_payload(base_idx[cid])
            h = _stable_payload(head_idx[cid])
            if b != h:
                modified.append({
                    "id": cid,
                    "name": head_idx[cid].get("name"),
                    "before": b,
                    "after": h,
                })

        kind_changes = {
            "added": [
                {"id": i, "name": head_idx[i].get("name"), "type": head_idx[i].get("type")}
                for i in added_ids
            ],
            "removed": [
                {"id": i, "name": base_idx[i].get("name"), "type": base_idx[i].get("type")}
                for i in removed_ids
            ],
            "modified": modified,
        }
        out["changes"][kind] = kind_changes
        summary["added"] += len(added_ids)
        summary["removed"] += len(removed_ids)
        summary["modified"] += len(modified)

    out["summary"] = summary
    return out

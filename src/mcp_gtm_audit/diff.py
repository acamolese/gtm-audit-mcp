"""Diff between two container snapshots (workspace or version)."""

from __future__ import annotations

from typing import Any

_KIND_KEYS = {
    "tags": "tagId",
    "triggers": "triggerId",
    "variables": "variableId",
}

# Fields that differ between a version and a workspace copy of the same entity
# without meaning anything changed. `tagManagerUrl` was the one that made every
# entity look modified in 0.1.
VOLATILE_FIELDS = frozenset({"fingerprint", "accountId", "containerId", "workspaceId", "path", "tagManagerUrl"})


def _index(items: list[dict], key: str) -> dict[str, dict]:
    return {i.get(key): i for i in items if i.get(key)}


def _stable_payload(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in VOLATILE_FIELDS}


def _changed_fields(before: dict, after: dict) -> list[str]:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def diff_snapshots(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """Return added / removed / modified entities per kind, with the changed fields."""
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

        added_ids = sorted(head_idx.keys() - base_idx.keys(), key=_as_int)
        removed_ids = sorted(base_idx.keys() - head_idx.keys(), key=_as_int)
        common_ids = sorted(base_idx.keys() & head_idx.keys(), key=_as_int)

        modified = []
        for cid in common_ids:
            before = _stable_payload(base_idx[cid])
            after = _stable_payload(head_idx[cid])
            if before != after:
                fields = _changed_fields(before, after)
                modified.append(
                    {
                        "id": cid,
                        "name": head_idx[cid].get("name"),
                        "type": head_idx[cid].get("type"),
                        "fields": fields,
                        "before": {f: before.get(f) for f in fields},
                        "after": {f: after.get(f) for f in fields},
                    }
                )

        out["changes"][kind] = {
            "added": [{"id": i, "name": head_idx[i].get("name"), "type": head_idx[i].get("type")} for i in added_ids],
            "removed": [
                {"id": i, "name": base_idx[i].get("name"), "type": base_idx[i].get("type")} for i in removed_ids
            ],
            "modified": modified,
        }
        summary["added"] += len(added_ids)
        summary["removed"] += len(removed_ids)
        summary["modified"] += len(modified)

    out["summary"] = summary
    return out


def _as_int(value: str) -> tuple[int, str]:
    try:
        return (int(value), "")
    except (TypeError, ValueError):
        return (1 << 62, str(value))

"""Thin REST client for the Google Tag Manager API v2.

Every call goes through `_request`, which owns the three things the API makes
you care about: the per-user quota (15 requests per minute, enforced here with
a sliding window so a burst of list calls does not end in 429), retries on
429 and 5xx, and error messages that say which path failed.

Writes exist only on the client; the server decides whether to expose them.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Iterable
from typing import Any

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_URL = "https://tagmanager.googleapis.com/tagmanager/v2"

# Google's documented quota for the Tag Manager API is 0.25 queries per second
# per user, i.e. 15 per minute. The window is kept slightly under that.
RATE_LIMIT_CALLS = 15
RATE_LIMIT_WINDOW = 62.0
MAX_ATTEMPTS = 5
# Writes are metered separately and much more tightly than reads: a burst of
# writes answers 429 "rateLimitExceeded" for minutes. Space them out and back
# off longer, and say what happened when the quota does not come back.
WRITE_MIN_INTERVAL = 4.2
WRITE_BACKOFF = (20.0, 40.0, 60.0, 90.0)
WRITE_METHODS = {"POST", "PUT", "DELETE"}

ENTITY_KINDS = {
    "tag": ("tags", "tagId"),
    "trigger": ("triggers", "triggerId"),
    "variable": ("variables", "variableId"),
    "folder": ("folders", "folderId"),
}


class GTMAPIError(RuntimeError):
    """An HTTP error from the Tag Manager API, with the status and path kept."""

    def __init__(self, status: int, path: str, body: str):
        self.status = status
        self.path = path
        self.body = body
        hint = ""
        if status == 429:
            hint = (
                " (Tag Manager API quota: 15 requests per minute per user for reads; writes have their own, "
                "smaller allowance and a burst of them is refused for minutes. Wait, then retry one change at a time)"
            )
        elif status == 403:
            hint = " (no access to this entity with the authorized account, or a missing OAuth scope)"
        elif status == 404:
            hint = " (check account, container and workspace ids: the container id is numeric, not GTM-XXXX)"
        elif status == 409:
            hint = " (the entity changed since it was read; fetch it again and retry)"
        super().__init__(f"GTM API {status} on {path}{hint}: {body[:400]}")


def _workspace_path(account_id: str, container_id: str, workspace_id: str) -> str:
    return f"/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}"


class GTMClient:
    def __init__(self, credentials: Credentials, timeout: int = 30, sleep=time.sleep, clock=time.monotonic):
        self.credentials = credentials
        self.timeout = timeout
        self.session = requests.Session()
        self._sleep = sleep
        self._clock = clock
        self._calls: deque[float] = deque()
        self._last_write: float | None = None

    # ---- transport ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return {
            "Authorization": f"Bearer {self.credentials.token}",
            "Accept": "application/json",
        }

    def _throttle(self) -> None:
        now = self._clock()
        while self._calls and now - self._calls[0] > RATE_LIMIT_WINDOW:
            self._calls.popleft()
        if len(self._calls) >= RATE_LIMIT_CALLS:
            wait = RATE_LIMIT_WINDOW - (now - self._calls[0])
            if wait > 0:
                self._sleep(wait)
            self._calls.popleft()
        self._calls.append(self._clock())

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
        is_write = method.upper() in WRITE_METHODS
        last: requests.Response | None = None
        for attempt in range(MAX_ATTEMPTS):
            self._throttle()
            if is_write:
                self._space_writes()
            resp = self.session.request(
                method, url, headers=self._headers(), params=params, json=json, timeout=self.timeout
            )
            last = resp
            if resp.status_code == 429 or resp.status_code >= 500:
                if is_write and attempt >= len(WRITE_BACKOFF):
                    break
                self._sleep(WRITE_BACKOFF[attempt] if is_write else 15.0 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                raise GTMAPIError(resp.status_code, path, resp.text)
            return resp.json() if resp.text else {}
        assert last is not None  # noqa: S101 - loop runs at least once
        raise GTMAPIError(last.status_code, path, "still refused after retries: " + last.text)

    def _space_writes(self) -> None:
        if self._last_write is not None:
            wait = WRITE_MIN_INTERVAL - (self._clock() - self._last_write)
            if wait > 0:
                self._sleep(wait)
        self._last_write = self._clock()

    def _get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def _paginate(self, path: str, key: str, params: dict | None = None) -> Iterable[dict]:
        params = dict(params or {})
        while True:
            data = self._get(path, params=params)
            yield from data.get(key, []) or []
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token

    # ---- inventory ---------------------------------------------------------

    def list_accounts(self) -> list[dict]:
        return list(self._paginate("/accounts", "account"))

    def list_containers(self, account_id: str) -> list[dict]:
        return list(self._paginate(f"/accounts/{account_id}/containers", "container"))

    def get_container(self, account_id: str, container_id: str) -> dict:
        return self._get(f"/accounts/{account_id}/containers/{container_id}")

    def list_workspaces(self, account_id: str, container_id: str) -> list[dict]:
        return list(self._paginate(f"/accounts/{account_id}/containers/{container_id}/workspaces", "workspace"))

    def get_workspace(self, account_id: str, container_id: str, workspace_id: str) -> dict:
        return self._get(_workspace_path(account_id, container_id, workspace_id))

    def list_tags(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(self._paginate(_workspace_path(account_id, container_id, workspace_id) + "/tags", "tag"))

    def list_triggers(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(self._paginate(_workspace_path(account_id, container_id, workspace_id) + "/triggers", "trigger"))

    def list_variables(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(
            self._paginate(_workspace_path(account_id, container_id, workspace_id) + "/variables", "variable")
        )

    def list_built_in_variables(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(
            self._paginate(
                _workspace_path(account_id, container_id, workspace_id) + "/built_in_variables",
                "builtInVariable",
            )
        )

    def list_folders(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(self._paginate(_workspace_path(account_id, container_id, workspace_id) + "/folders", "folder"))

    def list_templates(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(
            self._paginate(_workspace_path(account_id, container_id, workspace_id) + "/templates", "template")
        )

    def list_versions(self, account_id: str, container_id: str) -> list[dict]:
        return list(
            self._paginate(
                f"/accounts/{account_id}/containers/{container_id}/version_headers",
                "containerVersionHeader",
            )
        )

    def get_version(self, account_id: str, container_id: str, version_id: str) -> dict:
        return self._get(f"/accounts/{account_id}/containers/{container_id}/versions/{version_id}")

    def get_live_version(self, account_id: str, container_id: str) -> dict:
        return self._get(f"/accounts/{account_id}/containers/{container_id}/versions:live")

    def get_entity(self, account_id: str, container_id: str, workspace_id: str, kind: str, entity_id: str) -> dict:
        collection, _ = _kind(kind)
        return self._get(_workspace_path(account_id, container_id, workspace_id) + f"/{collection}/{entity_id}")

    # ---- snapshots ---------------------------------------------------------

    def workspace_snapshot(self, account_id: str, container_id: str, workspace_id: str) -> dict[str, Any]:
        return {
            "source": "workspace",
            "accountId": account_id,
            "containerId": container_id,
            "workspaceId": workspace_id,
            "tags": self.list_tags(account_id, container_id, workspace_id),
            "triggers": self.list_triggers(account_id, container_id, workspace_id),
            "variables": self.list_variables(account_id, container_id, workspace_id),
            "builtInVariables": self.list_built_in_variables(account_id, container_id, workspace_id),
            "folders": self.list_folders(account_id, container_id, workspace_id),
        }

    def version_snapshot(self, account_id: str, container_id: str, version_id: str | None) -> dict[str, Any]:
        version = (
            self.get_live_version(account_id, container_id)
            if version_id in (None, "", "live")
            else self.get_version(account_id, container_id, version_id)
        )
        return {
            "source": "version",
            "accountId": account_id,
            "containerId": container_id,
            "versionId": version.get("containerVersionId"),
            "name": version.get("name"),
            "container": version.get("container") or {},
            "tags": version.get("tag", []) or [],
            "triggers": version.get("trigger", []) or [],
            "variables": version.get("variable", []) or [],
            "builtInVariables": version.get("builtInVariable", []) or [],
            "folders": version.get("folder", []) or [],
            "customTemplates": version.get("customTemplate", []) or [],
        }

    # ---- writes (exposed by the server only in write mode) -----------------

    def create_workspace(self, account_id: str, container_id: str, name: str, description: str = "") -> dict:
        body = {"name": name}
        if description:
            body["description"] = description
        return self._request("POST", f"/accounts/{account_id}/containers/{container_id}/workspaces", json=body)

    def delete_workspace(self, account_id: str, container_id: str, workspace_id: str) -> None:
        self._request("DELETE", _workspace_path(account_id, container_id, workspace_id))

    def create_entity(self, account_id: str, container_id: str, workspace_id: str, kind: str, body: dict) -> dict:
        collection, _ = _kind(kind)
        return self._request(
            "POST", _workspace_path(account_id, container_id, workspace_id) + f"/{collection}", json=body
        )

    def update_entity(
        self, account_id: str, container_id: str, workspace_id: str, kind: str, entity_id: str, patch: dict
    ) -> dict:
        """Read-merge-write: the API wants the full resource plus its fingerprint."""
        collection, _ = _kind(kind)
        path = _workspace_path(account_id, container_id, workspace_id) + f"/{collection}/{entity_id}"
        current = self._get(path)
        fingerprint = current.get("fingerprint")
        merged = {k: v for k, v in current.items() if k not in ("fingerprint", "path", "tagManagerUrl")}
        merged.update({k: v for k, v in patch.items() if k not in ("fingerprint", "path", "tagManagerUrl")})
        params = {"fingerprint": fingerprint} if fingerprint else None
        return self._request("PUT", path, params=params, json=merged)

    def delete_entity(self, account_id: str, container_id: str, workspace_id: str, kind: str, entity_id: str) -> None:
        collection, _ = _kind(kind)
        self._request(
            "DELETE", _workspace_path(account_id, container_id, workspace_id) + f"/{collection}/{entity_id}"
        )


def _kind(kind: str) -> tuple[str, str]:
    key = (kind or "").strip().lower().rstrip("s")
    if key not in ENTITY_KINDS:
        raise ValueError(f"Unknown entity kind {kind!r}. Use tag, trigger, variable or folder.")
    return ENTITY_KINDS[key]

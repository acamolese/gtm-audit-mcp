"""Wrapper REST per Google Tag Manager API v2."""

from __future__ import annotations

from typing import Any, Iterable

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_URL = "https://tagmanager.googleapis.com/tagmanager/v2"


class GTMClient:
    def __init__(self, credentials: Credentials, timeout: int = 30):
        self.credentials = credentials
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return {
            "Authorization": f"Bearer {self.credentials.token}",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
        resp = self.session.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        if resp.status_code >= 400:
            raise RuntimeError(f"GTM API {resp.status_code} su {path}: {resp.text}")
        return resp.json()

    def _paginate(self, path: str, key: str, params: dict | None = None) -> Iterable[dict]:
        params = dict(params or {})
        while True:
            data = self._get(path, params=params)
            for item in data.get(key, []) or []:
                yield item
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token

    # ---- Inventario --------------------------------------------------------

    def list_accounts(self) -> list[dict]:
        return list(self._paginate("/accounts", "account"))

    def list_containers(self, account_id: str) -> list[dict]:
        return list(self._paginate(f"/accounts/{account_id}/containers", "container"))

    def list_workspaces(self, account_id: str, container_id: str) -> list[dict]:
        return list(self._paginate(
            f"/accounts/{account_id}/containers/{container_id}/workspaces",
            "workspace",
        ))

    def list_tags(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(self._paginate(
            f"/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/tags",
            "tag",
        ))

    def list_triggers(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(self._paginate(
            f"/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/triggers",
            "trigger",
        ))

    def list_variables(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(self._paginate(
            f"/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/variables",
            "variable",
        ))

    def list_built_in_variables(
        self, account_id: str, container_id: str, workspace_id: str
    ) -> list[dict]:
        return list(self._paginate(
            f"/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/built_in_variables",
            "builtInVariable",
        ))

    def list_folders(self, account_id: str, container_id: str, workspace_id: str) -> list[dict]:
        return list(self._paginate(
            f"/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/folders",
            "folder",
        ))

    def list_versions(self, account_id: str, container_id: str) -> list[dict]:
        return list(self._paginate(
            f"/accounts/{account_id}/containers/{container_id}/version_headers",
            "containerVersionHeader",
        ))

    def get_version(self, account_id: str, container_id: str, version_id: str) -> dict:
        return self._get(
            f"/accounts/{account_id}/containers/{container_id}/versions/{version_id}"
        )

    def get_live_version(self, account_id: str, container_id: str) -> dict:
        return self._get(
            f"/accounts/{account_id}/containers/{container_id}/versions:live"
        )

    # ---- Snapshot completo (workspace o version) ---------------------------

    def workspace_snapshot(
        self, account_id: str, container_id: str, workspace_id: str
    ) -> dict[str, Any]:
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
            if version_id in (None, "live")
            else self.get_version(account_id, container_id, version_id)
        )
        return {
            "source": "version",
            "accountId": account_id,
            "containerId": container_id,
            "versionId": version.get("containerVersionId"),
            "name": version.get("name"),
            "tags": version.get("tag", []) or [],
            "triggers": version.get("trigger", []) or [],
            "variables": version.get("variable", []) or [],
            "builtInVariables": version.get("builtInVariable", []) or [],
            "folders": version.get("folder", []) or [],
        }

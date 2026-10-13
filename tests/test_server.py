"""Tool-level behaviour with a fake client: write gate, workspace guard, outputs."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from mcp_gtm_audit import config


class FakeClient:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.created = []
        self.deleted = []

    def list_workspaces(self, a, c):
        return [{"workspaceId": "3", "name": "Default Workspace"}, {"workspaceId": "4", "name": "Fix set"}]

    def get_workspace(self, a, c, w):
        return next(x for x in self.list_workspaces(a, c) if x["workspaceId"] == w)

    def list_containers(self, a):
        return [{"containerId": "2", "name": "Site", "publicId": "GTM-ABC", "accountId": "1"}]

    def get_container(self, a, c):
        return {"accountId": "1", "containerId": "2", "name": "Site", "publicId": "GTM-ABC", "usageContext": ["WEB"]}

    def workspace_snapshot(self, a, c, w):
        return {**self.snapshot, "workspaceId": w}

    def version_snapshot(self, a, c, v):
        return {**self.snapshot, "source": "version", "versionId": "5", "workspaceId": None}

    def list_templates(self, a, c, w):
        return []

    def create_entity(self, a, c, w, kind, body):
        self.created.append((kind, body))
        return {**body, f"{kind}Id": "100", "fingerprint": "fp"}

    def get_entity(self, a, c, w, kind, entity_id):
        return {f"{kind.rstrip('s')}Id": entity_id, "name": "Thing", "type": "html"}

    def delete_entity(self, a, c, w, kind, entity_id):
        self.deleted.append((kind, entity_id))

    def delete_workspace(self, a, c, w):
        self.deleted.append(("workspace", w))


@pytest.fixture
def server(monkeypatch, snapshot, tmp_path):
    monkeypatch.setenv("GTM_REPORTS_DIR", str(tmp_path))
    from mcp_gtm_audit import server as server_module

    fake = FakeClient(snapshot)
    monkeypatch.setattr(server_module, "_client", lambda: fake)
    return server_module, fake


def test_write_tools_are_not_registered_without_the_flag(monkeypatch):
    monkeypatch.delenv("GTM_ALLOW_WRITE", raising=False)
    from mcp_gtm_audit import server as server_module

    importlib.reload(server_module)
    names = {t.name for t in server_module.mcp._tool_manager.list_tools()}
    assert "gtm_audit" in names and "gtm_export" in names
    assert not names & {"create_tag", "update_tag", "delete_entity", "create_workspace"}


def test_write_tools_are_registered_with_the_flag(monkeypatch):
    monkeypatch.setenv("GTM_ALLOW_WRITE", "1")
    from mcp_gtm_audit import server as server_module

    importlib.reload(server_module)
    names = {t.name for t in server_module.mcp._tool_manager.list_tools()}
    assert {
        "create_workspace",
        "create_tag",
        "update_tag",
        "create_trigger",
        "update_trigger",
        "create_variable",
        "update_variable",
        "delete_entity",
    } <= names
    assert not names & {"publish", "create_version"}
    monkeypatch.delenv("GTM_ALLOW_WRITE")
    importlib.reload(server_module)


def test_audit_writes_both_reports_and_returns_paths(server):
    server_module, _ = server
    out = json.loads(server_module.gtm_audit("1", "2", workspace_id="4", language="it"))
    assert out["container"] == "Site (GTM-ABC)"
    assert out["stats"]["tags"] == 5
    html = Path(out["html_report"]).read_text(encoding="utf-8")
    assert 'lang="it"' in html and "Criticità rilevate" in html
    assert Path(out["json_report"]).read_text(encoding="utf-8").startswith("{")


def test_export_writes_an_importable_file(server):
    server_module, _ = server
    out = json.loads(server_module.gtm_export("1", "2", workspace_id="4"))
    data = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert data["exportFormatVersion"] == 2
    assert out["counts"]["tag"] == 5


def test_writes_refuse_the_default_workspace(server):
    server_module, fake = server
    with pytest.raises(ValueError, match="Default Workspace"):
        server_module.create_tag("1", "2", "3", json.dumps({"name": "t", "type": "html"}))
    assert fake.created == []


def test_create_in_a_dedicated_workspace_returns_the_review_step(server):
    server_module, fake = server
    out = json.loads(server_module.create_tag("1", "2", "4", json.dumps({"name": "t", "type": "html"})))
    assert out["status"] == "created" and out["entity"]["id"] == "100"
    assert "never publishes" in out["next"]
    assert fake.created[0][0] == "tag"


def test_create_requires_name_and_type(server):
    server_module, _ = server
    with pytest.raises(ValueError, match="'type'"):
        server_module.create_variable("1", "2", "4", json.dumps({"name": "x"}))
    with pytest.raises(ValueError, match="JSON object"):
        server_module.create_variable("1", "2", "4", "not json")


def test_delete_reports_what_was_removed(server):
    server_module, fake = server
    out = json.loads(server_module.delete_entity("1", "2", "4", "trigger", "5"))
    assert out["status"] == "deleted" and out["entity"]["name"] == "Thing"
    assert fake.deleted == [("trigger", "5")]


def test_required_scopes_follow_the_mode(monkeypatch):
    monkeypatch.delenv("GTM_ALLOW_WRITE", raising=False)
    assert config.required_scopes() == [config.READ_SCOPE]
    monkeypatch.setenv("GTM_ALLOW_WRITE", "true")
    assert config.required_scopes() == [config.READ_SCOPE, config.EDIT_SCOPE]


def test_delete_workspace_refuses_default_and_deletes_dedicated(server):
    server_module, fake = server
    with pytest.raises(ValueError, match="Default Workspace"):
        server_module.delete_workspace("1", "2", "3")
    out = json.loads(server_module.delete_workspace("1", "2", "4"))
    assert out["status"] == "deleted" and out["workspace"]["name"] == "Fix set"
    assert fake.deleted == [("workspace", "4")]

"""Synthetic snapshots and a fake HTTP session shared by the suite."""

from __future__ import annotations

import pytest


def tag(tag_id, name, type_="gaawe", firing=("1",), params=None, consent="NEEDED", **extra):
    body = {
        "tagId": tag_id,
        "name": name,
        "type": type_,
        "firingTriggerId": list(firing),
        "parameter": params or [],
        "consentSettings": {"consentStatus": consent},
        "fingerprint": "f-" + tag_id,
        "path": f"accounts/1/containers/2/workspaces/3/tags/{tag_id}",
        "tagManagerUrl": f"https://tagmanager.google.com/#/container/accounts/1/containers/2/workspaces/3/tags/{tag_id}",
    }
    body.update(extra)
    return body


def trigger(trigger_id, name, type_="pageview"):
    return {"triggerId": trigger_id, "name": name, "type": type_, "fingerprint": "f-" + trigger_id}


def variable(variable_id, name, type_="v"):
    return {"variableId": variable_id, "name": name, "type": type_, "fingerprint": "f-" + variable_id}


@pytest.fixture
def snapshot():
    return {
        "source": "workspace",
        "accountId": "1",
        "containerId": "2",
        "workspaceId": "3",
        "tags": [
            tag(
                "10",
                "GA4 - Configuration",
                "googtag",
                firing=("2147479553",),
                params=[{"type": "template", "key": "tagId", "value": "{{GA4 - Measurement ID}}"}],
            ),
            tag(
                "11",
                "GA4 - purchase",
                "gaawe",
                params=[
                    {"type": "template", "key": "eventName", "value": "purchase"},
                    {"type": "template", "key": "measurementIdOverride", "value": "{{GA4 - Measurement ID}}"},
                    {
                        "type": "list",
                        "key": "eventSettingsTable",
                        "list": [
                            {"type": "map", "map": [{"type": "template", "key": "parameter", "value": "value"}]},
                            {"type": "map", "map": [{"type": "template", "key": "parameter", "value": "currency"}]},
                        ],
                    },
                ],
            ),
            tag(
                "12",
                "Orphan HTML",
                "html",
                firing=(),
                params=[{"key": "html", "value": "<script>document.write(1)</script>"}],
                consent="NOT_SET",
            ),
            tag("13", "Ads - conversion", "awct", params=[{"key": "conversionId", "value": "AW-1"}], paused=True),
            tag(
                "14",
                "Dead ref",
                "gaawe",
                params=[
                    {"key": "eventName", "value": "x"},
                    {"key": "measurementIdOverride", "value": "{{Missing Var}}"},
                ],
            ),
        ],
        "triggers": [trigger("1", "All custom"), trigger("5", "Unused trigger")],
        "variables": [variable("20", "GA4 - Measurement ID", "c"), variable("21", "Unused variable", "c")],
        "builtInVariables": [{"name": "Page URL", "type": "PAGE_URL"}],
        "folders": [],
    }

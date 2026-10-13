from mcp_gtm_audit.export import build_export, export_counts


def test_export_has_the_gtm_import_shape(snapshot):
    container = {
        "accountId": "1",
        "containerId": "2",
        "name": "Site",
        "publicId": "GTM-ABC",
        "usageContext": ["WEB"],
        "path": "accounts/1/containers/2",
        "fingerprint": "x",
        "tagIds": ["GTM-ABC"],
    }
    export = build_export(container, snapshot)
    assert export["exportFormatVersion"] == 2
    version = export["containerVersion"]
    assert version["containerVersionId"] == "0"
    assert version["container"]["publicId"] == "GTM-ABC"
    assert version["path"] == "accounts/1/containers/2/versions/0"
    assert export_counts(export) == {
        "tag": 5,
        "trigger": 2,
        "variable": 2,
        "folder": 0,
        "builtInVariable": 1,
        "customTemplate": 0,
    }


def test_export_from_a_version_keeps_its_id():
    snap = {
        "source": "version",
        "accountId": "1",
        "containerId": "2",
        "versionId": "53",
        "tags": [],
        "triggers": [],
        "variables": [],
        "customTemplates": [{"name": "T"}],
    }
    export = build_export({"accountId": "1", "containerId": "2"}, snap)
    assert export["containerVersion"]["containerVersionId"] == "53"
    assert export_counts(export)["customTemplate"] == 1

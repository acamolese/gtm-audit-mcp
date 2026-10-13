import copy

from mcp_gtm_audit.diff import diff_snapshots


def test_volatile_fields_do_not_count_as_changes(snapshot):
    head = copy.deepcopy(snapshot)
    for t in head["tags"]:
        t["tagManagerUrl"] = "https://tagmanager.google.com/other"
        t["fingerprint"] = "changed"
        t["path"] = "accounts/1/containers/2/versions/9/tags/" + t["tagId"]
    out = diff_snapshots(snapshot, head)
    assert out["summary"] == {"added": 0, "removed": 0, "modified": 0}


def test_real_changes_are_listed_with_their_fields(snapshot):
    head = copy.deepcopy(snapshot)
    head["tags"][0]["notes"] = "now with notes"
    head["tags"][0]["parameter"][0]["value"] = "{{Other}}"
    head["variables"].append({"variableId": "99", "name": "New", "type": "c"})
    del head["triggers"][1]
    out = diff_snapshots(snapshot, head)
    assert out["summary"] == {"added": 1, "removed": 1, "modified": 1}
    mod = out["changes"]["tags"]["modified"][0]
    assert mod["id"] == "10" and mod["fields"] == ["notes", "parameter"]
    assert mod["before"]["notes"] is None and mod["after"]["notes"] == "now with notes"
    assert out["changes"]["variables"]["added"] == [{"id": "99", "name": "New", "type": "c"}]
    assert out["changes"]["triggers"]["removed"][0]["name"] == "Unused trigger"

from mcp_gtm_audit.audit import run_audit


def codes(result):
    return {(i.code, i.entity_name) for i in result.issues}


def test_rules_fire_on_the_synthetic_container(snapshot):
    result = run_audit(snapshot)
    found = codes(result)
    assert ("tag_no_trigger", "Orphan HTML") in found
    assert ("tag_custom_html", "Orphan HTML") in found
    assert ("tag_no_consent", "Orphan HTML") in found
    assert ("tag_paused", "Ads - conversion") in found
    assert ("tag_dead_variable", "Dead ref") in found
    assert ("trigger_orphan", "Unused trigger") in found
    assert ("variable_unused", "Unused variable") in found
    # the referenced trigger and variable are not reported
    assert ("trigger_orphan", "All custom") not in found
    assert ("variable_unused", "GA4 - Measurement ID") not in found


def test_stats_count_by_severity(snapshot):
    stats = run_audit(snapshot).stats
    assert stats["tags"] == 5
    assert stats["issues_total"] == stats["issues_high"] + stats["issues_medium"] + stats["issues_low"]
    assert stats["tags_by_type"]["gaawe"] == 2


def test_issue_wording_follows_the_language(snapshot):
    result = run_audit(snapshot)
    issue = next(i for i in result.issues if i.code == "tag_dead_variable")
    en = issue.to_dict("en")
    it = issue.to_dict("it")
    assert "Missing Var" in en["detail"] and "Missing Var" in it["detail"]
    assert en["title"] != it["title"]
    assert en["code"] == it["code"] == "tag_dead_variable"


def test_document_write_is_called_out():
    snap = {
        "tags": [
            {
                "tagId": "1",
                "name": "H",
                "type": "html",
                "firingTriggerId": ["1"],
                "parameter": [{"key": "html", "value": "document.write('x')"}],
                "consentSettings": {"consentStatus": "NEEDED"},
            }
        ],
        "triggers": [{"triggerId": "1", "name": "t"}],
        "variables": [],
    }
    issue = next(i for i in run_audit(snap).issues if i.code == "tag_custom_html")
    assert "document.write" in issue.to_dict("en")["detail"]


def test_duplicate_and_default_names():
    snap = {
        "tags": [
            {
                "tagId": "1",
                "name": "Same",
                "type": "html",
                "firingTriggerId": ["1"],
                "parameter": [{"key": "html", "value": "a"}],
            },
            {
                "tagId": "2",
                "name": "Same",
                "type": "html",
                "firingTriggerId": ["1"],
                "parameter": [{"key": "html", "value": "b"}],
            },
            {
                "tagId": "3",
                "name": "Untitled Tag",
                "type": "html",
                "firingTriggerId": ["1"],
                "parameter": [{"key": "html", "value": "c"}],
            },
        ],
        "triggers": [{"triggerId": "1", "name": "t"}],
        "variables": [],
    }
    found = codes(run_audit(snap))
    assert ("tag_duplicate_name", "Same") in found
    assert ("tag_default_name", "Untitled Tag") in found
    rendered = [i.to_dict("en") for i in run_audit(snap).issues if i.code == "tag_duplicate_name"][0]
    assert rendered["title"] == "Tag with a duplicated name"
    assert "2 tags share the name 'Same'" in rendered["detail"]

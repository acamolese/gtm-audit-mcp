from mcp_gtm_audit.tracking import validate_tracking


def test_event_map_and_missing_ecommerce_params(snapshot):
    out = validate_tracking(snapshot)
    assert out["ga4_configs"][0]["measurementId"] == "{{GA4 - Measurement ID}}"
    events = out["ga4_events_by_config"]["{{GA4 - Measurement ID}}"]
    purchase = next(e for e in events if e["event"] == "purchase")
    assert purchase["params"] == ["currency", "value"]
    missing = next(f for f in out["findings"] if f["code"] == "ga4_event_missing_params")
    assert "items" in missing["issue"] and "transaction_id" in missing["issue"]


def test_ads_without_linker_is_flagged(snapshot):
    out = validate_tracking(snapshot)
    assert out["ads_conversion_linker_present"] is False
    assert any(f["code"] == "ads_no_linker" for f in out["findings"])


def test_findings_are_translated(snapshot):
    en = validate_tracking(snapshot, "en")["findings"]
    it = validate_tracking(snapshot, "it")["findings"]
    assert [f["code"] for f in en] == [f["code"] for f in it]
    assert en[0]["issue"] != it[0]["issue"]


def test_server_side_tags_are_detected():
    snap = {
        "tags": [
            {
                "tagId": "1",
                "name": "GT",
                "type": "googtag",
                "parameter": [
                    {"key": "tagId", "value": "G-1"},
                    {"key": "configSettingsTable", "list": []},
                    {"key": "server_container_url", "value": "https://sgtm.example"},
                ],
            }
        ]
    }
    out = validate_tracking(snap)
    assert out["server_side_tags"] == ["GT"]
    assert out["ga4_configs"][0]["server_container_url"] == "https://sgtm.example"


def test_server_url_in_configuration_settings_rows_counts():
    row = {
        "type": "map",
        "map": [
            {"key": "parameter", "value": "server_container_url"},
            {"key": "parameterValue", "value": "https://sgtm.example"},
        ],
    }
    snap = {
        "tags": [
            {
                "tagId": "1",
                "name": "GT",
                "type": "googtag",
                "parameter": [{"key": "tagId", "value": "G-1"}, {"key": "configSettingsTable", "list": [row]}],
            }
        ],
        "variables": [
            {
                "variableId": "9",
                "name": "Config - Site",
                "type": "gtcs",
                "parameter": [{"key": "configSettingsTable", "list": [row]}],
            }
        ],
    }
    out = validate_tracking(snap)
    assert out["ga4_configs"][0]["server_container_url"] == "https://sgtm.example"
    assert out["server_side_tags"] == ["GT", "Config - Site (variable)"]
    assert not any(f["code"] == "no_server_side" for f in out["findings"])

"""Tracking validation: GA4 / Google Ads / Meta event map, consent and server-side hints."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from . import i18n

GA4_CONFIG_TYPES = {"gaawc", "googtag"}
GA4_EVENT_TYPES = {"gaawe"}
ADS_CONVERSION_TYPES = {"awct", "awcr"}
ADS_LINKER_TYPE = "gclidw"
META_TYPE_HINTS = ("Facebook Pixel", "Meta Pixel", "Facebook", "Meta")
SERVER_HINT_KEYS = ("server_container_url", "serverContainerUrl", "transport_url", "transportUrl")

# Parameters GA4 needs for its standard ecommerce and lead events.
GA4_REQUIRED_BY_EVENT = {
    "purchase": {"transaction_id", "value", "currency", "items"},
    "begin_checkout": {"value", "currency", "items"},
    "add_to_cart": {"value", "currency", "items"},
    "view_item": {"value", "currency", "items"},
    "generate_lead": {"value", "currency"},
}


def _flat_params(tag: dict) -> dict[str, Any]:
    """Flatten a tag's parameter list into key -> value / list / dict."""
    out: dict[str, Any] = {}
    for p in tag.get("parameter") or []:
        key = p.get("key")
        if not key:
            continue
        if "value" in p:
            out[key] = p["value"]
        elif "list" in p:
            out[key] = [_resolve_list_item(x) for x in p["list"]]
        elif "map" in p:
            out[key] = {m.get("key"): m.get("value") for m in p["map"]}
    return out


def _resolve_list_item(item: dict) -> Any:
    if "map" in item:
        return {m.get("key"): m.get("value") for m in item["map"]}
    if "value" in item:
        return item["value"]
    return item


def _event_parameter_names(params: dict[str, Any]) -> set[str]:
    """Names of the event parameters, from the Google tag's list-of-maps shape."""
    raw = params.get("eventSettingsTable") or params.get("eventParameters")
    names: set[str] = set()
    if isinstance(raw, dict):
        names.update(k for k in raw if k)
    elif isinstance(raw, list):
        for row in raw:
            if isinstance(row, dict):
                name = row.get("parameter") or row.get("name") or row.get("key")
                if name:
                    names.add(str(name))
    return names


def validate_tracking(snapshot: dict[str, Any], language: str = "en") -> dict[str, Any]:
    tags = snapshot.get("tags", []) or []

    ga4_events_by_config: dict[str, list[dict]] = defaultdict(list)
    ga4_configs: list[dict] = []
    ads_conversions: list[dict] = []
    ads_linker = False
    meta_pixels: list[dict] = []
    server_side_tags: list[str] = []
    findings: list[dict] = []

    def finding(severity: str, tag_name: str, code: str, **params) -> None:
        findings.append(
            {"severity": severity, "tag": tag_name, "code": code, "issue": i18n.t(language, code, **params)}
        )

    for tag in tags:
        ttype = tag.get("type", "")
        name = tag.get("name") or ""
        params = _flat_params(tag)

        if ttype in GA4_CONFIG_TYPES:
            mid = params.get("measurementId") or params.get("tagId")
            ga4_configs.append(
                {
                    "name": name,
                    "tagId": tag.get("tagId"),
                    "measurementId": mid,
                    "server_container_url": _server_url(params),
                }
            )
            if not mid:
                finding("high", name, "ga4_config_no_mid")

        elif ttype in GA4_EVENT_TYPES:
            event_name = params.get("eventName") or "(unknown)"
            mid = params.get("measurementId") or params.get("measurementIdOverride")
            provided = _event_parameter_names(params)
            ga4_events_by_config[mid or "(no-config)"].append(
                {"name": name, "tagId": tag.get("tagId"), "event": event_name, "params": sorted(provided)}
            )
            required = GA4_REQUIRED_BY_EVENT.get(event_name)
            if required:
                missing = required - provided
                if missing:
                    finding("high", name, "ga4_event_missing_params", event=event_name, params=sorted(missing))

        elif ttype in ADS_CONVERSION_TYPES:
            ads_conversions.append(
                {
                    "name": name,
                    "tagId": tag.get("tagId"),
                    "conversionId": params.get("conversionId"),
                    "conversionLabel": params.get("conversionLabel"),
                }
            )
            if not params.get("conversionId"):
                finding("high", name, "ads_conversion_no_id")

        elif ttype == ADS_LINKER_TYPE:
            ads_linker = True

        if any(h in ttype for h in META_TYPE_HINTS) or any(h in name for h in META_TYPE_HINTS):
            meta_pixels.append(
                {
                    "name": name,
                    "tagId": tag.get("tagId"),
                    "pixelId": params.get("pixelId") or params.get("pixel_id"),
                    "event": params.get("eventName") or params.get("standardEventName"),
                }
            )

        if _server_url(params):
            server_side_tags.append(name)

    # A Google tag can also inherit the server URL from a configuration-settings variable.
    for var in snapshot.get("variables", []) or []:
        if var.get("type") == "gtcs" and _server_url(_flat_params(var)):
            server_side_tags.append(f"{var.get('name')} (variable)")

    if ads_conversions and not ads_linker:
        finding("medium", "(global)", "ads_no_linker")

    if not server_side_tags and (len(ga4_configs) + len(ads_conversions) + len(meta_pixels)) >= 3:
        finding("low", "(global)", "no_server_side")

    return {
        "ga4_configs": ga4_configs,
        "ga4_events_by_config": dict(ga4_events_by_config),
        "ads_conversions": ads_conversions,
        "ads_conversion_linker_present": ads_linker,
        "meta_pixels": meta_pixels,
        "server_side_tags": server_side_tags,
        "client_side_tag_count": len(tags) - len(server_side_tags),
        "findings": findings,
    }


def _first_present(d: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if d.get(k):
            return d[k]
    return None


def _server_url(params: dict[str, Any]) -> str | None:
    """server_container_url, whether set as a field or as a configuration-settings row.

    The Google tag and the "Google tag: Configuration settings" variable keep it
    in a list of {parameter, parameterValue} maps, not as a top-level key.
    """
    direct = _first_present(params, SERVER_HINT_KEYS)
    if direct:
        return direct
    for row in params.get("configSettingsTable") or []:
        if isinstance(row, dict) and row.get("parameter") in SERVER_HINT_KEYS and row.get("parameterValue"):
            return str(row["parameterValue"])
    return None

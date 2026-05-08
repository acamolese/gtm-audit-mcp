"""Validazione tracciamento: mappa eventi GA4/Ads/Meta + consent + server-side."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

GA4_CONFIG_TYPES = {"gaawc", "googtag"}
GA4_EVENT_TYPES = {"gaawe"}
ADS_CONVERSION_TYPES = {"awct", "awcr"}
ADS_LINKER_TYPE = "gclidw"
META_TYPE_HINTS = ("Facebook Pixel", "Meta Pixel", "Facebook", "Meta")
SERVER_HINT_KEYS = ("server_container_url", "serverContainerUrl", "transport_url", "transportUrl")

# Parametri raccomandati per GA4 ecommerce
GA4_REQUIRED_BY_EVENT = {
    "purchase": {"transaction_id", "value", "currency", "items"},
    "begin_checkout": {"value", "currency", "items"},
    "add_to_cart": {"value", "currency", "items"},
    "view_item": {"value", "currency", "items"},
    "generate_lead": {"value", "currency"},
}


def _param_value(params: list[dict] | None, key: str) -> Any:
    for p in params or []:
        if p.get("key") == key:
            return p.get("value") or p.get("list") or p.get("map")
    return None


def _flat_params(tag: dict) -> dict[str, Any]:
    """Estrae i parametri di un tag in dict piatto stringa→valore."""
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


def validate_tracking(snapshot: dict[str, Any]) -> dict[str, Any]:
    tags = snapshot.get("tags", []) or []

    ga4_events_by_config: dict[str, list[dict]] = defaultdict(list)
    ga4_configs: list[dict] = []
    ads_conversions: list[dict] = []
    ads_linker = False
    meta_pixels: list[dict] = []
    server_side_hints: list[str] = []
    findings: list[dict] = []

    for tag in tags:
        ttype = tag.get("type", "")
        params = _flat_params(tag)

        # GA4 Configuration
        if ttype in GA4_CONFIG_TYPES:
            mid = params.get("measurementId") or params.get("tagId")
            ga4_configs.append({
                "name": tag.get("name"),
                "tagId": tag.get("tagId"),
                "measurementId": mid,
                "server_container_url": _first_present(params, SERVER_HINT_KEYS),
            })
            if not mid:
                findings.append({
                    "severity": "high",
                    "tag": tag.get("name"),
                    "issue": "GA4 Configuration senza Measurement ID",
                })

        # GA4 Event
        elif ttype in GA4_EVENT_TYPES:
            event_name = params.get("eventName") or "(unknown)"
            mid = params.get("measurementId") or params.get("measurementIdOverride")
            ga4_events_by_config[mid or "(no-config)"].append({
                "name": tag.get("name"),
                "tagId": tag.get("tagId"),
                "event": event_name,
                "params": list((params.get("eventParameters") or {}).keys())
                          if isinstance(params.get("eventParameters"), dict) else [],
            })
            # Parametri obbligatori per evento ecommerce
            required = GA4_REQUIRED_BY_EVENT.get(event_name)
            if required:
                provided = set()
                ev_params = params.get("eventParameters")
                if isinstance(ev_params, dict):
                    provided = set(ev_params.keys())
                missing = required - provided
                if missing:
                    findings.append({
                        "severity": "high",
                        "tag": tag.get("name"),
                        "issue": f"Evento {event_name}: mancano parametri {sorted(missing)}",
                    })

        # Google Ads conversion
        elif ttype in ADS_CONVERSION_TYPES:
            ads_conversions.append({
                "name": tag.get("name"),
                "tagId": tag.get("tagId"),
                "conversionId": params.get("conversionId"),
                "conversionLabel": params.get("conversionLabel"),
            })
            if not params.get("conversionId"):
                findings.append({
                    "severity": "high",
                    "tag": tag.get("name"),
                    "issue": "Google Ads conversion senza Conversion ID",
                })

        # Google Ads conversion linker
        elif ttype == ADS_LINKER_TYPE:
            ads_linker = True

        # Meta / Facebook (sempre tag template di terze parti)
        if any(h in ttype for h in META_TYPE_HINTS) or any(
            h in (tag.get("name") or "") for h in META_TYPE_HINTS
        ):
            meta_pixels.append({
                "name": tag.get("name"),
                "tagId": tag.get("tagId"),
                "pixelId": params.get("pixelId") or params.get("pixel_id"),
                "event": params.get("eventName") or params.get("standardEventName"),
            })

        # Server-side hint
        for k in SERVER_HINT_KEYS:
            if k in params and params[k]:
                server_side_hints.append(tag.get("name", ""))
                break

    # Ads conversion senza linker
    if ads_conversions and not ads_linker:
        findings.append({
            "severity": "medium",
            "tag": "(global)",
            "issue": "Sono presenti conversioni Google Ads ma manca il Conversion Linker.",
        })

    # Suggerimento server-side
    client_side_count = len(tags) - len(server_side_hints)
    if not server_side_hints and (len(ga4_configs) + len(ads_conversions) + len(meta_pixels)) >= 3:
        findings.append({
            "severity": "low",
            "tag": "(global)",
            "issue": "Nessun tag punta a un container server-side: valuta la migrazione a sGTM "
                     "per ridurre l'impatto di adblocker e ITP.",
        })

    return {
        "ga4_configs": ga4_configs,
        "ga4_events_by_config": dict(ga4_events_by_config),
        "ads_conversions": ads_conversions,
        "ads_conversion_linker_present": ads_linker,
        "meta_pixels": meta_pixels,
        "server_side_tags": server_side_hints,
        "client_side_tag_count": client_side_count,
        "findings": findings,
    }


def _first_present(d: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if d.get(k):
            return d[k]
    return None

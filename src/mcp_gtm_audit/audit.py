"""Regole di audit su uno snapshot GTM (workspace o version)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# Trigger built-in di GTM senza ID nelle proprietà standard.
ALWAYS_TRIGGER_ID = "2147479553"  # All Pages

GA4_CONFIG_TYPES = {"gaawc", "googtag"}
GA4_EVENT_TYPES = {"gaawe"}
ADS_TYPES = {"awct", "sp", "awcr"}  # conversion tracking, remarketing, conversion linker
META_TYPES_HINTS = ("Facebook", "Meta", "Pixel")


@dataclass
class Issue:
    severity: str
    code: str
    title: str
    detail: str
    entity_type: str = ""
    entity_name: str = ""
    entity_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "entity_id": self.entity_id,
        }


@dataclass
class AuditResult:
    snapshot: dict[str, Any]
    issues: list[Issue] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": {
                "source": self.snapshot.get("source"),
                "accountId": self.snapshot.get("accountId"),
                "containerId": self.snapshot.get("containerId"),
                "workspaceId": self.snapshot.get("workspaceId"),
                "versionId": self.snapshot.get("versionId"),
            },
            "stats": self.stats,
            "issues": [i.to_dict() for i in self.issues],
        }


def _param_value(params: list[dict] | None, key: str) -> str | None:
    for p in params or []:
        if p.get("key") == key:
            return p.get("value")
    return None


def _all_strings(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_all_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_all_strings(v))
    elif isinstance(obj, str):
        out.append(obj)
    return out


def _variable_references(text: str) -> set[str]:
    return set(re.findall(r"\{\{([^}]+)\}\}", text))


def run_audit(snapshot: dict[str, Any]) -> AuditResult:
    result = AuditResult(snapshot=snapshot)
    tags = snapshot.get("tags", []) or []
    triggers = snapshot.get("triggers", []) or []
    variables = snapshot.get("variables", []) or []

    trigger_by_id = {t["triggerId"]: t for t in triggers}
    variable_names = {v["name"] for v in variables}
    used_trigger_ids: set[str] = set()
    used_variable_names: set[str] = set()

    # ----- Pre-scan riferimenti a variabili -----
    for tag in tags:
        for s in _all_strings(tag):
            used_variable_names.update(_variable_references(s))
    for trig in triggers:
        for s in _all_strings(trig):
            used_variable_names.update(_variable_references(s))
    for var in variables:
        for s in _all_strings(var):
            used_variable_names.update(_variable_references(s))

    # ----- Audit per tag -----
    type_counts: Counter[str] = Counter()
    duplicate_signature: dict[str, list[dict]] = defaultdict(list)

    for tag in tags:
        type_counts[tag.get("type", "unknown")] += 1
        firing = tag.get("firingTriggerId") or []
        blocking = tag.get("blockingTriggerId") or []
        used_trigger_ids.update(firing)
        used_trigger_ids.update(blocking)

        # Tag senza trigger
        if not firing:
            result.add(Issue(
                SEVERITY_HIGH, "tag_no_trigger",
                "Tag senza trigger di firing",
                "Il tag non si attiverà mai. Aggiungi almeno un trigger o eliminalo.",
                "tag", tag.get("name", ""), tag.get("tagId", ""),
            ))

        # Tag in pausa
        if tag.get("paused"):
            result.add(Issue(
                SEVERITY_LOW, "tag_paused",
                "Tag in pausa",
                "Il tag è in pausa: verifica se va riattivato o rimosso.",
                "tag", tag.get("name", ""), tag.get("tagId", ""),
            ))

        # Custom HTML
        if tag.get("type") == "html":
            html = _param_value(tag.get("parameter"), "html") or ""
            detail = "Custom HTML in produzione: rivedi sicurezza, performance e privacy."
            if "document.write" in html:
                detail += " Contiene document.write (sconsigliato)."
            result.add(Issue(
                SEVERITY_MEDIUM, "tag_custom_html",
                "Custom HTML attivo",
                detail,
                "tag", tag.get("name", ""), tag.get("tagId", ""),
            ))

        # GA4 Configuration senza Measurement ID
        if tag.get("type") in GA4_CONFIG_TYPES:
            mid = (
                _param_value(tag.get("parameter"), "measurementId")
                or _param_value(tag.get("parameter"), "measurementIdOverride")
                or _param_value(tag.get("parameter"), "tagId")
            )
            if not mid:
                result.add(Issue(
                    SEVERITY_HIGH, "ga4_missing_mid",
                    "GA4 Configuration senza Measurement ID",
                    "Configura il Measurement ID (formato G-XXXXX) per trasmettere dati a GA4.",
                    "tag", tag.get("name", ""), tag.get("tagId", ""),
                ))

        # GA4 Event senza riferimento a un Configuration tag o senza event name
        if tag.get("type") in GA4_EVENT_TYPES:
            event_name = _param_value(tag.get("parameter"), "eventName")
            measurement = _param_value(tag.get("parameter"), "measurementId")
            config_ref = _param_value(tag.get("parameter"), "measurementIdOverride")
            if not event_name:
                result.add(Issue(
                    SEVERITY_HIGH, "ga4_event_no_name",
                    "GA4 Event senza event name",
                    "Imposta un eventName: i tag GA4 senza nome non producono eventi validi.",
                    "tag", tag.get("name", ""), tag.get("tagId", ""),
                ))
            if not measurement and not config_ref:
                result.add(Issue(
                    SEVERITY_MEDIUM, "ga4_event_no_config",
                    "GA4 Event senza riferimento a Configuration",
                    "Specifica una GA4 Configuration o un Measurement ID di override.",
                    "tag", tag.get("name", ""), tag.get("tagId", ""),
                ))

        # Consent settings
        consent = tag.get("consentSettings", {})
        if not consent or consent.get("consentStatus") == "NOT_SET":
            result.add(Issue(
                SEVERITY_MEDIUM, "tag_no_consent",
                "Tag senza Additional Consent Checks",
                "Configura le Additional Consent Checks per rispettare il Consent Mode v2.",
                "tag", tag.get("name", ""), tag.get("tagId", ""),
            ))

        # Riferimenti a variabili eliminate
        refs = set()
        for s in _all_strings(tag):
            refs.update(_variable_references(s))
        missing = refs - variable_names - _builtin_names(snapshot)
        if missing:
            result.add(Issue(
                SEVERITY_HIGH, "tag_dead_variable",
                "Tag referenzia variabili inesistenti",
                "Variabili non trovate nel container: " + ", ".join(sorted(missing)),
                "tag", tag.get("name", ""), tag.get("tagId", ""),
            ))

        # Firma per duplicati: tipo + parametri normalizzati
        sig = _tag_signature(tag)
        duplicate_signature[sig].append(tag)

    # Tag duplicati (>1 con stessa firma)
    for sig, group in duplicate_signature.items():
        if len(group) > 1:
            names = ", ".join(t.get("name", "?") for t in group)
            result.add(Issue(
                SEVERITY_MEDIUM, "tag_duplicate",
                "Tag potenzialmente duplicati",
                f"{len(group)} tag con configurazione equivalente: {names}",
                "tag", names, ",".join(t.get("tagId", "") for t in group),
            ))

    # ----- Trigger orfani -----
    for trig in triggers:
        tid = trig.get("triggerId")
        if tid not in used_trigger_ids and tid != ALWAYS_TRIGGER_ID:
            result.add(Issue(
                SEVERITY_LOW, "trigger_orphan",
                "Trigger non utilizzato",
                "Nessun tag fa riferimento a questo trigger. Verifica se va eliminato.",
                "trigger", trig.get("name", ""), tid or "",
            ))

    # ----- Variabili inutilizzate -----
    for var in variables:
        if var["name"] not in used_variable_names:
            result.add(Issue(
                SEVERITY_LOW, "variable_unused",
                "Variabile non utilizzata",
                "Nessun tag, trigger o altra variabile la referenzia.",
                "variable", var["name"], var.get("variableId", ""),
            ))

    # ----- Naming convention -----
    name_issues = _check_naming(tags, "tag")
    name_issues += _check_naming(triggers, "trigger")
    name_issues += _check_naming(variables, "variable")
    for issue in name_issues:
        result.add(issue)

    # ----- Stats finali -----
    result.stats = {
        "tags": len(tags),
        "triggers": len(triggers),
        "variables": len(variables),
        "tags_by_type": dict(type_counts),
        "issues_total": len(result.issues),
        "issues_high": sum(1 for i in result.issues if i.severity == SEVERITY_HIGH),
        "issues_medium": sum(1 for i in result.issues if i.severity == SEVERITY_MEDIUM),
        "issues_low": sum(1 for i in result.issues if i.severity == SEVERITY_LOW),
    }
    return result


def _builtin_names(snapshot: dict[str, Any]) -> set[str]:
    return {b.get("name", "") for b in snapshot.get("builtInVariables", []) or []}


def _tag_signature(tag: dict) -> str:
    params = tag.get("parameter") or []
    norm = sorted(
        (p.get("key", ""), p.get("type", ""), p.get("value", ""))
        for p in params
        if p.get("key") not in ("tagFiringOption", "useDebugVersion")
    )
    return f"{tag.get('type', '')}|{norm}|{sorted(tag.get('firingTriggerId') or [])}"


def _check_naming(items: list[dict], kind: str) -> list[Issue]:
    issues: list[Issue] = []
    seen_names: dict[str, int] = Counter(i.get("name", "") for i in items)
    for item in items:
        name = item.get("name", "")
        if not name:
            continue
        if seen_names[name] > 1:
            issues.append(Issue(
                SEVERITY_MEDIUM, f"{kind}_duplicate_name",
                f"{kind.capitalize()} con nome duplicato",
                f"Esistono {seen_names[name]} {kind} con lo stesso nome '{name}'.",
                kind, name, item.get(f"{kind}Id", ""),
            ))
        if name.startswith("Untitled") or name.lower().startswith("copy of"):
            issues.append(Issue(
                SEVERITY_LOW, f"{kind}_default_name",
                f"{kind.capitalize()} con nome di default",
                f"Rinomina '{name}' usando una convenzione esplicita.",
                kind, name, item.get(f"{kind}Id", ""),
            ))
    return issues

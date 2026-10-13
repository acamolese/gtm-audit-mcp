"""Audit rules over a container snapshot (workspace or version).

Rules are pure functions over the snapshot: no I/O, no HTTP. Each issue carries
a code and parameters; the wording is resolved by `i18n` when the result is
serialised, so the same run can be reported in any supported language.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from . import i18n

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# Built-in "All Pages" trigger: it never appears in the trigger list.
ALWAYS_TRIGGER_ID = "2147479553"
BUILTIN_TRIGGER_IDS = {ALWAYS_TRIGGER_ID, "2147479572", "2147479573"}  # All Pages, Consent Init, Initialization

GA4_CONFIG_TYPES = {"gaawc", "googtag"}
GA4_EVENT_TYPES = {"gaawe"}


@dataclass
class Issue:
    severity: str
    code: str
    entity_type: str = ""
    entity_name: str = ""
    entity_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, language: str = "en") -> dict[str, Any]:
        base = self.code
        if self.code.endswith("_duplicate_name"):
            base = "duplicate_name"
        elif self.code.endswith("_default_name"):
            base = "default_name"
        params = dict(self.params)
        if "kind" in params:
            params["kind"] = i18n.t(language, f"kind.{params['kind']}")
            params["kind_lower"] = params["kind"].lower()
        if base == "tag_custom_html":
            params["document_write"] = (
                i18n.t(language, "tag_custom_html.document_write") if params.get("document_write") else ""
            )
        return {
            "severity": self.severity,
            "code": self.code,
            "title": i18n.t(language, f"{base}.title", **params),
            "detail": i18n.t(language, f"{base}.detail", **params),
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

    def to_dict(self, language: str = "en") -> dict[str, Any]:
        return {
            "snapshot": {
                "source": self.snapshot.get("source"),
                "accountId": self.snapshot.get("accountId"),
                "containerId": self.snapshot.get("containerId"),
                "workspaceId": self.snapshot.get("workspaceId"),
                "versionId": self.snapshot.get("versionId"),
            },
            "stats": self.stats,
            "issues": [i.to_dict(language) for i in self.issues],
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

    variable_names = {v.get("name", "") for v in variables}
    builtin_names = _builtin_names(snapshot)
    used_trigger_ids: set[str] = set()
    used_variable_names: set[str] = set()

    for entity in (*tags, *triggers, *variables):
        for s in _all_strings(entity):
            used_variable_names.update(_variable_references(s))

    type_counts: Counter[str] = Counter()
    duplicate_signature: dict[str, list[dict]] = defaultdict(list)

    for tag in tags:
        name, tag_id = tag.get("name", ""), tag.get("tagId", "")
        type_counts[tag.get("type", "unknown")] += 1
        firing = tag.get("firingTriggerId") or []
        blocking = tag.get("blockingTriggerId") or []
        used_trigger_ids.update(firing)
        used_trigger_ids.update(blocking)

        if not firing:
            result.add(Issue(SEVERITY_HIGH, "tag_no_trigger", "tag", name, tag_id))

        if tag.get("paused"):
            result.add(Issue(SEVERITY_LOW, "tag_paused", "tag", name, tag_id))

        if tag.get("type") == "html":
            html = _param_value(tag.get("parameter"), "html") or ""
            result.add(
                Issue(
                    SEVERITY_MEDIUM,
                    "tag_custom_html",
                    "tag",
                    name,
                    tag_id,
                    {"document_write": "document.write" in html},
                )
            )

        if tag.get("type") in GA4_CONFIG_TYPES:
            mid = (
                _param_value(tag.get("parameter"), "measurementId")
                or _param_value(tag.get("parameter"), "measurementIdOverride")
                or _param_value(tag.get("parameter"), "tagId")
            )
            if not mid:
                result.add(Issue(SEVERITY_HIGH, "ga4_missing_mid", "tag", name, tag_id))

        if tag.get("type") in GA4_EVENT_TYPES:
            event_name = _param_value(tag.get("parameter"), "eventName")
            measurement = _param_value(tag.get("parameter"), "measurementId")
            config_ref = _param_value(tag.get("parameter"), "measurementIdOverride")
            if not event_name:
                result.add(Issue(SEVERITY_HIGH, "ga4_event_no_name", "tag", name, tag_id))
            if not measurement and not config_ref:
                result.add(Issue(SEVERITY_MEDIUM, "ga4_event_no_config", "tag", name, tag_id))

        consent = tag.get("consentSettings") or {}
        if not consent or consent.get("consentStatus") == "NOT_SET":
            result.add(Issue(SEVERITY_MEDIUM, "tag_no_consent", "tag", name, tag_id))

        refs: set[str] = set()
        for s in _all_strings(tag):
            refs.update(_variable_references(s))
        missing = refs - variable_names - builtin_names
        if missing:
            result.add(
                Issue(
                    SEVERITY_HIGH,
                    "tag_dead_variable",
                    "tag",
                    name,
                    tag_id,
                    {"names": ", ".join(sorted(missing))},
                )
            )

        duplicate_signature[_tag_signature(tag)].append(tag)

    for group in duplicate_signature.values():
        if len(group) > 1:
            names = ", ".join(t.get("name", "?") for t in group)
            result.add(
                Issue(
                    SEVERITY_MEDIUM,
                    "tag_duplicate",
                    "tag",
                    names,
                    ",".join(t.get("tagId", "") for t in group),
                    {"count": len(group), "names": names},
                )
            )

    for trig in triggers:
        tid = trig.get("triggerId")
        if tid not in used_trigger_ids and tid not in BUILTIN_TRIGGER_IDS:
            result.add(Issue(SEVERITY_LOW, "trigger_orphan", "trigger", trig.get("name", ""), tid or ""))

    for var in variables:
        if var.get("name") not in used_variable_names:
            result.add(
                Issue(SEVERITY_LOW, "variable_unused", "variable", var.get("name", ""), var.get("variableId", ""))
            )

    for kind, items in (("tag", tags), ("trigger", triggers), ("variable", variables)):
        for issue in _check_naming(items, kind):
            result.add(issue)

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
    seen_names: Counter[str] = Counter(i.get("name", "") for i in items)
    for item in items:
        name = item.get("name", "")
        if not name:
            continue
        entity_id = item.get(f"{kind}Id", "")
        if seen_names[name] > 1:
            issues.append(
                Issue(
                    SEVERITY_MEDIUM,
                    f"{kind}_duplicate_name",
                    kind,
                    name,
                    entity_id,
                    {"kind": kind, "count": seen_names[name], "name": name},
                )
            )
        if name.startswith("Untitled") or name.lower().startswith("copy of"):
            issues.append(
                Issue(SEVERITY_LOW, f"{kind}_default_name", kind, name, entity_id, {"kind": kind, "name": name})
            )
    return issues

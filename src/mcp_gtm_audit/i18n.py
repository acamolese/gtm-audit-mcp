"""User-facing strings of the audit, tracking findings and HTML report.

Rules return a code and parameters; the text is resolved here in the language
the caller asked for. Adding a language is one more dictionary.
"""

from __future__ import annotations

LANGUAGES = ("en", "it")

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # audit issues: title / detail
        "tag_no_trigger.title": "Tag without a firing trigger",
        "tag_no_trigger.detail": "The tag can never fire. Add a trigger or delete it.",
        "tag_paused.title": "Paused tag",
        "tag_paused.detail": "The tag is paused: decide whether to re-enable or remove it.",
        "tag_custom_html.title": "Active Custom HTML tag",
        "tag_custom_html.detail": "Custom HTML in production: review it for security, performance and privacy.{document_write}",
        "tag_custom_html.document_write": " It uses document.write, which breaks on asynchronous loads.",
        "ga4_missing_mid.title": "Google tag without a Measurement ID",
        "ga4_missing_mid.detail": "Set the Measurement ID (G-XXXXXXX) or the tag sends nothing to GA4.",
        "ga4_event_no_name.title": "GA4 event without an event name",
        "ga4_event_no_name.detail": "Set eventName: GA4 event tags without a name do not produce valid events.",
        "ga4_event_no_config.title": "GA4 event without a Measurement ID",
        "ga4_event_no_config.detail": "Point the event at a Google tag or set a Measurement ID override.",
        "tag_no_consent.title": "Tag without Additional Consent Checks",
        "tag_no_consent.detail": "Set the consent requirements so the tag respects Consent Mode v2.",
        "tag_dead_variable.title": "Tag references variables that do not exist",
        "tag_dead_variable.detail": "Variables not found in the container: {names}",
        "tag_duplicate.title": "Possibly duplicated tags",
        "tag_duplicate.detail": "{count} tags with an equivalent configuration: {names}",
        "trigger_orphan.title": "Unused trigger",
        "trigger_orphan.detail": "No tag references this trigger. Check whether it should be deleted.",
        "variable_unused.title": "Unused variable",
        "variable_unused.detail": "No tag, trigger or variable references it.",
        "duplicate_name.title": "{kind} with a duplicated name",
        "duplicate_name.detail": "{count} {kind_lower}s share the name '{name}'.",
        "default_name.title": "{kind} with a default name",
        "default_name.detail": "Rename '{name}' following an explicit naming convention.",
        # tracking findings
        "ga4_config_no_mid": "Google tag without a Measurement ID",
        "ga4_event_missing_params": "Event {event}: missing parameters {params}",
        "ads_conversion_no_id": "Google Ads conversion without a Conversion ID",
        "ads_no_linker": "Google Ads conversions are present but the Conversion Linker tag is missing.",
        "no_server_side": "No tag points to a server-side container: consider server-side tagging to limit the impact of ad blockers and ITP.",
        # report
        "report.title": "Google Tag Manager audit",
        "report.generated": "generated",
        "report.tags": "Tags",
        "report.triggers": "Triggers",
        "report.variables": "Variables",
        "report.high": "High severity",
        "report.medium": "Medium",
        "report.low": "Low",
        "report.by_type": "Tags by type",
        "report.type": "Type",
        "report.count": "Count",
        "report.no_tags": "No tags",
        "report.issues": "Issues found ({n})",
        "report.severity": "Severity",
        "report.code": "Code",
        "report.entity": "Entity",
        "report.detail": "Detail",
        "report.no_issues": "No issues found",
        "report.tracking": "Tracking validation",
        "report.tag": "Tag",
        "report.issue": "Issue",
        "report.no_findings": "No tracking findings",
        "report.ga4_configs": "Google tags (GA4)",
        "report.measurement_id": "Measurement ID",
        "report.server_container": "Server container",
        "report.no_ga4": "No Google tag",
        "report.ads": "Google Ads conversions",
        "report.conversion_id": "Conversion ID",
        "report.conversion_label": "Conversion label",
        "report.no_ads": "No Google Ads conversion",
        "report.snapshot": "Snapshot",
        "kind.tag": "Tag",
        "kind.trigger": "Trigger",
        "kind.variable": "Variable",
    },
    "it": {
        "tag_no_trigger.title": "Tag senza trigger di attivazione",
        "tag_no_trigger.detail": "Il tag non si attiverà mai. Aggiungi un trigger o eliminalo.",
        "tag_paused.title": "Tag in pausa",
        "tag_paused.detail": "Il tag è in pausa: decidere se riattivarlo o rimuoverlo.",
        "tag_custom_html.title": "Tag Custom HTML attivo",
        "tag_custom_html.detail": "Custom HTML in produzione: verificare sicurezza, prestazioni e privacy.{document_write}",
        "tag_custom_html.document_write": " Usa document.write, che si rompe con i caricamenti asincroni.",
        "ga4_missing_mid.title": "Google tag senza Measurement ID",
        "ga4_missing_mid.detail": "Impostare il Measurement ID (G-XXXXXXX), altrimenti il tag non invia nulla a GA4.",
        "ga4_event_no_name.title": "Evento GA4 senza nome evento",
        "ga4_event_no_name.detail": "Impostare eventName: i tag evento GA4 senza nome non producono eventi validi.",
        "ga4_event_no_config.title": "Evento GA4 senza Measurement ID",
        "ga4_event_no_config.detail": "Collegare l'evento a un Google tag o impostare un Measurement ID di override.",
        "tag_no_consent.title": "Tag senza Additional Consent Checks",
        "tag_no_consent.detail": "Impostare i requisiti di consenso perché il tag rispetti il Consent Mode v2.",
        "tag_dead_variable.title": "Il tag richiama variabili inesistenti",
        "tag_dead_variable.detail": "Variabili non trovate nel container: {names}",
        "tag_duplicate.title": "Tag potenzialmente duplicati",
        "tag_duplicate.detail": "{count} tag con configurazione equivalente: {names}",
        "trigger_orphan.title": "Trigger non utilizzato",
        "trigger_orphan.detail": "Nessun tag richiama questo trigger. Verificare se va eliminato.",
        "variable_unused.title": "Variabile non utilizzata",
        "variable_unused.detail": "Nessun tag, trigger o variabile la richiama.",
        "duplicate_name.title": "{kind} con nome duplicato",
        "duplicate_name.detail": "{count} {kind_lower} hanno lo stesso nome '{name}'.",
        "default_name.title": "{kind} con nome di default",
        "default_name.detail": "Rinominare '{name}' seguendo una convenzione esplicita.",
        "ga4_config_no_mid": "Google tag senza Measurement ID",
        "ga4_event_missing_params": "Evento {event}: mancano i parametri {params}",
        "ads_conversion_no_id": "Conversione Google Ads senza Conversion ID",
        "ads_no_linker": "Ci sono conversioni Google Ads ma manca il tag Conversion Linker.",
        "no_server_side": "Nessun tag punta a un container server-side: valutare il server-side tagging per limitare l'impatto di ad blocker e ITP.",
        "report.title": "Audit Google Tag Manager",
        "report.generated": "generato",
        "report.tags": "Tag",
        "report.triggers": "Trigger",
        "report.variables": "Variabili",
        "report.high": "Criticità alta",
        "report.medium": "Media",
        "report.low": "Bassa",
        "report.by_type": "Tag per tipo",
        "report.type": "Tipo",
        "report.count": "Conteggio",
        "report.no_tags": "Nessun tag",
        "report.issues": "Criticità rilevate ({n})",
        "report.severity": "Severità",
        "report.code": "Codice",
        "report.entity": "Entità",
        "report.detail": "Dettaglio",
        "report.no_issues": "Nessuna criticità rilevata",
        "report.tracking": "Validazione del tracciamento",
        "report.tag": "Tag",
        "report.issue": "Problema",
        "report.no_findings": "Nessun problema di tracciamento",
        "report.ga4_configs": "Google tag (GA4)",
        "report.measurement_id": "Measurement ID",
        "report.server_container": "Container server",
        "report.no_ga4": "Nessun Google tag",
        "report.ads": "Conversioni Google Ads",
        "report.conversion_id": "Conversion ID",
        "report.conversion_label": "Conversion label",
        "report.no_ads": "Nessuna conversione Google Ads",
        "report.snapshot": "Snapshot",
        "kind.tag": "Tag",
        "kind.trigger": "Trigger",
        "kind.variable": "Variabile",
    },
}


def normalize_language(language: str | None) -> str:
    value = (language or "en").strip().lower()[:2]
    return value if value in LANGUAGES else "en"


def t(language: str, key: str, **params) -> str:
    """Translate `key`, falling back to English, then to the key itself."""
    lang = normalize_language(language)
    text = _STRINGS[lang].get(key) or _STRINGS["en"].get(key) or key
    try:
        return text.format(**params)
    except (KeyError, IndexError):
        return text


def keys() -> set[str]:
    return set(_STRINGS["en"])

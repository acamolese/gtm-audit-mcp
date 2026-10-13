from mcp_gtm_audit import i18n


def test_every_language_has_every_key():
    en = i18n.keys()
    for lang in i18n.LANGUAGES:
        assert set(i18n._STRINGS[lang]) == en, lang


def test_unknown_language_falls_back_to_english():
    assert i18n.normalize_language("de") == "en"
    assert i18n.t("de", "report.title") == "Google Tag Manager audit"
    assert i18n.t("it-IT", "report.title") == "Audit Google Tag Manager"


def test_no_client_or_agency_names_in_the_copy():
    text = " ".join(" ".join(d.values()) for d in i18n._STRINGS.values()).lower()
    for banned in ("genoma", "camicissima", "magis", "maurel"):
        assert banned not in text

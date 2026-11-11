from __future__ import annotations

import builtins

from langbot_plugin.cli import i18n
from langbot_plugin.cli.utils import form


def test_i18n_manager_detects_locale_from_environment(monkeypatch):
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")

    assert i18n.I18nManager().get_current_locale() == "zh_Hans"

    monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
    assert i18n.I18nManager().get_current_locale() == "es_ES"


def test_set_locale_ignores_unsupported_locale_and_translate_falls_back_to_key():
    original = i18n.get_current_locale()
    try:
        i18n.set_locale("en_US")
        assert i18n.get_current_locale() == "en_US"
        assert i18n.t("missing_key") == "missing_key"
        i18n.set_locale("not_real")
        assert i18n.get_current_locale() == "en_US"
    finally:
        i18n.set_locale(original)


def test_extract_i18n_label_uses_current_locale_then_english_fallback():
    original = i18n.get_current_locale()
    try:
        i18n.set_locale("zh_Hans")
        assert i18n.extract_i18n_label({"en_US": "Name", "zh_Hans": "名称"}) == "名称"
        assert i18n.extract_i18n_label({"en_US": "Name"}) == "Name"
    finally:
        i18n.set_locale(original)


def test_input_form_values_retries_required_invalid_value(monkeypatch, capsys):
    answers = iter(["Bad Value", "good_name", "description"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))
    fields = [
        {
            "name": "tool_name",
            "label": {"en_US": "Tool name"},
            "required": True,
            "format": {
                "regexp": form.NUMBER_LOWER_UNDERSCORE_REGEXP,
                "error": {"en_US": "Bad tool name"},
            },
        },
        {
            "name": "description",
            "label": {"en_US": "Description"},
            "required": False,
        },
    ]

    values = form.input_form_values(fields)

    assert values == {"tool_name": "good_name", "description": "description"}
    assert "Bad tool name" in capsys.readouterr().out

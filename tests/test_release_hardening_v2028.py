import json
from pathlib import Path

import pytest


def _flat(obj, prefix=""):
    out = {}
    for key, value in obj.items():
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(_flat(value, full))
        else:
            out[full] = str(value)
    return out


def test_money_parser_rejects_non_numeric_input():
    from utils.money import parse_money, set_money_locale

    set_money_locale(currency="CHF", number_format="swiss")
    assert parse_money("", empty_is_zero=True) == 0.0
    with pytest.raises(ValueError):
        parse_money("", empty_is_zero=False)
    for raw in ["abc", "CHF", "12abc", "--12", "€€"]:
        with pytest.raises(ValueError):
            parse_money(raw)


def test_budget_modes_are_language_neutral():
    from model.budget_modes import (
        BUDGET_MODE_ALL,
        BUDGET_MODE_MONTH,
        BUDGET_MODE_RANGE,
        normalize_budget_mode,
    )

    assert normalize_budget_mode("Alle") == BUDGET_MODE_ALL
    assert normalize_budget_mode("All") == BUDGET_MODE_ALL
    assert normalize_budget_mode("Tous") == BUDGET_MODE_ALL
    assert normalize_budget_mode("Monat") == BUDGET_MODE_MONTH
    assert normalize_budget_mode("Month") == BUDGET_MODE_MONTH
    assert normalize_budget_mode("Mois") == BUDGET_MODE_MONTH
    assert normalize_budget_mode("Bereich") == BUDGET_MODE_RANGE
    assert normalize_budget_mode("Range") == BUDGET_MODE_RANGE
    assert normalize_budget_mode("Période") == BUDGET_MODE_RANGE


def test_en_fr_no_known_german_ui_regressions():
    forbidden_terms = [
        "Monat",
        "Bereich",
        "Bearbeiten",
        "Sparziel freigeben",
        "Sparziel abschliessen",
        "Fixkosten buchen",
        "Zeilen aus",
        "Jahr kopieren",
        "Alles aufklappen",
        "Alles zuklappen",
        "Bis Ebene",
        "Speichern fehlgeschlagen",
        "Nicht genug Tags",
        "Separaten Kategorien-Tab anzeigen",
        "Alle Dateien",
    ]
    for lang in ["en", "fr"]:
        data = _flat(
            json.loads((Path("locales") / f"{lang}.json").read_text(encoding="utf-8"))
        )
        offenders = []
        for key, value in data.items():
            for term in forbidden_terms:
                if term in value:
                    offenders.append((key, term, value))
        assert offenders == []

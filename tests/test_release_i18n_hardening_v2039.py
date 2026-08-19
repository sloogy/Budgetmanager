from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TR_CALL_RE = re.compile(r"\b(?:tr|trf)\(\s*['\"]([^'\"]+)['\"]")
GERMAN_RESIDUAL_RE = re.compile(
    r"\b("
    r"Bitte|Fehler|Warnung|Erfolgreich|erfolgreich|fehlgeschlagen|Löschen|Bearbeiten|"
    r"Hinzufügen|Ausgaben|Einkommen|Ersparnisse|Kategorie|Betrag|Monat|Jahr|"
    r"Wiederkehrend|Fixkosten|Überschuss|Datenbank|Sicherung|Abbrechen|Speichern|"
    r"Übernehmen|Kopieren|Deutsch|Schweiz|Monatslohn|Passwort|Aktuelles|Neues|"
    r"Namen|anzeigen|auswählen|Sicherheitsstufe|Zeitraum|Optionen|Exportieren|"
    r"Gespeichert|Ordner|Pfad|Schlüssel|Währung|Sprache|Bedienung|Tabellen|Listen|"
    r"Umbenennen|Eigenschaften|Unterkategorie|Keine|Hauptkategorie|Benutzer|Statistiken|"
    r"erlaubt|Öffnen|Schließen|Schliessen|Weiter|Zurück|Eingabe|wiederholen|Aktuelle|Stufe|Wechseln|Schutz|entfernen|Entfernen|Erstellt|Dein|Zwischenablage|Kopiert|Erstellen|speichern|unter|verwenden|Zeile|Aktuell|keine|Neuer|existiert|bereits|Startfehler"
    r")\b"
)


def _flatten_values(obj: object, prefix: str = "") -> dict[str, str]:
    values: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            full = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                values.update(_flatten_values(value, full))
            elif isinstance(value, str):
                values[full] = value
    return values


def _referenced_i18n_keys() -> set[str]:
    referenced: set[str] = set()
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(
            part
            in {
                "tests",
                "tools",
                "locales",
                "docs",
                "data",
                "updater",
                "installer",
                "__pycache__",
            }
            for part in rel.parts
        ):
            continue
        referenced.update(
            TR_CALL_RE.findall(path.read_text(encoding="utf-8", errors="replace"))
        )
    return referenced


def test_en_fr_referenced_values_have_no_german_residuals():
    referenced = _referenced_i18n_keys()
    for lang in ("en", "fr"):
        values = _flatten_values(
            json.loads((ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        )
        findings = {
            key: values[key]
            for key in referenced
            if key in values
            and "language_select_dialog" not in key
            and GERMAN_RESIDUAL_RE.search(values[key])
        }
        assert findings == {}


def test_13th_salary_dialog_has_no_hardcoded_chf_or_german_default_category():
    source = (ROOT / "views" / "special_income_dialog.py").read_text(encoding="utf-8")
    assert 'setSuffix(" CHF")' not in source
    assert 'tr("income13.default_category")' in source
    assert "format_money(plan.amount)" in source


def test_copy_year_dialog_uses_localized_rule_flags():
    source = (ROOT / "views" / "copy_year_dialog.py").read_text(encoding="utf-8")
    assert "_localized_flags(row)" in source
    assert "row.flags_label," not in source


def test_github_workflow_gates_qt_translation_catalogs():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "Verify Qt translation catalogs" in workflow
    assert "python tools/verify_qt_translations.py" in workflow

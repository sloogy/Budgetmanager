from __future__ import annotations

import csv
from pathlib import Path

from app_info import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "archive" / "release-evidence"

# Der v3.0.6-Nachweis entstand in einer Umgebung ohne PySide6. Die Qt-Pruefungen
# d3 und d4 wichen dort still auf eine Textsuche im Quelltext aus und schrieben
# 200 WARN-Zeilen - 200 von 4300 Checks sind nie gelaufen, und weder Exit-Code
# noch Gate zeigten das an. Die Datei bleibt trotzdem unveraendert: Sie ist der
# Nachweis eines vergangenen Laufs; nachtraeglich ueberschrieben waere sie kein
# Nachweis mehr, sondern eine Behauptung ueber einen Lauf, den es nie gab.
# Festgeschrieben wird deshalb der genaue Schaden - jede weitere WARN-Zeile und
# jede stille Neuerzeugung faellt sofort auf. Ab der naechsten Version greift
# die Ausnahme nicht mehr, und das Werkzeug kann seither gar nicht mehr
# ausweichen (Abbruch mit Code 2 statt WARN).
DEGRADIERTE_ALTNACHWEISE = {
    "3.0.6": {"d3_form_accessibility": 100, "d4_destructive_metadata": 100}
}


def _ui_audit_matrix() -> Path:
    name = (
        "UI_USABILITY_ADHS_1000_LOOP_MATRIX_v" + APP_VERSION.replace(".", "_") + ".csv"
    )
    return EVIDENCE / name


def _erlaubte_workflows() -> list[str]:
    """Liest die erlaubte Liste aus dem Werkzeug, statt sie abzuschreiben.

    Sie stand hier viermal als ["build.yml"] und musste bei jeder Aenderung an
    vier Stellen nachgezogen werden - derselbe Fehler wie bei den Versionen in
    Loop 6.
    """
    import importlib.util

    pfad = ROOT / "tools" / "lint_procedure_check.py"
    spec = importlib.util.spec_from_file_location("lint_procedure_check", pfad)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return list(modul.ERLAUBTE_WORKFLOWS)


def test_tag_build_uses_only_the_single_release_workflow():
    workflow_dir = ROOT / ".github" / "workflows"
    assert (
        sorted(path.name for path in workflow_dir.glob("*.yml"))
        == _erlaubte_workflows()
    )
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "build:" in workflow
    assert "installer:" in workflow
    assert "manifest:" in workflow
    assert "enterprise-release-audit-10000:" not in workflow


def test_release_checklist_requires_enterprise_10000_audit():
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
    assert "python tools/enterprise_release_audit_10000.py" in checklist
    assert "--loops 10000" in checklist
    assert "10.000" in checklist


def test_ui_audit_uses_current_version_for_evidence_filename():
    source = (ROOT / "tools" / "enterprise_ui_adhs_audit_1000.py").read_text(
        encoding="utf-8"
    )
    assert "from app_info import APP_VERSION" in source
    assert "APP_VERSION.replace" in source
    assert "UI_USABILITY_ADHS_1000_LOOP_MATRIX_v2_2_24.csv" not in source


def test_ui_audit_evidence_matrix_contains_no_unproven_checks():
    """Der Dateiname allein war bisher der ganze Nachweis.

    Genau deshalb fiel nicht auf, dass die eingecheckte v3.0.6-Matrix zu einem
    Zwanzigstel aus Zeilen besteht, die eine Textsuche im Quelltext statt einer
    Qt-Pruefung protokollieren. Geprueft wird jetzt der Inhalt.
    """
    matrix = _ui_audit_matrix()
    assert matrix.is_file(), (
        f"Release-Nachweis fehlt: {matrix.relative_to(ROOT)} - erzeugen mit "
        "QT_QPA_PLATFORM=offscreen python tools/enterprise_ui_adhs_audit_1000.py"
    )
    with matrix.open(encoding="utf-8", newline="") as handle:
        zeilen = list(csv.DictReader(handle))
    assert zeilen, "Nachweismatrix ist leer"

    warnungen: dict[str, int] = {}
    for zeile in zeilen:
        if zeile["result"] == "WARN":
            warnungen[zeile["domain"]] = warnungen.get(zeile["domain"], 0) + 1
    assert not [z for z in zeilen if z["result"] == "FAIL"]

    erwartet = DEGRADIERTE_ALTNACHWEISE.get(APP_VERSION, {})
    assert warnungen == erwartet, (
        "Nachweismatrix enthaelt nicht erbrachte Pruefungen: "
        f"{warnungen} (erwartet: {erwartet or 'keine'})"
    )


def test_ui_audit_cannot_substitute_source_search_for_a_qt_run():
    """Ohne Qt darf das Werkzeug keine Matrix schreiben, sondern muss abbrechen.

    Der Rueckfallzweig lieferte ``return 0`` und eine WARN-Zeile - ein Lauf, der
    nichts geprueft hatte, sah damit aus wie ein gruener Lauf.
    """
    source = (ROOT / "tools" / "enterprise_ui_adhs_audit_1000.py").read_text(
        encoding="utf-8"
    )
    qt_pruefungen = source[
        source.index("def d3_form_accessibility") : source.index(
            "def d5_language_consistency"
        )
    ]
    assert "except" not in qt_pruefungen
    assert "read_text" not in qt_pruefungen
    assert "Qt-freie Kernprüfung" not in source
    # Der Abbruch steht vor dem ersten Schreibzugriff auf die Matrix.
    assert source.index("NICHT ERBRACHT") < source.index("csv_path.open")
    # WARN zaehlt fuer den Exit-Code wie FAIL.
    assert "return 1 if fails or warns else 0" in source


def test_release_prepare_regenerates_the_ui_audit_matrix_with_qt():
    """Die Matrix hing bisher an einem Lauf von Hand.

    Kein Workflow erzeugte sie; bei jeder Versionsanhebung wurde deshalb der
    Nachweis der Vorversion mitgeschleppt oder von Hand nachgereicht - in einer
    Umgebung, deren Qt niemand geprueft hatte.
    """
    workflow = (ROOT / ".github" / "workflows" / "release-prepare.yml").read_text(
        encoding="utf-8"
    )
    assert "tools/enterprise_ui_adhs_audit_1000.py" in workflow
    assert "requirements-build.lock" in workflow
    assert "QT_QPA_PLATFORM=offscreen" in workflow

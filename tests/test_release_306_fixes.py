"""Regressionen fuer die in v3.0.6 behobenen Fehler.

Jeder Test haelt genau einen Befund fest. Die Tests sind bewusst Qt-frei, damit
sie in der headless Gate-Batterie mitlaufen - die Ursache mehrerer frueherer
Release-Blocker war, dass GUI-Pfade nur hinter ``importorskip("PySide6")``
geprueft wurden und dadurch in jedem Gate-Lauf unsichtbar blieben.
"""

from __future__ import annotations

import ast
import json
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ── Befund 1: Architektur-Gate, main_window.py ueber Zeilenlimit ────────────
def test_hauptfenster_bleibt_unter_dem_architektur_limit():
    """v3.0.5 hatte 3502 Zeilen bei einem harten Limit von 3500."""
    zeilen = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8").count("\n")
    assert zeilen <= 3500, f"views/main_window.py hat {zeilen} Zeilen"


def test_diagnose_workflow_liegt_im_eigenen_modul():
    """Die Auslagerung darf nicht stillschweigend zurueckgedreht werden."""
    modul = ROOT / "views" / "main_window_diagnostics.py"
    assert modul.is_file()
    quelltext = modul.read_text(encoding="utf-8")
    for funktion in (
        "show_log_file",
        "show_app_log",
        "show_crash_log",
        "open_diagnostics_folder",
        "create_diagnostic_report",
    ):
        assert f"def {funktion}(" in quelltext, funktion

    hauptfenster = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    assert "from views.main_window_diagnostics import" in hauptfenster


def test_log_viewer_wird_nicht_mehr_ueber_das_hauptfenster_importiert():
    """LogViewerDialog wohnt in main_window_dialogs; der Umweg war eine Falle.

    Vor v3.0.6 zog ``tools/killcritic_usability_audit_10000.py`` den Dialog ueber
    ``views.main_window`` - also ueber ein Modul, das ihn nur weiterreichte.
    Beim Auslagern des Diagnose-Workflows brach dieser Umweg sofort.
    """
    for pfad in list((ROOT / "tools").rglob("*.py")) + list(
        (ROOT / "views").rglob("*.py")
    ):
        for nummer, zeile in enumerate(
            pfad.read_text(encoding="utf-8").splitlines(), 1
        ):
            if "from views.main_window import" in zeile and "LogViewerDialog" in zeile:
                raise AssertionError(f"{pfad.name}:{nummer}: {zeile.strip()}")


# ── Befund 2: fehlende Tab-Kette im Bankimport V4 ───────────────────────────
def test_bankimport_v4_registriert_eine_tab_kette():
    """Der V4-Dialog war als einziger komplexer Dialog nicht tastaturnavigierbar."""
    quelltext = (ROOT / "views" / "bank_import_dialog_v4.py").read_text(
        encoding="utf-8"
    )
    assert "from utils.accessibility import configure_dialog_tab_order" in quelltext
    assert "configure_dialog_tab_order(self)" in quelltext


def test_jeder_komplexe_dialog_hat_eine_tab_kette():
    """Spiegelt d10_taborder_decl aus tools/final_release_audit_1000.py.

    Als Test formuliert, damit der Befund nicht erst im 1000-Schleifen-Lauf
    auffaellt.
    """
    dateien = list((ROOT / "views").rglob("*.py")) + [ROOT / "settings_dialog.py"]
    fehlend: list[str] = []
    for pfad in dateien:
        if not pfad.exists():
            continue
        quelltext = pfad.read_text(encoding="utf-8")
        if not re.search(r"^class .*\(QDialog\)", quelltext, re.MULTILINE):
            continue
        if quelltext.count("QPushButton(") < 5:
            continue
        if (
            "configure_dialog_tab_order(" not in quelltext
            and "setTabOrder(" not in quelltext
        ):
            fehlend.append(pfad.name)
    assert not fehlend, f"Dialoge ohne Tab-Kette: {fehlend}"


# ── Befund 3: deutsche Restuebersetzungen in en.json / fr.json ──────────────
def _flach(daten, praefix: str = "") -> dict[str, object]:
    ergebnis: dict[str, object] = {}
    if isinstance(daten, dict):
        for schluessel, wert in daten.items():
            neu = f"{praefix}.{schluessel}" if praefix else schluessel
            ergebnis.update(_flach(wert, neu))
    else:
        ergebnis[praefix] = daten
    return ergebnis


def _locale(sprache: str) -> dict[str, object]:
    pfad = ROOT / "locales" / f"{sprache}.json"
    return _flach(json.loads(pfad.read_text(encoding="utf-8")))


def test_sprachdateien_haben_identische_schluessel():
    deutsch = set(_locale("de"))
    for sprache in ("en", "fr"):
        assert set(_locale(sprache)) == deutsch, sprache


DEUTSCHE_WOERTER = re.compile(
    r"\b(Neustart|erforderlich|Anmelden|Starten|Verwalten|Abschliessen|Ergebnis|"
    r"Datenordner|Favorit|Aktionen|Gesamtbetrag|dunkel|hell|Kopie|duplizieren|"
    r"importieren|exportieren|Massenbearbeitung|erfassen|Beschreibung|Restbetrag|"
    r"Synchronisiert|Versicherung|einblenden|eingeben|Deine|Zeichen)\b"
)


@pytest.mark.parametrize("sprache", ["en", "fr"])
def test_keine_deutschen_restuebersetzungen(sprache: str):
    """v3.0.5 lieferte 89 unuebersetzte Strings in en.json und fr.json aus.

    Die Schluesselparitaet war dabei perfekt - genau deshalb schlug das
    bestehende i18n-Audit nicht an. Geprueft wird hier der Wert, nicht der
    Schluessel.
    """
    deutsch = _locale("de")
    fremd = _locale(sprache)
    reste = [
        schluessel
        for schluessel, wert in deutsch.items()
        if isinstance(wert, str)
        and fremd.get(schluessel) == wert
        and DEUTSCHE_WOERTER.search(wert)
    ]
    assert not reste, f"{sprache}: unuebersetzt {reste[:10]}"


# ── Befund 4: Undo-Pruning setzte auf undokumentiertes SQLite-Verhalten ─────
def _pruning_sql() -> str:
    """Holt die Pruning-Abfrage aus dem Modell statt sie zu duplizieren."""
    quelltext = (ROOT / "model" / "undo_redo_model.py").read_text(encoding="utf-8")
    baum = ast.parse(quelltext)
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
            continue
    treffer = [
        knoten
        for knoten in ast.walk(baum)
        if isinstance(knoten, ast.Call)
        and isinstance(knoten.func, ast.Attribute)
        and knoten.func.attr == "execute"
        and knoten.args
    ]
    for aufruf in treffer:
        text = _konstanter_string(aufruf.args[0])
        if text and "DELETE FROM undo_stack WHERE group_id NOT IN" in text:
            return text
    raise AssertionError("Pruning-Abfrage nicht gefunden")


def _konstanter_string(knoten: ast.AST) -> str | None:
    if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
        return knoten.value
    if isinstance(knoten, ast.BinOp) and isinstance(knoten.op, ast.Add):
        links = _konstanter_string(knoten.left)
        rechts = _konstanter_string(knoten.right)
        if links is not None and rechts is not None:
            return links + rechts
    if isinstance(knoten, ast.JoinedStr):
        return None
    return None


def test_pruning_sortiert_nicht_ueber_eine_nicht_ausgewaehlte_spalte():
    """SQLite verlangt bei DISTINCT, dass ORDER BY eine Ergebnisspalte nennt.

    Die alte Fassung sortierte ein ``SELECT DISTINCT group_id`` nach ``id``.
    Heutige Builds tolerieren das; garantiert ist es nicht. Ein Fehler waere vom
    umschliessenden except verschluckt worden - das Pruning haette still
    ausgesetzt und der undo_stack waere unbegrenzt gewachsen.
    """
    sql = _pruning_sql()
    assert "SELECT DISTINCT group_id FROM undo_stack" not in sql
    assert "MAX(id)" in sql
    assert "GROUP BY group_id" in sql


def test_pruning_behaelt_genau_die_juengsten_gruppen():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE undo_stack(id INTEGER PRIMARY KEY, group_id TEXT)")
    for gruppe in range(6):
        for _ in range(3):
            conn.execute("INSERT INTO undo_stack(group_id) VALUES(?)", (f"g{gruppe}",))
    conn.execute(_pruning_sql(), (2,))
    behalten = {zeile[0] for zeile in conn.execute("SELECT group_id FROM undo_stack")}
    assert behalten == {"g4", "g5"}
    assert conn.execute("SELECT COUNT(*) FROM undo_stack").fetchone()[0] == 6


def test_pruning_ist_bei_wenigen_gruppen_und_leerem_stack_stabil():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE undo_stack(id INTEGER PRIMARY KEY, group_id TEXT)")
    conn.execute(_pruning_sql(), (100,))
    assert conn.execute("SELECT COUNT(*) FROM undo_stack").fetchone()[0] == 0
    conn.execute("INSERT INTO undo_stack(group_id) VALUES('a')")
    conn.execute(_pruning_sql(), (100,))
    assert conn.execute("SELECT COUNT(*) FROM undo_stack").fetchone()[0] == 1


def test_pruning_fehler_wird_nicht_stillschweigend_verschluckt():
    """Ein Pruning-Fehler muss sichtbar sein, sonst waechst der Stack unbemerkt."""
    quelltext = (ROOT / "model" / "undo_redo_model.py").read_text(encoding="utf-8")
    assert 'logger.warning("undo_stack pruning fehlgeschlagen: %s", e)' in quelltext


# ── Befund 5: Ballast im Auslieferungsbaum ──────────────────────────────────
def test_kein_release_status_ordner_im_auslieferungsbaum():
    """.release-status enthielt Fehlschlagsmarken alter Versionen."""
    assert not (ROOT / ".release-status").exists()


def test_release_nachweise_sind_zusammengefasst():
    """Die 49 Einzelberichte der Reihen 2.1/2.2 liegen als eine Chronik vor."""
    archiv = ROOT / "docs" / "archive" / "release-evidence"
    chronik = archiv / "RELEASE_AUDIT_HISTORY_v2_1_7_bis_v2_2_60.md"
    assert chronik.is_file()
    berichte = sorted(p.name for p in archiv.glob("*.md"))
    assert berichte == [
        "KILLCRITIC_X10THINK_10000_v2_2_25.md",
        "README.md",
        "RELEASE_AUDIT_HISTORY_v2_1_7_bis_v2_2_60.md",
    ], berichte


def test_funktionsinventar_ist_versionslos_und_vorhanden():
    """Das Inventar wird fortgeschrieben statt je Version neu angelegt."""
    assert (ROOT / "docs" / "FEATURE_INVENTORY.md").is_file()
    veraltet = list((ROOT / "docs").glob("FEATURE_INVENTORY_v*.md"))
    assert not veraltet, veraltet


# ── Befund 6: Audit-Matrizen landeten im Wurzelverzeichnis ──────────────────
def test_alle_matrix_werkzeuge_schreiben_ins_beweisarchiv():
    """Ein voller Batteriedurchlauf machte den eigenen Baum rot.

    ``final_release_audit_1000`` schreibt seine Matrix seit v2.2.60 nach
    ``docs/archive/release-evidence``. ``killcritic_x10think_10000`` und
    ``enterprise_ui_adhs_audit_1000`` zogen nicht nach und legten ihre CSV im
    Projekt-Hauptordner ab - genau dort, wo
    ``test_project_root_holds_no_release_evidence`` sie verbietet. Wer die
    Batterie vollstaendig fuhr, bekam danach einen roten Test, dessen Ursache
    der Testlauf selbst war.
    """
    werkzeuge = (
        "final_release_audit_1000.py",
        "killcritic_x10think_10000.py",
        "enterprise_ui_adhs_audit_1000.py",
    )
    for name in werkzeuge:
        quelltext = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "release-evidence" in quelltext, name
        assert 'ROOT / (\n        "UI_USABILITY' not in quelltext, name
        assert "CSV_PATH = ROOT / (" not in quelltext, name

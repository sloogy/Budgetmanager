"""Dem Hell/Dunkel-Wechsel des Betriebssystems folgen.

Warum es diesen Test gibt: Die Wahl "Wie das System" greift an drei Stellen
ineinander - die Abfrage bei Qt, die Aufloesung in `_current_mode`, und das
Speichern der Wahl als "system" statt als aufgeloester Modus. Faellt die dritte
aus, steht nach dem naechsten Start wieder "Hell" im Dropdown, ohne dass jemand
einen Fehler sieht.

Die Gegenstuecke in FPM, Kontaktmanager und LifePlanner heissen genauso.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import theme_manager as tm

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_DIALOG = ROOT / "settings_dialog.py"


class _Settings(dict):
    """Settings-Ersatz: ThemeManager braucht davon nur `.get`."""


@pytest.fixture()
def manager(tmp_path, monkeypatch):
    """ThemeManager mit eigenem Datenordner - keine Spuren im echten Profil."""
    monkeypatch.setattr("model.app_paths.data_dir", lambda: tmp_path)
    return tm.ThemeManager(_Settings())


# ── Abfrage beim Betriebssystem ─────────────────────────────────────────────

def test_ohne_qt_anwendung_meldet_das_system_nichts():
    """Ohne laufende QApplication gibt es keine Auskunft - und keinen Absturz."""
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        assert tm.system_mode() is None
    else:
        assert tm.system_mode() in (None, "hell", "dunkel")


# ── Aufloesung im ThemeManager ──────────────────────────────────────────────

def test_system_folgt_dem_dunklen_betriebssystem(manager, monkeypatch):
    manager.settings["theme"] = "system"
    monkeypatch.setattr(tm, "system_mode", lambda: "dunkel")
    assert manager._current_mode() == "dunkel"


def test_system_folgt_dem_hellen_betriebssystem(manager, monkeypatch):
    manager.settings["theme"] = "system"
    monkeypatch.setattr(tm, "system_mode", lambda: "hell")
    assert manager._current_mode() == "hell"


def test_ohne_auskunft_bleibt_es_hell(manager, monkeypatch):
    """Der Zustand, den BudgetManager immer schon hatte - kein Blindflug."""
    manager.settings["theme"] = "system"
    monkeypatch.setattr(tm, "system_mode", lambda: None)
    assert manager._current_mode() == "hell"


def test_auto_gilt_als_gleichbedeutend(manager, monkeypatch):
    manager.settings["theme"] = "auto"
    monkeypatch.setattr(tm, "system_mode", lambda: "dunkel")
    assert manager._current_mode() == "dunkel"


@pytest.mark.parametrize(
    "gespeichert,erwartet",
    [("light", "hell"), ("dark", "dunkel"), ("dunkel", "dunkel"), ("", "hell")],
)
def test_die_ausdrueckliche_wahl_bleibt_unberuehrt(
    manager, monkeypatch, gespeichert, erwartet
):
    """Ein Systemwechsel darf nicht gegen eine getroffene Wahl ziehen."""
    manager.settings["theme"] = gespeichert
    monkeypatch.setattr(tm, "system_mode", lambda: "dunkel")
    assert manager._current_mode() == erwartet


# ── Die Wahl muss als "system" gespeichert werden ───────────────────────────

def _method(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} nicht gefunden")


def test_gespeichert_wird_die_wahl_nicht_der_aufgeloeste_modus():
    """Aus "dunkel" liesse sich nicht zurueckgewinnen, ob das System gemeint war."""
    source = SETTINGS_DIALOG.read_text(encoding="utf-8")
    tree = ast.parse(source)

    wert = _method(tree, "SettingsDialog", "_theme_setting_value")
    assert "system" in (ast.get_source_segment(source, wert) or "")

    persist = _method(tree, "SettingsDialog", "_persist_design_selection")
    aufrufe = {
        node.func.attr
        for node in ast.walk(persist)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_theme_setting_value" in aufrufe, (
        "_persist_design_selection leitet den Wert wieder aus dem Modus ab"
    )


def test_das_dropdown_hat_die_dritte_wahl():
    source = SETTINGS_DIALOG.read_text(encoding="utf-8")
    assert 'tr("settings.theme_system")' in source
    assert 'tr("settings.theme_system_hint")' in source, (
        "Der uebersetzte Hinweis wird nirgends angezeigt"
    )


# ── Uebersetzungen ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("sprache", ["de", "en", "fr"])
def test_die_dritte_wahl_ist_uebersetzt(sprache):
    daten = json.loads((ROOT / "locales" / f"{sprache}.json").read_text(encoding="utf-8"))
    eintraege = daten.get("settings", {})
    for schluessel in ("theme_system", "theme_system_hint"):
        assert eintraege.get(schluessel), f"{sprache}: {schluessel} fehlt"

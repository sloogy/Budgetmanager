"""Die Bruecke zu FPM zieht von selbst nach.

Warum es das braucht: Bis hierher schrieb BudgetManager seine Outboxen nur,
wenn jemand im LifePlanner-Dialog ausdruecklich darauf drueckte. Wer ein
Sparziel anlegte und den Dialog nie oeffnete, dessen Ziel erreichte FPM nie -
ohne Fehlermeldung, die Anzeige blieb einfach leer. FPM haelt seine Seite
umgekehrt seit jeher nach jeder Aenderung aktuell.

Geprueft wird hier die Verdrahtung, nicht der Export selbst - der steht in
test_fpm_bridge_contract.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "views" / "main_window.py"


@pytest.fixture(scope="module")
def quelle() -> str:
    return MAIN_WINDOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def baum(quelle: str) -> ast.AST:
    return ast.parse(quelle)


def _methode(baum: ast.AST, name: str) -> ast.FunctionDef:
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.ClassDef):
            for eintrag in knoten.body:
                if isinstance(eintrag, ast.FunctionDef) and eintrag.name == name:
                    return eintrag
    raise AssertionError(f"{name} nicht gefunden")


def _ruft(methode: ast.FunctionDef, name: str) -> bool:
    for knoten in ast.walk(methode):
        if isinstance(knoten, ast.Call):
            ziel = knoten.func
            if isinstance(ziel, ast.Attribute) and ziel.attr == name:
                return True
            if isinstance(ziel, ast.Name) and ziel.id == name:
                return True
        # QTimer.singleShot(..., self._sync_bridge_outboxes_safely)
        if isinstance(knoten, ast.Attribute) and knoten.attr == name:
            return True
    return False


# ── Die drei Ausloeser ──────────────────────────────────────────────────────

def test_ein_voll_refresh_zieht_die_bruecke_nach(baum):
    """Ein Voll-Refresh folgt auf eine Datenaenderung - genau dann.

    Das ist der Ausloeser, der den Alltagsfall abdeckt: Sparziel anlegen,
    weiterarbeiten, FPM zeigt es kurz darauf.
    """
    assert _ruft(_methode(baum, "_refresh_all_tabs"), "_schedule_bridge_outbox_sync")


def test_beim_schliessen_wird_der_letzte_stand_geschrieben(baum):
    """Wer ein Ziel anlegt und gleich schliesst, wartet sonst bis zum
    naechsten Start - der traege Zeitgeber kaeme nicht mehr zum Zug."""
    assert _ruft(_methode(baum, "closeEvent"), "_sync_bridge_outboxes_safely")


def test_beim_start_wird_einmal_geschrieben(quelle):
    """Faengt den Lauf ab, der ohne sauberes Beenden endete."""
    assert "QTimer.singleShot(1500, self._sync_bridge_outboxes_safely)" in quelle


# ── Der Abgleich darf die Buchhaltung nie stoeren ───────────────────────────

def test_der_abgleich_faengt_seine_fehler_selbst(baum):
    """Die Bruecke ist eine Spiegelung. Ein getrenntes Netzlaufwerk oder ein
    falsch gesetztes LIFEPLANNER_BRIDGE_DIR darf nicht vor dem Nutzer landen -
    beim Schliessen wuerde das sogar das Schliessen verhindern."""
    methode = _methode(baum, "_sync_bridge_outboxes_safely")
    handler = [k for k in ast.walk(methode) if isinstance(k, ast.ExceptHandler)]
    assert handler, "kein except - ein Bridge-Fehler schlaegt bis in die UI durch"

    gefangen = set()
    for h in handler:
        if h.type is None:
            gefangen.add("bare")
        elif isinstance(h.type, ast.Name):
            gefangen.add(h.type.id)
    assert "Exception" in gefangen or "bare" in gefangen

    # Und er darf nicht spurlos verschwinden.
    assert _ruft(methode, "warning"), "der Fehler gehoert ins Log"


def test_der_zeitgeber_buendelt_mehrere_aenderungen(baum):
    """Beide Exporte lesen die vollstaendigen Tabellen. Zehn Aenderungen kurz
    hintereinander sollen einen Lauf ergeben, nicht zehn."""
    methode = _methode(baum, "_schedule_bridge_outbox_sync")
    quelltext = ast.unparse(methode)
    assert "_bridge_sync_pending" in quelltext
    assert "singleShot" in quelltext


# ── Der Export selbst bleibt erreichbar ─────────────────────────────────────

def test_beide_richtungen_werden_geschrieben():
    """sync_default_outboxes deckt Ausgabenvorschlaege *und* Sparziele ab.
    Faellt eine der beiden weg, fehlt in FPM die halbe Bruecke."""
    from model.lifeplanner_import_service import sync_default_outboxes

    quelle = ast.unparse(
        ast.parse(
            (ROOT / "model" / "lifeplanner_import_service.py").read_text(
                encoding="utf-8"
            )
        )
    )
    assert "def sync_default_outboxes" in quelle
    assert sync_default_outboxes is not None
    for name in ("export_fpm_expense_proposals", "export_savings_goals"):
        assert name in quelle

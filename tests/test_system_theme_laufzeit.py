"""Der Systemwechsel greift sofort, nicht erst beim nächsten Start.

Loop 1 brachte die Einstellung "dem System folgen" in alle vier Programme.
Die Verbindung zum Signal, das Qt beim Umschalten des Betriebssystems sendet,
hatten aber nur drei — FPM, FreizeitManager und LifePlanner. Im BudgetManager
griff die Einstellung erst beim nächsten Start, und genau dann hilft sie
niemandem.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUELLE = ROOT / "views" / "main_window.py"


def _methoden() -> set[str]:
    baum = ast.parse(QUELLE.read_text(encoding="utf-8"))
    return {
        k.name
        for klasse in ast.walk(baum)
        if isinstance(klasse, ast.ClassDef)
        for k in klasse.body
        if isinstance(k, ast.FunctionDef)
    }


def test_das_fenster_hoert_auf_den_systemwechsel() -> None:
    assert "_watch_system_color_scheme" in _methoden()
    assert "_system_color_scheme_changed" in _methoden()


def test_die_verbindung_wird_beim_aufbau_hergestellt() -> None:
    """Eine Methode, die niemand ruft, ist keine Verbindung."""
    text = QUELLE.read_text(encoding="utf-8")
    assert text.count("self._watch_system_color_scheme()") >= 1


def test_es_wird_auf_das_richtige_signal_gehoert() -> None:
    text = QUELLE.read_text(encoding="utf-8")
    assert "colorSchemeChanged" in text


def test_qt_vor_6_5_wird_abgefangen() -> None:
    """Das Signal gibt es erst seit Qt 6.5.

    Ohne die Prüfung stürzt der Aufbau auf älteren Qt-Fassungen ab — und
    zwar beim Start, nicht irgendwo im Hintergrund.
    """
    text = QUELLE.read_text(encoding="utf-8")
    # Die Definition, nicht die Aufrufstelle weiter oben.
    stelle = text.index("def _watch_system_color_scheme")
    abschnitt = text[stelle : stelle + 1200]
    assert "getattr(" in abschnitt
    assert "is None" in abschnitt


def test_nur_wer_dem_system_folgt_wird_umgestellt() -> None:
    """Wer Hell oder Dunkel fest gewählt hat, will nicht umgestellt werden.

    Ohne diese Prüfung würde ein Systemwechsel die feste Wahl überschreiben —
    das wäre schlimmer als gar keine Reaktion.
    """
    text = QUELLE.read_text(encoding="utf-8")
    stelle = text.index("def _system_color_scheme_changed")
    abschnitt = text[stelle : stelle + 800]
    assert '"system"' in abschnitt
    assert "return" in abschnitt

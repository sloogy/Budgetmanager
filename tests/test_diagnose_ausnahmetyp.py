"""Ein Diagnosebericht muss den Fehler benennen, ohne die Daten zu nennen.

Aus einem eingesandten Bericht (2.2.71, Windows 11) liess sich nichts
schliessen: Das App-Log war Zeile fuer Zeile geschwaerzt, und die
Schlusszeile jedes Tracebacks - die einzige, die sagt, *was* schiefging -
gleich mit. Ein KeyError war von einem Datenbankfehler nicht zu
unterscheiden.

Der Ausnahmetyp ist ein Klassenname aus dem Programmcode und nennt keine
Kategorien, Betraege oder Kommentare. Er bleibt jetzt stehen, sein Text
nicht.
"""

from __future__ import annotations

from model.diagnostics import _sanitize_application_log


def test_der_ausnahmetyp_bleibt_der_text_verschwindet():
    log = "KeyError: 'Miete'\n"
    assert _sanitize_application_log(log) == "KeyError: <redacted>\n"


def test_auch_ein_qualifizierter_typ_bleibt():
    log = "sqlite3.OperationalError: no such table: buchungen_2026\n"
    assert _sanitize_application_log(log) == "sqlite3.OperationalError: <redacted>\n"


def test_eine_freie_meldung_bleibt_geschwaerzt():
    """Sonst waere die Regel eine Hintertuer fuer beliebigen Text."""
    log = "Miete: 1450.00 CHF gebucht\n"
    assert _sanitize_application_log(log) == "<redacted>\n"


def test_ein_wert_mit_doppelpunkt_wird_nicht_zum_typ():
    """'Coop Pronto: 12.40' sieht einer Ausnahmezeile aehnlich genug."""
    log = "Coop Pronto: 12.40\n"
    assert _sanitize_application_log(log) == "<redacted>\n"


def test_die_logzeile_selbst_bleibt_geschwaerzt():
    log = "2026-08-22 18:27:37 [ERROR   ] model.database: Kategorie Miete fehlt\n"
    assert (
        _sanitize_application_log(log)
        == "2026-08-22 18:27:37 [ERROR   ] model.database: <message redacted>\n"
    )


def test_der_traceback_rahmen_bleibt_lesbar():
    log = (
        "Traceback (most recent call last):\n"
        '  File "model/tracking_model.py", line 412, in save\n'
        "ValueError: Betrag 1450.00 ist ungueltig\n"
    )
    assert _sanitize_application_log(log) == (
        "Traceback (most recent call last):\n"
        '  File "model/tracking_model.py", line 412, in save\n'
        "ValueError: <redacted>\n"
    )

"""Rechnen im Betragsfeld.

(Zielbild des Nutzers: "Budgettool soll SAP-aehnlich einen Rechner
erhalten.") In SAP nimmt ein Betragsfeld nicht nur eine Zahl, sondern auch
eine Rechnung: ``23,40 + 12,60``. Wer eine Quittung mit drei Posten bucht,
tippt sie ab, statt vorher im Kopf zu addieren.

Der wichtigere Teil dieser Tests ist der zweite: **was der Rechner ablehnt.**
Ein Betragsfeld ist eine Stelle, an der Text von aussen hereinkommt - aus
einer Zwischenablage, aus einem Kontoauszug. Mit ``eval`` waere
``__import__("os").system(...)`` eine gueltige Eingabe.
"""

from __future__ import annotations

import pytest

from utils.rechner import (
    HOECHSTLAENGE,
    RechenFehler,
    ist_rechnung,
    rechne,
    rechne_oder_lies,
)


@pytest.fixture(autouse=True)
def deutsches_format(monkeypatch):
    """Komma als Dezimalzeichen - der Fall, in dem es knifflig wird."""
    import utils.money as money

    monkeypatch.setattr(money, "get_decimal_separator", lambda: ",")
    import utils.rechner as rechner

    monkeypatch.setattr(rechner, "get_decimal_separator", lambda: ",")


# ── Rechnen ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ausdruck,erwartet",
    [
        ("23,40 + 12,60", 36.0),
        ("100 - 20 - 5", 75.0),
        ("10*3", 30.0),
        ("(5+5)/2", 5.0),
        ("2 * (3 + 4,5)", 15.0),
        ("-15,50", -15.5),
        ("1.234,56 + 1", 1235.56),
    ],
)
def test_rechnungen_werden_ausgewertet(ausdruck, erwartet) -> None:
    assert rechne(ausdruck) == pytest.approx(erwartet)


def test_tausendertrennung_wird_nicht_zum_dezimalzeichen() -> None:
    """Die Tuecke des deutschen Formats.

    In Python ist der Punkt das Dezimalzeichen und ein Komma macht aus zwei
    Zahlen ein Tupel. Wer den Ausdruck ungewandelt an den Parser gaebe,
    bekaeme aus "1.234,56" eine 1.234 und eine 56.
    """
    assert rechne("1.234,56 * 2") == pytest.approx(2469.12)


def test_eine_blosse_zahl_ist_keine_rechnung() -> None:
    """Sonst liefe "1.234,56" durch den Rechner statt durch parse_money."""
    assert not ist_rechnung("1.234,56")
    assert not ist_rechnung("-15,50")
    assert ist_rechnung("1+1")


def test_rechne_oder_lies_nimmt_beides() -> None:
    assert rechne_oder_lies("12,50") == pytest.approx(12.5)
    assert rechne_oder_lies("12,50 + 3") == pytest.approx(15.5)


def test_leeres_feld_je_nach_ort() -> None:
    """In einer Tabellenzelle heisst leer "null", in einem Dialog "nichts"."""
    assert rechne_oder_lies("", empty_is_zero=True) == 0.0
    with pytest.raises(ValueError):
        rechne_oder_lies("", empty_is_zero=False)


# ── Was abgelehnt wird ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "angriff",
    [
        '__import__("os").system("id")',
        'open("/etc/passwd").read()',
        "().__class__.__bases__",
        "[1,2,3]",
        "lambda: 1",
        "print(1)",
        "1 if True else 2",
    ],
)
def test_kein_python_wird_ausgefuehrt(angriff) -> None:
    """Der Kern: Die erlaubte Liste ist die Erlaubnis, nicht eine Sammlung
    von Verboten, die jemand vergessen kann."""
    with pytest.raises(RechenFehler):
        rechne(angriff)


def test_potenzieren_ist_nicht_erlaubt() -> None:
    """``2**10000000`` haelt das Programm minutenlang an.

    In einem Betragsfeld hat das nichts zu suchen - und ein Programm, das
    beim Tippen einfriert, sieht aus wie ein Absturz.
    """
    with pytest.raises(RechenFehler):
        rechne("2**10")


def test_teilen_durch_null_meldet_sich() -> None:
    with pytest.raises(RechenFehler, match="null"):
        rechne("10/0")


def test_zu_langer_ausdruck_wird_abgelehnt() -> None:
    """Laenger als eine Quittung ist keine Eingabe mehr."""
    with pytest.raises(RechenFehler):
        rechne("1+" * HOECHSTLAENGE + "1")


def test_unfug_wird_nicht_zu_null() -> None:
    """Ein Betragsfeld, das aus Unverstandenem eine Null macht, bucht falsch."""
    for text in ("abc", "12,, 5", "+*3", "(1+2"):
        with pytest.raises(ValueError):
            rechne_oder_lies(text)


def test_unendlich_wird_abgelehnt() -> None:
    with pytest.raises(RechenFehler):
        rechne("9" * 20 + "e300 * 9" + "9" * 10)


# ── Anbindung an die Dialoge ──────────────────────────────────────────────


def test_der_budgetdialog_rechnet(monkeypatch) -> None:
    """parse_amount ist der zentrale Weg der Dialoge."""
    import utils.rechner as rechner
    from views.budget_entry_dialog_extended import parse_amount

    monkeypatch.setattr(rechner, "get_decimal_separator", lambda: ",")
    assert parse_amount("23,40 + 12,60") == pytest.approx(36.0)
    assert parse_amount("50") == pytest.approx(50.0)

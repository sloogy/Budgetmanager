"""Rechnen im Betragsfeld.

In SAP kann man in ein Betragsfeld nicht nur eine Zahl schreiben, sondern
auch eine Rechnung: ``23,40 + 12,60``. Wer eine Quittung mit drei Posten
bucht, tippt sie ab, statt vorher im Kopf zu addieren - und sieht dabei noch,
woraus die Summe entstanden ist.

Genau das leistet dieses Modul: Es nimmt einen Ausdruck in der Zahlenschreibweise
des Nutzers und gibt das Ergebnis zurueck.

**Ohne ``eval``.** Ein Betragsfeld ist eine Stelle, an der Text von aussen
hereinkommt - aus einer Zwischenablage, aus einem Kontoauszug, aus einer
E-Mail. ``eval`` wuerde dort beliebigen Python-Code ausfuehren:
``__import__("os").system(...)`` ist ein gueltiger Ausdruck. Stattdessen wird
der Syntaxbaum gelesen und nur zugelassen, was hier ausdruecklich steht:
vier Grundrechenarten, Klammern, Vorzeichen, Zahlen.

Was nicht erlaubt ist, wird abgelehnt - nicht stillschweigend ignoriert. Ein
Betragsfeld, das aus etwas Unverstandenem eine Null macht, bucht falsch.
"""

from __future__ import annotations

import ast
import operator
import re

from utils.money import get_decimal_separator, parse_money

# Genau die vier Grundrechenarten. Kein Potenzieren: ``2**10000000`` haelt das
# Programm minutenlang an, und in einem Betragsfeld hat es nichts zu suchen.
_OPERATOREN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_VORZEICHEN = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# Ein Ausdruck, der nur aus Zahlen und diesen Zeichen besteht. Die Pruefung
# davor spart den Syntaxbaum fuer den haeufigsten Fall - eine blosse Zahl.
_ERLAUBTE_ZEICHEN = re.compile(r"^[0-9\s.,+\-*/()']+$")

# Genug fuer jede Quittung. Ein laengerer Ausdruck ist keine Eingabe mehr,
# sondern etwas, das jemand hineingeschoben hat.
HOECHSTLAENGE = 200


class RechenFehler(ValueError):
    """Der Ausdruck laesst sich nicht als Rechnung lesen."""


def ist_rechnung(text: str) -> bool:
    """Enthaelt der Text einen Rechenoperator?

    Eine blosse Zahl ist keine Rechnung - "1.234,56" soll nicht durch den
    Rechner laufen, sondern durch ``parse_money``, das die
    Tausendertrennung kennt.
    """
    ohne_vorzeichen = text.strip().lstrip("+-")
    return any(zeichen in ohne_vorzeichen for zeichen in "+-*/")


def _zahlen_normalisieren(text: str) -> str:
    """Uebersetzt die Zahlenschreibweise des Nutzers nach Python.

    Hier liegt die Tuecke: Im deutschen Format ist das Komma das
    Dezimalzeichen und der Punkt der Tausendertrenner - in Python ist es
    umgekehrt, und ein Komma macht aus zwei Zahlen ein Tupel.
    """

    def ersetze(treffer: re.Match[str]) -> str:
        return str(parse_money(treffer.group(0), empty_is_zero=False))

    # Kein Ternary: die beiden Muster stehen so untereinander und sind
    # vergleichbar - das eine hat den Punkt innen, das andere das Komma.
    if get_decimal_separator() == ",":  # noqa: SIM108
        muster = r"\d[\d.',   ]*\d|\d"
    else:
        muster = r"\d[\d,'   .]*\d|\d"
    return re.sub(muster, ersetze, text)


def _auswerten(knoten: ast.AST) -> float:
    if isinstance(knoten, ast.Expression):
        return _auswerten(knoten.body)
    if isinstance(knoten, ast.Constant):
        if isinstance(knoten.value, bool) or not isinstance(knoten.value, (int, float)):
            raise RechenFehler(f"kein Zahlenwert: {knoten.value!r}")
        return float(knoten.value)
    if isinstance(knoten, ast.BinOp) and type(knoten.op) in _OPERATOREN:
        links = _auswerten(knoten.left)
        rechts = _auswerten(knoten.right)
        if isinstance(knoten.op, ast.Div) and rechts == 0:
            raise RechenFehler("Teilen durch null")
        return _OPERATOREN[type(knoten.op)](links, rechts)
    if isinstance(knoten, ast.UnaryOp) and type(knoten.op) in _VORZEICHEN:
        return _VORZEICHEN[type(knoten.op)](_auswerten(knoten.operand))
    # Alles andere - Namen, Aufrufe, Attribute, Vergleiche - faellt hier
    # durch. Das ist der Punkt: Die Liste oben ist die Erlaubnis, nicht
    # eine Sammlung von Verboten, die jemand vergessen kann.
    raise RechenFehler(f"nicht erlaubt: {type(knoten).__name__}")


def rechne(text: str) -> float:
    """Wertet einen Betragsausdruck aus.

    Wirft ``RechenFehler``, wenn der Text keine Rechnung im erlaubten Sinn
    ist. Der Aufrufer entscheidet, was er damit tut - stehen lassen und
    melden ist meist richtiger, als eine Null einzutragen.
    """
    roh = (text or "").strip()
    if not roh:
        raise RechenFehler("leerer Ausdruck")
    if len(roh) > HOECHSTLAENGE:
        raise RechenFehler(f"laenger als {HOECHSTLAENGE} Zeichen")
    if not _ERLAUBTE_ZEICHEN.match(roh):
        raise RechenFehler("enthaelt Zeichen, die keine Rechnung sein koennen")

    vorbereitet = _zahlen_normalisieren(roh)
    try:
        baum = ast.parse(vorbereitet, mode="eval")
    except SyntaxError as fehler:
        raise RechenFehler(f"keine gueltige Rechnung: {fehler.msg}") from fehler

    ergebnis = _auswerten(baum)
    if ergebnis != ergebnis or ergebnis in (float("inf"), float("-inf")):
        # NaN oder unendlich - etwa aus 1e308*10. Als Betrag ist beides
        # unbrauchbar, und stillschweigend gerundet waere es schlimmer.
        raise RechenFehler("Ergebnis ist keine brauchbare Zahl")
    return float(ergebnis)


def rechne_oder_lies(text: str, *, empty_is_zero: bool = False) -> float:
    """Wertet aus, wenn es eine Rechnung ist - sonst liest es die Zahl.

    Der Weg, den ein Betragsfeld nimmt: "12,50" geht an ``parse_money``,
    das die Tausendertrennung des Formats kennt; "12,50+3" an den Rechner.

    ``empty_is_zero`` reicht die Entscheidung von ``parse_money`` durch: In
    einer Tabellenzelle heisst leer "null", in einem Dialogfeld "nichts
    eingegeben" - und das ist ein Unterschied.
    """
    if ist_rechnung(text):
        return rechne(text)
    return parse_money(text, empty_is_zero=empty_is_zero)

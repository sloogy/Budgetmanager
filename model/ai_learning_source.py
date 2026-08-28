"""Herkunft und Gewicht eines Lernsignals der Import-KI.

Bis P2.2 kannte der Lernspeicher nur *dass* etwas gelernt wurde, nicht
*woher* es kam. Damit war jede importierte Zeile gleich viel wert - auch
die, bei der die KI selbst geraten und niemand widersprochen hatte. Das
erzeugt genau den Kreislauf, den P2.3 aufbrechen soll::

    KI raet falsch -> Nutzer korrigiert nicht -> Import
    -> KI behandelt eigenen Rat als starke Wahrheit -> wird immer sicherer falsch

Dieses Modul beantwortet die drei Fragen, die dafuer noetig sind:

* Welche Herkunftsarten gibt es?
* Welche schlaegt welche?
* Was macht eine Vorhersagemethode aus der Pruefliste zu einer Lernquelle?

**Warum das ein eigenes Modul ist.** ``model/ai_learning_store.py`` weiss,
*welche Tabellen* zum Lernspeicher gehoeren; das ist eine andere Frage.
Die Herkunft brauchen dagegen drei Stellen mit unterschiedlichen
Abhaengigkeiten: ``bank_import_ai.py`` (Haendlergedaechtnis),
``twint_import_policy.py`` (TWINT-Gedaechtnis) und der Importdialog. Eine
davon zur Heimat der Regel zu machen, haette die beiden anderen an sie
gebunden. Dieses Modul importiert darum nichts aus dem Projekt.

**Was die Gewichtung *nicht* tut.** Sie entscheidet nie, was gebucht wird.
Der Anwender sieht in der Pruefliste, was er importiert, und genau das wird
gebucht. Die Gewichtung entscheidet ausschliesslich, was die KI daraus
*lernt* - ob ein Signal das Haendlergedaechtnis umschreiben darf und ob es
den Zaehler erhoeht, aus dem spaeter die Zuversicht wird.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

#: Eine nachtraegliche Korrektur an einer bereits gebuchten Zeile. Das
#: staerkste Signal ueberhaupt: Der Anwender ist zurueckgegangen und hat
#: eine Entscheidung ausdruecklich zurueckgenommen. Geschrieben wird diese
#: Quelle erst von P2.4; die Ordnung steht hier bereits, damit P2.4 nur noch
#: den Schreibweg dazulegen muss.
SOURCE_TRACKING_CORRECTION = "tracking_correction"

#: Eine einzeln von Hand gesetzte Kategorie in der Pruefliste.
SOURCE_MANUAL = "manual"

#: Eine Sammelzuweisung ueber mehrere angehakte Zeilen. Ebenfalls Handarbeit,
#: aber groeber: Sie trifft viele Buchungstexte mit einer Geste.
SOURCE_MANUAL_BULK = "manual_bulk"

#: Die KI hat verallgemeinert - aus aehnlichen Buchungen oder ueber die
#: Wortstatistik - und der Anwender hat den Vorschlag stehen lassen. Ein
#: schwaches, aber echtes Signal: Der Fingerprint war der KI vorher nicht
#: bekannt, die Zuordnung ist also neue Information.
SOURCE_AI_CONFIRMED = "ai_confirmed"

#: Die automatische Eigenbestaetigung. Die KI hat wiederholt, was sie ohnehin
#: schon wusste (Haendler- oder TWINT-Gedaechtnis), und die Zeile lief
#: unveraendert durch den Import. Darin steckt keine neue Information -
#: nur die KI, die sich selbst zuhoert. Das ist die schwaechste Stufe und die
#: einzige, die den Zaehler nicht erhoeht.
SOURCE_IMPORT_CONFIRMED = "import_confirmed"

#: Die Rangfolge aus der Aufgabenstellung, in Zahlen::
#:
#:     tracking_correction > manual > manual_bulk > ai_confirmed
#:                                                > automatische Eigenbestaetigung
#:
#: Die Abstaende sind absichtlich gross. Eine spaetere Quelle laesst sich so
#: dazwischenschieben, ohne jede bereits gespeicherte Zeile umzuschreiben -
#: in der Datenbank steht der Name, nicht die Zahl.
SOURCE_WEIGHTS: Mapping[str, int] = MappingProxyType(
    {
        SOURCE_TRACKING_CORRECTION: 50,
        SOURCE_MANUAL: 40,
        SOURCE_MANUAL_BULK: 30,
        SOURCE_AI_CONFIRMED: 20,
        SOURCE_IMPORT_CONFIRMED: 10,
    }
)

#: Alle gueltigen Herkunftsnamen - fuer Pruefungen und Migrationen.
KNOWN_SOURCES: frozenset[str] = frozenset(SOURCE_WEIGHTS)

#: Obergrenze der Zuversicht je Herkunft.
#:
#: Ohne sie waere die Rangfolge folgenlos: Ein Eintrag, der nur aus
#: Eigenbestaetigung besteht, haette dieselbe Zuversicht erreichen koennen wie
#: einer, den der Anwender selbst gesetzt hat. Der Deckel ist die Stelle, an
#: der aus "woher" ein spuerbarer Unterschied wird.
#:
#: ``import_confirmed`` liegt bewusst auf dem Startwert der Formel in
#: :func:`model.bank_import_ai.predict_from_knowledge` (0.90). Reine
#: Eigenbestaetigung bewegt die Zuversicht damit ueberhaupt nicht mehr -
#: weder ueber den Zaehler noch ueber den Deckel.
SOURCE_CONFIDENCE_CAP: Mapping[str, float] = MappingProxyType(
    {
        SOURCE_TRACKING_CORRECTION: 0.995,
        SOURCE_MANUAL: 0.995,
        SOURCE_MANUAL_BULK: 0.98,
        SOURCE_AI_CONFIRMED: 0.93,
        SOURCE_IMPORT_CONFIRMED: 0.90,
    }
)

#: Was eine Vorhersagemethode der Pruefliste ueber die Herkunft aussagt.
#:
#: ``ReviewState.prediction_method`` haelt fest, wie eine Zeile zu ihrer
#: Kategorie gekommen ist. Genau daraus - und aus nichts sonst - ergibt sich
#: die Lernquelle; der Dialog erfindet sie nicht.
#:
#: Der entscheidende Schnitt liegt zwischen ``similar_merchant``/``naive_bayes``
#: und ``merchant_memory``/``twint_memory``: Die ersten beiden verallgemeinern
#: auf einen Fingerprint, den das Gedaechtnis noch nicht kennt - stehen zu
#: lassen ist dort eine Aussage. Die letzten beiden geben zurueck, was schon
#: gespeichert ist; sie erneut zu lernen fuegt nichts hinzu.
_METHOD_SOURCES: Mapping[str, str] = MappingProxyType(
    {
        "manual": SOURCE_MANUAL,
        "manual_bulk": SOURCE_MANUAL_BULK,
        "similar_merchant": SOURCE_AI_CONFIRMED,
        "naive_bayes": SOURCE_AI_CONFIRMED,
        "merchant_memory": SOURCE_IMPORT_CONFIRMED,
        "twint_memory": SOURCE_IMPORT_CONFIRMED,
        # Der Erstattungstreffer erbt die Kategorie der zugehoerigen Ausgabe.
        # Ueber den Buchungstext der *Gutschrift* sagt sie nichts aus - der
        # Fingerprint lautet "TWINT Gutschrift von ...", die Kategorie kommt
        # von woanders. Deshalb die schwaechste Stufe, unabhaengig davon, wie
        # gut die Ausgabe belegt war.
        "twint_match": SOURCE_IMPORT_CONFIRMED,
    }
)


def validate_source(value: str) -> str:
    """Prueft eine Herkunft auf dem Schreibweg.

    Streng, weil eine falsch geschriebene Herkunft in der Datenbank spaeter
    als "unbekannt" und damit als schwaechstes Signal gelesen wuerde - der
    Fehler waere ein stillschweigend entwertetes Lernsignal.
    """
    name = str(value or "").strip()
    if name not in SOURCE_WEIGHTS:
        raise ValueError(f"Unbekannte Lernquelle: {value!r}")
    return name


def source_weight(value: str) -> int:
    """Gewicht einer Herkunft auf dem Leseweg.

    Nachsichtig, weil hier auch Zeilen ankommen, die aelter sind als die
    Herkunftsfuehrung oder aus einer neueren Programmversion stammen. Ein
    unbekannter Name wiegt ``0`` und damit weniger als jede bekannte Quelle:
    Er darf nichts ueberschreiben, aber er blockiert auch nichts.
    """
    return int(SOURCE_WEIGHTS.get(str(value or "").strip(), 0))


def strongest_source(left: str, right: str) -> str:
    """Die staerkere zweier Herkuenfte; bei Gleichstand die erste."""
    return left if source_weight(left) >= source_weight(right) else right


def confirms(value: str) -> bool:
    """Erhoeht dieses Signal den Bestaetigungszaehler?

    Alles ausser der automatischen Eigenbestaetigung tut das. ``import_confirmed``
    ist die KI, die ihren eigenen Rat wiederholt gelesen hat; sie darf sich
    davon nicht sicherer werden.
    """
    return str(value or "").strip() != SOURCE_IMPORT_CONFIRMED


def confidence_cap(value: str) -> float:
    """Obergrenze der Zuversicht fuer Wissen dieser Herkunft."""
    return float(
        SOURCE_CONFIDENCE_CAP.get(
            str(value or "").strip(), SOURCE_CONFIDENCE_CAP[SOURCE_IMPORT_CONFIRMED]
        )
    )


def source_from_prediction_method(method: str) -> str:
    """Uebersetzt eine Vorhersagemethode der Pruefliste in eine Lernquelle.

    Unbekannte oder leere Methoden - etwa ``untrained``, ``no_categories`` oder
    ein Vermerk aus einer aelteren Programmversion - gelten als
    Eigenbestaetigung. Im Zweifel das schwaechste Gewicht: Eine zu schwach
    eingestufte Handarbeit kostet einen weiteren Bestaetigungsschritt, eine zu
    stark eingestufte Vermutung schreibt sich dagegen ins Gedaechtnis.
    """
    return _METHOD_SOURCES.get(str(method or "").strip(), SOURCE_IMPORT_CONFIRMED)


__all__ = [
    "KNOWN_SOURCES",
    "SOURCE_AI_CONFIRMED",
    "SOURCE_CONFIDENCE_CAP",
    "SOURCE_IMPORT_CONFIRMED",
    "SOURCE_MANUAL",
    "SOURCE_MANUAL_BULK",
    "SOURCE_TRACKING_CORRECTION",
    "SOURCE_WEIGHTS",
    "confidence_cap",
    "confirms",
    "source_from_prediction_method",
    "source_weight",
    "strongest_source",
    "validate_source",
]

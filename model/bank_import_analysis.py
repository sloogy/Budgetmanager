"""Die Bankimport-Analyse als reine Rechnung - ohne Oberflaeche, ohne Datenbank.

Bis hierher stand diese Rechnung verteilt im V4-Dialog: Datei lesen, Buchungen
erkennen, Duplikate abgleichen, TWINT-Erstattungen zuordnen, Kategorien
vorhersagen, Prueflistenzustand aufbauen. Sie lief damit im GUI-Thread, und bei
einem grossen Kontoauszug steht das Importfenster sichtbar still.

Dieses Modul enthaelt dieselbe Rechnung als freie Funktion :func:`analyse`.
Sie kennt kein Widget und keine ``sqlite3.Connection``; alles
Datenbankgebundene kommt als eingefrorener
:class:`~model.bank_import_snapshot.BankImportAnalysisSnapshot` herein, der auf
dem besitzenden Thread gezogen wurde. Damit ist sie in einem Worker-Thread
ausfuehrbar, ohne die Regel "keine Connection zwischen Threads" zu verletzen.

Fortschritt meldet sie ueber einen :class:`ProgressSink`. Die Vorgabe verwirft
alle Meldungen, ein Test kann sie mitschreiben, und der Qt-Worker uebersetzt
sie in Signale. Ein Sink kann ausserdem ``cancelled()`` bejahen; die Rechnung
prueft das an ihren Schleifengrenzen und bricht dann mit
:class:`AnalysisCancelled` ab, statt sich abschiessen zu lassen.

Die Rechnung selbst denkt in Phasen und meldet je Phase "Posten x von y".
Zwischen ihr und dem Aufrufer sitzt :class:`WeightedProgress`: Sie legt die
sieben Phasen aller Dateien zu **einem** Balken zusammen, gewichtet nach
Buchungszahl, und der gemeldete Prozentwert steigt monoton. Ohne diese Schicht
faengt jede Datei und jede Phase wieder bei null an.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from model.bank_import_ai import (
    BookingSignal,
    ReimbursementMatch,
    match_twint_reimbursement,
)
from model.bank_import_service import source_digest
from model.bank_import_snapshot import BankImportAnalysisSnapshot
from model.bank_statement_reader import (
    BankStatementError,
    BankTransaction,
    load_transactions,
)
from model.credit_card_statement_reader import is_credit_card_csv, load_credit_card_csv
from model.twint_import_policy import TYP_TWINT_AI, is_twint_credit
from model.typ_constants import TYP_EXPENSES, TYP_INCOME

# Formatnamen der Quellen. Sie stehen in der Quellenliste des Dialogs und in
# Tests; deshalb Konstanten statt wiederholter Zeichenketten.
FORMAT_BANK = "Bank-CSV/PDF"
FORMAT_CREDIT_CARD = "Kreditkarten-CSV"

# ── Phasen ───────────────────────────────────────────────────────────
# Bezeichner, keine Anzeigetexte: dieses Modul uebersetzt nicht. Wer die
# Phasen anzeigt, bildet sie auf i18n-Schluessel ab (siehe
# ``views/bank_import_analysis_worker.py``).
PHASE_READ = "read"
PHASE_PARSE = "parse"
PHASE_DUPLICATES = "duplicates"
PHASE_TWINT = "twint"
PHASE_CATEGORIZE = "categorize"
PHASE_TAGS = "tags"
PHASE_REVIEW = "review"

#: Die sieben Phasen in genau der Reihenfolge, in der sie ablaufen. Der
#: Gesamtfortschritt rechnet mit dieser Reihenfolge; wer sie aendert, aendert
#: auch die Reihenfolge der Balkenabschnitte.
ALL_PHASES = (
    PHASE_READ,
    PHASE_PARSE,
    PHASE_DUPLICATES,
    PHASE_TWINT,
    PHASE_CATEGORIZE,
    PHASE_TAGS,
    PHASE_REVIEW,
)

#: Phasen, die je Datei einmal ablaufen.
PER_FILE_PHASES = (PHASE_READ, PHASE_PARSE, PHASE_DUPLICATES)

#: Phasen, die einmal ueber alle Buchungen aller Quellen laufen.
GLOBAL_PHASES = (PHASE_TWINT, PHASE_CATEGORIZE, PHASE_TAGS, PHASE_REVIEW)

#: Aufwand einer Phase **je Buchung**, relativ zueinander gemessen. Die Zahlen
#: sind keine Sekunden, sondern Gewichte: Die Kategorisierung fragt fuer jede
#: Zeile die Vorhersage, das Uebernehmen der Tags ist ein Dictionary-Zugriff.
#: Sie entscheiden nur darueber, wie breit ein Phasenabschnitt im Balken ist.
PHASE_COST: Mapping[str, float] = {
    PHASE_READ: 0.5,
    PHASE_PARSE: 1.0,
    PHASE_DUPLICATES: 1.0,
    PHASE_TWINT: 2.0,
    PHASE_CATEGORIZE: 3.0,
    PHASE_TAGS: 0.2,
    PHASE_REVIEW: 0.2,
}

#: Grobe Umrechnung Dateigroesse -> Buchungszahl. Vor dem Lesen ist die
#: Buchungszahl einer Datei unbekannt; die Dateigroesse ist die einzige
#: belastbare Information, die vorher schon vorliegt. Sobald eine Datei
#: gelesen ist, tritt ihre echte Buchungszahl an die Stelle der Schaetzung.
BYTES_PER_BOOKING = 160.0

#: Schaetzung fuer eine Datei, deren Groesse sich nicht ermitteln laesst.
FALLBACK_BOOKINGS_PER_FILE = 100.0


class AnalysisCancelled(Exception):
    """Der Sink hat den Abbruch bejaht; die Rechnung endet ohne Ergebnis."""


class ProgressSink:
    """Nimmt Fortschritt entgegen. Diese Vorgabe verwirft ihn stillschweigend.

    Die Rechnung meldet drei Dinge: die aktuelle Phase, wie viele von wie
    vielen Einzelposten erledigt sind, und - wo es keine belastbare Restmenge
    gibt - einen unbestimmten Fortschritt (``percent(None)``). Erfundene
    Prozentzahlen entstehen hier nicht.
    """

    def phase(self, phase: str) -> None:
        """Eine neue Arbeitsphase beginnt."""

    def file(self, current: int, total: int) -> None:
        """Die Arbeit steckt gerade in Datei ``current`` von ``total``.

        In den Phasen, die je Datei ablaufen, ist das die gerade gelesene
        Datei. In den Phasen, die ueber alle Buchungen laufen, ist es die
        Quelle, aus der die gerade bearbeitete Buchung stammt - "Datei 3 von
        5" bleibt damit auch bei der Kategorisierung eine wahre Aussage.
        """

    def items(self, current: int, total: int) -> None:
        """``current`` von ``total`` Einzelposten der Phase sind erledigt."""

    def percent(self, value: int | None) -> None:
        """Prozentwert der Phase; ``None`` heisst unbestimmt."""

    def cancelled(self) -> bool:
        """True, sobald der Vorgang abgebrochen werden soll."""
        return False


@dataclass(frozen=True)
class _Cell:
    """Ein Abschnitt des Gesamtbalkens: eine Phase auf einer Arbeitsmenge."""

    phase: str
    #: Laufende Nummer der neuen Datei, oder ``-1`` fuer "alle Buchungen".
    file_index: int


class WeightedProgress(ProgressSink):
    """Rechnet Phasenfortschritt in einen globalen Gesamtfortschritt um.

    Ohne diese Schicht meldet jede Phase ihren eigenen Nullpunkt, und der
    Balken faellt an jeder Phasen- und Dateigrenze zurueck. Hier bekommt jede
    Phase jeder Datei einen eigenen Abschnitt des Balkens; die Breite eines
    Abschnitts ist ``PHASE_COST[phase] * Buchungen``.

    Die Buchungszahl einer noch ungelesenen Datei ist unbekannt. Geschaetzt
    wird sie aus der Dateigroesse; sobald die Datei gelesen ist, meldet der
    Duplikatabgleich die echte Zahl, und die Schaetzung wird ersetzt. Damit
    diese Korrektur den Balken nie zurueckwirft, ist der gemeldete Wert
    **monoton**: er wird gegen den zuletzt gemeldeten geklemmt. Eine zu kleine
    Schaetzung laesst den Balken also langsamer werden, aber nie springen.

    Erfunden wird dabei nichts (Regel 1.7): Der Wert ist der Anteil bereits
    erledigter Arbeit an der gesamten - nach der besten Schaetzung, die zu
    diesem Zeitpunkt vorliegt.
    """

    def __init__(
        self,
        inner: ProgressSink,
        *,
        known_bookings: int,
        estimates: Sequence[float],
        first_new_file: int = 0,
    ) -> None:
        self._inner = inner
        self._known = float(max(0, known_bookings))
        self._estimates = [max(1.0, float(value)) for value in estimates]
        self._first_new = int(first_new_file)
        self._cells: tuple[_Cell, ...] = tuple(
            [
                _Cell(phase, index)
                for index in range(len(self._estimates))
                for phase in PER_FILE_PHASES
            ]
            + [_Cell(phase, -1) for phase in GLOBAL_PHASES]
        )
        self._cursor = 0
        self._fraction = 0.0
        self._file_index = -1
        self._reported = 0

    # ── Gewichte ──────────────────────────────────────────────────

    def _budget(self, cell: _Cell) -> float:
        if cell.file_index < 0:
            return PHASE_COST[cell.phase] * (self._known + sum(self._estimates))
        return PHASE_COST[cell.phase] * self._estimates[cell.file_index]

    def percent_value(self) -> int:
        """Der aktuelle Gesamtfortschritt in Prozent, monoton steigend."""
        gesamt = sum(self._budget(cell) for cell in self._cells)
        if gesamt <= 0:
            return 100
        erledigt = sum(self._budget(cell) for cell in self._cells[: self._cursor])
        erledigt += self._budget(self._cells[self._cursor]) * self._fraction
        # Abrunden: 100 % steht erst, wenn wirklich alles erledigt ist. Das
        # ``round`` davor faengt nur den Rundungsfehler der Gleitkommasumme
        # ab - ohne ihn endet ein vollstaendiger Lauf bei 99 %, weil
        # ``erledigt`` um 1e-13 unter ``gesamt`` liegt.
        wert = int(round(erledigt * 100.0 / gesamt, 6))
        return max(0, min(100, wert))

    def _emit(self) -> None:
        wert = max(self._reported, self.percent_value())
        self._reported = wert
        self._inner.percent(wert)

    def _find(self, phase: str) -> int | None:
        """Der naechste Abschnitt dieser Phase - nie einer, der schon vorbei ist."""
        for index in range(self._cursor, len(self._cells)):
            cell = self._cells[index]
            if cell.phase != phase:
                continue
            if cell.file_index >= 0 and cell.file_index != self._file_index:
                continue
            return index
        return None

    # ── ProgressSink ──────────────────────────────────────────────

    def phase(self, phase: str) -> None:
        ziel = self._find(phase)
        if ziel is not None and ziel != self._cursor:
            self._cursor = ziel
            self._fraction = 0.0
        self._inner.phase(phase)
        self._emit()

    def file(self, current: int, total: int) -> None:
        self._file_index = int(current) - 1 - self._first_new
        self._inner.file(int(current), int(total))

    def items(self, current: int, total: int) -> None:
        if total > 0:
            self._fraction = max(0.0, min(1.0, float(current) / float(total)))
            cell = self._cells[self._cursor]
            if cell.phase == PHASE_DUPLICATES and cell.file_index >= 0:
                # Erst hier steht die echte Buchungszahl der Datei fest.
                self._estimates[cell.file_index] = float(total)
        else:
            # Nichts zu tun ist nicht "unbekannt", sondern fertig.
            self._fraction = 1.0
        self._inner.items(int(current), int(total))
        self._emit()

    def percent(self, value: int | None) -> None:
        if value is None:
            self._inner.percent(None)
            return
        self._fraction = max(0.0, min(1.0, float(value) / 100.0))
        self._emit()

    def cancelled(self) -> bool:
        return self._inner.cancelled()


@dataclass
class LoadedSource:
    """Eine eingelesene Auszugsdatei samt ihrer Buchungszeilen."""

    path: str
    digest: str
    source_format: str
    transactions: list[BankTransaction]
    duplicate_indexes: set[int]


@dataclass
class ReviewState:
    """Der Prueflistenzustand einer einzelnen Buchungszeile."""

    use: bool
    typ: str
    category_typ: str = ""
    category: str = ""
    manual_tags: set[str] = field(default_factory=set)
    confidence: float = 0.0
    prediction_method: str = ""


#: Schluessel, unter dem eine Zeile ihren Zustand ueber einen Neuaufbau
#: hinweg wiederfindet: Dateidigest, Quellname und Zeilennummer.
StateKey = tuple[str, str, int]


@dataclass(frozen=True)
class AnalysisRequest:
    """Alles, was die Analyse braucht - und nichts, was am Thread haengt."""

    snapshot: BankImportAnalysisSnapshot
    sources: tuple[LoadedSource, ...] = ()
    new_paths: tuple[str, ...] = ()
    currency: str = "CHF"
    previous_states: Mapping[StateKey, ReviewState] = field(default_factory=dict)
    #: Meldung fuer eine inhaltsgleich schon geladene Datei. Sie wird vom
    #: Aufrufer uebersetzt hereingereicht - dieses Modul kennt keine Sprache
    #: und darf ``utils.i18n`` nicht aus einem Worker-Thread anfassen.
    same_file_message: str = "same file already loaded"


@dataclass(frozen=True)
class AnalysisResult:
    """Das fertige Analyseergebnis, bereit zum Anzeigen im GUI-Thread."""

    sources: tuple[LoadedSource, ...] = ()
    transactions: tuple[BankTransaction, ...] = ()
    transaction_digests: tuple[str, ...] = ()
    duplicate_indexes: frozenset[int] = frozenset()
    twint_credit_indexes: frozenset[int] = frozenset()
    marked_twint_indexes: frozenset[int] = frozenset()
    ai_marker_indexes: frozenset[int] = frozenset()
    matches: Mapping[int, ReimbursementMatch] = field(default_factory=dict)
    matched_credit_indexes: frozenset[int] = frozenset()
    states: Mapping[int, ReviewState] = field(default_factory=dict)
    errors: tuple[str, ...] = ()


def state_key(digest: str, tx: BankTransaction) -> StateKey:
    """Wiedererkennungsschluessel einer Zeile ueber einen Neuaufbau hinweg."""
    return (digest, str(tx.source_name or ""), int(tx.source_index))


def booking_signal(index: int, tx: BankTransaction) -> BookingSignal:
    """Buchungssignal fuer den TWINT-Erstattungsabgleich."""
    return BookingSignal(
        booking_id=f"row:{index}",
        booking_date=tx.booking_date,
        amount=float(tx.amount),
        description=tx.description,
        counterparty=tx.counterparty,
    )


def _checkpoint(sink: ProgressSink) -> None:
    if sink.cancelled():
        raise AnalysisCancelled()


def _load_sources(
    request: AnalysisRequest, sink: ProgressSink
) -> tuple[list[LoadedSource], list[str]]:
    """Liest die neu gewaehlten Dateien und haengt sie an die bekannten an.

    Doppelt gewaehlte Pfade und inhaltsgleiche Dateien fallen hier heraus -
    genau wie zuvor im Dialog, damit derselbe Auszug nicht zweimal in der
    Pruefliste landet.
    """
    sources = list(request.sources)
    errors: list[str] = []
    if not request.new_paths:
        return sources, errors

    known_paths = {str(Path(source.path).resolve()) for source in sources}
    known_digests = {source.digest for source in sources}
    erste_neue = len(request.sources)
    dateien_gesamt = erste_neue + len(request.new_paths)
    for position, path in enumerate(request.new_paths):
        _checkpoint(sink)
        sink.file(erste_neue + position + 1, dateien_gesamt)
        sink.phase(PHASE_READ)
        resolved = str(Path(path).resolve())
        if resolved in known_paths:
            continue
        try:
            # Phase "Datei lesen": beides holt die Datei tatsaechlich von der
            # Platte - der Formatschnueffler und die Pruefsumme. Beide Wege
            # lesen in einem ``with``-Block bzw. ueber ``read_bytes()`` und
            # lassen kein offenes Handle zurueck.
            kreditkarte = is_credit_card_csv(path)
            digest = source_digest(path)
            if digest in known_digests:
                errors.append(f"{Path(path).name}: {request.same_file_message}")
                continue
            # Phase "Buchungen erkennen": aus Bytes werden Buchungszeilen.
            sink.phase(PHASE_PARSE)
            if kreditkarte:
                transactions = load_credit_card_csv(path, request.currency)
                source_format = FORMAT_CREDIT_CARD
            else:
                transactions = load_transactions(path, request.currency)
                source_format = FORMAT_BANK
            duplicates = _duplicates_of(request.snapshot, transactions, digest, sink)
        except (BankStatementError, OSError, ValueError) as exc:
            errors.append(f"{Path(path).name}: {exc}")
            continue
        sources.append(
            LoadedSource(path, digest, source_format, list(transactions), duplicates)
        )
        known_paths.add(resolved)
        known_digests.add(digest)
    return sources, errors


def _duplicates_of(
    snapshot: BankImportAnalysisSnapshot,
    transactions: Sequence[BankTransaction],
    digest: str,
    sink: ProgressSink,
) -> set[int]:
    sink.phase(PHASE_DUPLICATES)
    total = len(transactions)
    duplicates: set[int] = set()
    for index, tx in enumerate(transactions):
        if index % 64 == 0:
            _checkpoint(sink)
        if snapshot.is_duplicate(tx, digest):
            duplicates.add(index)
        sink.items(index + 1, total)
    return duplicates


@dataclass(frozen=True)
class _Flat:
    """Alle Quellen als eine durchlaufende Buchungsliste."""

    transactions: list[BankTransaction]
    digests: list[str]
    duplicates: set[int]
    #: Zu jeder Buchung die 1-basierte Nummer ihrer Quelldatei.
    file_numbers: list[int]
    #: Anzahl Quelldateien - der Nenner in "Datei 3 von 5".
    file_count: int


def _flatten(sources: Iterable[LoadedSource]) -> _Flat:
    transactions: list[BankTransaction] = []
    digests: list[str] = []
    duplicates: set[int] = set()
    file_numbers: list[int] = []
    offset = 0
    count = 0
    for nummer, source in enumerate(sources, start=1):
        count = nummer
        transactions.extend(source.transactions)
        digests.extend(source.digest for _tx in source.transactions)
        file_numbers.extend(nummer for _tx in source.transactions)
        duplicates.update(offset + index for index in source.duplicate_indexes)
        offset += len(source.transactions)
    return _Flat(transactions, digests, duplicates, file_numbers, count)


class _FileReporter:
    """Meldet die Quelldatei der gerade bearbeiteten Buchung - nur bei Wechsel.

    Ohne die Wechselpruefung schickte jede einzelne Buchung dieselbe Meldung
    ueber die Threadgrenze; bei 5000 Zeilen sind das 5000 Ereignisse fuer eine
    Aussage, die sich vier Mal aendert.
    """

    def __init__(self, sink: ProgressSink, flat: _Flat) -> None:
        self._sink = sink
        self._numbers = flat.file_numbers
        self._count = flat.file_count
        self._last = -1

    def at(self, index: int) -> None:
        if not (0 <= index < len(self._numbers)):
            return
        nummer = self._numbers[index]
        if nummer == self._last:
            return
        self._last = nummer
        self._sink.file(nummer, self._count)


@dataclass(frozen=True)
class _TwintSets:
    credits: set[int]
    marked: set[int]
    ai_marked: set[int]


def _twint_sets(
    snapshot: BankImportAnalysisSnapshot,
    transactions: Sequence[BankTransaction],
    digests: Sequence[str],
    sink: ProgressSink,
) -> _TwintSets:
    """Positive TWINT-Eingaenge und die bereits als Lernsignal markierten Zeilen.

    Ohne Stueckmeldung: Diese Vorarbeit ist ein billiger Durchlauf. Den
    Fortschritt der TWINT-Phase meldet der teure Teil, der Erstattungsabgleich
    in :func:`_build_matches` - sonst liefe der Abschnitt zweimal von vorn.
    """
    sink.phase(PHASE_TWINT)
    credits: set[int] = set()
    for index, tx in enumerate(transactions):
        if index % 64 == 0:
            _checkpoint(sink)
        if is_twint_credit(tx):
            credits.add(index)

    groups: dict[str, list[int]] = {}
    for index, digest in enumerate(digests):
        groups.setdefault(digest, []).append(index)

    marked: set[int] = set()
    ai_marked: set[int] = set()
    for digest, indexes in groups.items():
        _checkpoint(sink)
        local = [transactions[index] for index in indexes]
        for position in snapshot.marked_indexes(
            local, digest, marker_kind="twint_credit"
        ):
            marked.add(indexes[position])
        # ``bank_import_marker_state.external_id`` ist Primaerschluessel: je
        # Buchungszeile existiert genau ein Marker, die Art steht in
        # ``marker_kind``. Zeilen, die in 3.0.3-3.0.6 auf "nur lernen, nicht
        # buchen" gesetzt wurden, tragen ``twint_ai``. Ohne diese zweite
        # Abfrage gelten sie als unmarkiert und werden erneut zum Import
        # angeboten.
        for position in snapshot.marked_indexes(local, digest, marker_kind="twint_ai"):
            ai_marked.add(indexes[position])
    return _TwintSets(credits, marked, ai_marked)


def _build_matches(
    transactions: Sequence[BankTransaction],
    duplicates: set[int],
    marked: set[int],
    sink: ProgressSink,
    dateien: _FileReporter,
) -> tuple[dict[int, ReimbursementMatch], set[int]]:
    """Ordnet Ausgaben eine zeitnahe TWINT-Erstattung zu."""
    matches: dict[int, ReimbursementMatch] = {}
    matched_credits: set[int] = set()
    credits = [
        booking_signal(index, tx)
        for index, tx in enumerate(transactions)
        if tx.amount > 0 and index not in duplicates and index not in marked
    ]
    total = len(transactions)
    for index, tx in enumerate(transactions):
        if index % 64 == 0:
            _checkpoint(sink)
        dateien.at(index)
        sink.items(index + 1, total)
        if tx.amount >= 0 or index in duplicates:
            continue
        match = match_twint_reimbursement(booking_signal(index, tx), credits)
        if match is None:
            continue
        try:
            credit_index = int(match.credit_id.split(":", 1)[1])
        except (ValueError, IndexError):
            continue
        if credit_index in matched_credits or credit_index in marked:
            continue
        matches[index] = match
        matched_credits.add(credit_index)
    return matches, matched_credits


def _initial_state(
    request: AnalysisRequest,
    index: int,
    tx: BankTransaction,
    digest: str,
    duplicates: set[int],
    twint: _TwintSets,
) -> ReviewState:
    snapshot = request.snapshot
    learned = index in twint.marked or index in twint.ai_marked
    if index in duplicates:
        return ReviewState(
            False,
            (
                TYP_TWINT_AI
                if is_twint_credit(tx)
                else (TYP_INCOME if tx.amount > 0 else TYP_EXPENSES)
            ),
        )
    if is_twint_credit(tx):
        preferred = snapshot.classification(tx, digest, marker_kind="twint_credit")
        if not all(preferred):
            preferred = snapshot.suggest_category(tx)
        return ReviewState(
            use=not learned and all(preferred),
            typ=TYP_TWINT_AI,
            category_typ=preferred[0] if all(preferred) else "",
            category=preferred[1] if all(preferred) else "",
            confidence=0.95 if all(preferred) else 0.0,
            prediction_method="twint_memory" if all(preferred) else "",
        )
    if index in twint.ai_marked:
        # Zeile wurde frueher bewusst auf "nur lernen, nicht buchen" gesetzt.
        # Sie bleibt ein Lernsignal und wird nicht erneut zum Import angeboten.
        preferred = snapshot.classification(tx, digest, marker_kind="twint_ai")
        if not all(preferred):
            preferred = snapshot.suggest_category(tx)
        return ReviewState(
            use=False,
            typ=TYP_TWINT_AI,
            category_typ=preferred[0] if all(preferred) else "",
            category=preferred[1] if all(preferred) else "",
            confidence=0.95 if all(preferred) else 0.0,
            prediction_method="twint_memory" if all(preferred) else "",
        )
    typ = TYP_INCOME if tx.amount > 0 else TYP_EXPENSES
    prediction = snapshot.predict(
        typ=typ, description=tx.description, counterparty=tx.counterparty
    )
    return ReviewState(
        use=True,
        typ=typ,
        category_typ=typ if prediction.category else "",
        category=prediction.category,
        confidence=float(prediction.confidence),
        prediction_method=prediction.method,
    )


def _states(
    request: AnalysisRequest,
    transactions: Sequence[BankTransaction],
    digests: Sequence[str],
    duplicates: set[int],
    twint: _TwintSets,
    matches: Mapping[int, ReimbursementMatch],
    sink: ProgressSink,
    dateien: _FileReporter,
) -> dict[int, ReviewState]:
    sink.phase(PHASE_CATEGORIZE)
    total = len(transactions)
    states: dict[int, ReviewState] = {}
    for index, tx in enumerate(transactions):
        if index % 32 == 0:
            _checkpoint(sink)
        dateien.at(index)
        digest = digests[index]
        state = _initial_state(request, index, tx, digest, duplicates, twint)
        previous = request.previous_states.get(state_key(digest, tx))
        if previous is not None:
            state.use = previous.use
            state.typ = previous.typ
            state.category_typ = previous.category_typ
            state.category = previous.category
        states[index] = state
        sink.items(index + 1, total)

    # Eigene Phase, weil die Tags aus einer anderen Quelle stammen als die
    # Kategorie: nicht aus der Vorhersage, sondern aus dem, was der Anwender
    # in einem frueheren Durchlauf selbst vergeben hat. Ein Neuaufbau der
    # Pruefliste - Datei dazu, Quelle weg - darf diese Handarbeit nicht
    # wegwerfen. Bei einem Erstimport ohne Vorzustand ist hier nichts zu tun.
    sink.phase(PHASE_TAGS)
    if request.previous_states:
        for index, tx in enumerate(transactions):
            if index % 32 == 0:
                _checkpoint(sink)
            dateien.at(index)
            previous = request.previous_states.get(state_key(digests[index], tx))
            if previous is not None and previous.manual_tags:
                states[index].manual_tags = set(previous.manual_tags)
            sink.items(index + 1, total)
    else:
        sink.items(total, total)

    # Ein sicherer TWINT-Erstattungstreffer uebernimmt die bereits bekannte
    # Kategorie der zugehoerigen Ausgabe. Damit wird die Lernzeile nicht zu
    # einem zusaetzlichen Pflichtschritt im normalen Import.
    sink.phase(PHASE_REVIEW)
    offen = len(matches)
    sink.items(0, offen)
    for erledigt, (expense_index, match) in enumerate(matches.items(), start=1):
        _checkpoint(sink)
        sink.items(erledigt, offen)
        try:
            credit_index = int(match.credit_id.split(":", 1)[1])
        except (ValueError, IndexError):
            continue
        expense_state = states.get(expense_index)
        credit_state = states.get(credit_index)
        if (
            expense_state is None
            or credit_state is None
            or credit_state.category
            or not expense_state.category
        ):
            continue
        credit_state.category_typ = expense_state.category_typ
        credit_state.category = expense_state.category
        credit_state.confidence = max(0.90, expense_state.confidence)
        credit_state.prediction_method = "twint_match"
        credit_state.use = credit_index not in twint.marked and (
            credit_index not in twint.ai_marked
        )
    if not offen:
        sink.percent(100)
    return states


def _estimated_bookings(path: str) -> float:
    """Grobschaetzung der Buchungszahl einer noch ungelesenen Datei."""
    try:
        groesse = Path(path).stat().st_size
    except OSError:
        return FALLBACK_BOOKINGS_PER_FILE
    return max(1.0, float(groesse) / BYTES_PER_BOOKING)


def weighted_sink(request: AnalysisRequest, sink: ProgressSink) -> WeightedProgress:
    """Legt die Gewichtung ueber einen Sink - eine Zeile fuer Aufrufer."""
    return WeightedProgress(
        sink,
        known_bookings=sum(len(source.transactions) for source in request.sources),
        estimates=[_estimated_bookings(path) for path in request.new_paths],
        first_new_file=len(request.sources),
    )


def analyse(
    request: AnalysisRequest, sink: ProgressSink | None = None
) -> AnalysisResult:
    """Rechnet die komplette Bankimport-Analyse aus eingefrorenen Daten.

    Reihenfolge und Ergebnis sind dieselben wie in der frueheren
    GUI-Thread-Fassung des V4-Dialogs; einziger Unterschied ist, dass hier
    Fortschritt gemeldet und der Abbruch geprueft wird.

    Der uebergebene Sink bekommt den **global gewichteten** Fortschritt: Die
    Rechnung meldet ihren Phasenfortschritt an eine :class:`WeightedProgress`,
    die daraus einen monoton steigenden Gesamtwert ueber alle Dateien und alle
    sieben Phasen macht.
    """
    roh = sink or ProgressSink()
    sink = weighted_sink(request, roh)
    sources, errors = _load_sources(request, sink)
    flat = _flatten(sources)
    transactions, digests, duplicates = flat.transactions, flat.digests, flat.duplicates
    dateien = _FileReporter(sink, flat)
    twint = _twint_sets(request.snapshot, transactions, digests, sink)
    matches, matched_credits = _build_matches(
        transactions, duplicates, twint.marked, sink, dateien
    )
    states = _states(
        request, transactions, digests, duplicates, twint, matches, sink, dateien
    )
    return AnalysisResult(
        sources=tuple(sources),
        transactions=tuple(transactions),
        transaction_digests=tuple(digests),
        duplicate_indexes=frozenset(duplicates),
        twint_credit_indexes=frozenset(twint.credits),
        marked_twint_indexes=frozenset(twint.marked),
        ai_marker_indexes=frozenset(twint.ai_marked),
        matches=dict(matches),
        matched_credit_indexes=frozenset(matched_credits),
        states=states,
        errors=tuple(errors),
    )


__all__ = [
    "ALL_PHASES",
    "BYTES_PER_BOOKING",
    "FALLBACK_BOOKINGS_PER_FILE",
    "GLOBAL_PHASES",
    "PER_FILE_PHASES",
    "PHASE_COST",
    "AnalysisCancelled",
    "AnalysisRequest",
    "AnalysisResult",
    "FORMAT_BANK",
    "FORMAT_CREDIT_CARD",
    "LoadedSource",
    "PHASE_CATEGORIZE",
    "PHASE_DUPLICATES",
    "PHASE_PARSE",
    "PHASE_READ",
    "PHASE_REVIEW",
    "PHASE_TAGS",
    "PHASE_TWINT",
    "ProgressSink",
    "ReviewState",
    "StateKey",
    "WeightedProgress",
    "analyse",
    "booking_signal",
    "state_key",
    "weighted_sink",
]

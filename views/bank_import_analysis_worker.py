"""Der Analyse-Worker des Bankimports: dieselbe Rechnung, anderer Thread.

Die Rechnung selbst steht Qt-frei in :mod:`model.bank_import_analysis`. Dieses
Modul haengt nur Signale daran, damit sie in einem ``QThread`` laufen kann:

    thread = QThread()
    worker = BankImportAnalysisWorker(request)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.status_changed.connect(area.set_activity)
    worker.item_progress.connect(area.set_item_progress)
    worker.finished.connect(dialog.apply_result)

Der Worker fasst **kein** Widget an. Er importiert deshalb nichts aus
``PySide6.QtWidgets`` und nichts aus ``views`` ausser i18n-Text; ein Test haelt
das ueber die Importliste fest. Er haelt ausserdem keine
``sqlite3.Connection``: alles Datenbankgebundene steckt eingefroren im
Snapshot des ``AnalysisRequest``.

Abbruch ist kooperativ. ``request_cancel()`` setzt ein ``threading.Event``,
die Rechnung fragt es an ihren Schleifengrenzen ab und endet mit
``cancelled()``. ``QThread.terminate()`` kommt hier nicht vor - es liesse
halboffene Dateihandles zurueck.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from model.bank_import_analysis import (
    PHASE_CATEGORIZE,
    PHASE_DUPLICATES,
    PHASE_READ,
    PHASE_REVIEW,
    PHASE_TWINT,
    AnalysisCancelled,
    AnalysisRequest,
    ProgressSink,
    analyse,
)
from model.bank_statement_reader import BankStatementError
from utils.i18n import tr

logger = logging.getLogger(__name__)

# Fehler, die eine kaputte oder unerwartete Datei ausloest. Sie gehoeren in
# die Oberflaeche, nicht in einen stillen Abbruch. Bewusst als Liste und
# nicht als ``except Exception``: ein ``KeyboardInterrupt`` oder ein
# ``SystemExit`` muss den Prozess weiterhin beenden koennen.
ANALYSIS_ERRORS = (
    BankStatementError,
    OSError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
    AttributeError,
    ArithmeticError,
    RuntimeError,
)


def phase_label(phase: str) -> str:
    """Anzeigetext einer Analysephase in der aktiven Sprache."""
    if phase == PHASE_READ:
        return tr("import_progress.phase_read")
    if phase == PHASE_DUPLICATES:
        return tr("import_progress.phase_duplicates")
    if phase == PHASE_TWINT:
        return tr("import_progress.phase_twint")
    if phase == PHASE_CATEGORIZE:
        return tr("import_progress.phase_categorize")
    if phase == PHASE_REVIEW:
        return tr("import_progress.phase_review")
    return ""


class _SignalSink(ProgressSink):
    """Uebersetzt Fortschrittsmeldungen in Signale des Workers.

    Gedrosselt, weil jede Meldung einen Thread-Wechsel kostet: gemeldet wird
    nur, wenn sich die ganze Prozentzahl aendert oder die Phase endet. Ein
    Auszug mit 5000 Zeilen erzeugt so hoechstens gut hundert Ereignisse statt
    fuenftausend.
    """

    def __init__(self, worker: BankImportAnalysisWorker) -> None:
        self._worker = worker
        self._phase = ""
        self._last_percent = -1

    def phase(self, phase: str) -> None:
        if phase == self._phase:
            return
        self._phase = phase
        self._last_percent = -1
        self._worker.status_changed.emit(phase_label(phase))

    def items(self, current: int, total: int) -> None:
        if total <= 0:
            # Nichts zu tun ist nicht "unbekannt", sondern fertig.
            self.percent(100)
            return
        percent = round(current * 100 / total)
        if percent == self._last_percent and current < total:
            return
        self._last_percent = percent
        self._worker.item_progress.emit(current, total)

    def percent(self, value: int | None) -> None:
        if value is None:
            self._last_percent = -1
            self._worker.indeterminate.emit()
            return
        if value == self._last_percent:
            return
        self._last_percent = value
        self._worker.progress_changed.emit(int(value))

    def cancelled(self) -> bool:
        return self._worker.is_cancelled()


class BankImportAnalysisWorker(QObject):
    """Fuehrt :func:`model.bank_import_analysis.analyse` ausserhalb der GUI aus."""

    #: Name der laufenden Taetigkeit, bereits uebersetzt.
    status_changed = Signal(str)
    #: Fortschritt der laufenden Phase in Prozent.
    progress_changed = Signal(int)
    #: Erledigte und gesamte Einzelposten der laufenden Phase.
    item_progress = Signal(int, int)
    #: Kein belastbarer Prozentwert - der Balken laeuft unbestimmt (Regel 1.7).
    indeterminate = Signal()
    #: Fertiges :class:`~model.bank_import_analysis.AnalysisResult`.
    finished = Signal(object)
    #: Fehlermeldung fuer die Oberflaeche.
    failed = Signal(str)
    #: Der Vorgang wurde auf Wunsch beendet und hat kein Ergebnis.
    cancelled = Signal()

    def __init__(self, request: AnalysisRequest) -> None:
        super().__init__()
        self._request = request
        self._cancel = threading.Event()

    # ── Abbruch ───────────────────────────────────────────────────
    @Slot()
    def request_cancel(self) -> None:
        """Bittet die laufende Rechnung, beim naechsten Pruefpunkt zu enden."""
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    # ── Ausfuehrung ───────────────────────────────────────────────
    @Slot()
    def run(self) -> None:
        """Rechnet und meldet genau ein Endergebnis: fertig, Fehler oder Abbruch.

        Der ``finally``-Zweig beendet die Ereignisschleife des Threads in
        *jedem* Fall - auch bei einem Fehler, den die Liste oben nicht kennt.
        Ohne ihn bliebe der Thread nach einer unerwarteten Ausnahme in seiner
        Schleife stehen, und der Dialog wartete beim Schliessen vergeblich.
        """
        try:
            result = analyse(self._request, _SignalSink(self))
        except AnalysisCancelled:
            self.cancelled.emit()
        except ANALYSIS_ERRORS as exc:
            logger.exception("Bankimport-Analyse fehlgeschlagen")
            self.failed.emit(str(exc))
        else:
            if self.is_cancelled():
                # Der Abbruch kam erst nach dem letzten Pruefpunkt. Ein
                # Ergebnis, das niemand mehr angefordert hat, darf die
                # Pruefliste nicht ueberschreiben.
                self.cancelled.emit()
            else:
                self.finished.emit(result)
        finally:
            self._quit_own_thread()

    @staticmethod
    def _quit_own_thread() -> None:
        """Beendet die Ereignisschleife des Worker-Threads - nur die eigene.

        Der GUI-Thread ist ausgenommen: Ein direkt aufgerufenes ``run()``
        (Test, synchroner Sonderweg) wuerde sonst die Ereignisschleife der
        Anwendung beenden.
        """
        thread = QThread.currentThread()
        app = QCoreApplication.instance()
        if thread is None or (app is not None and thread is app.thread()):
            return
        thread.quit()


__all__ = ["ANALYSIS_ERRORS", "BankImportAnalysisWorker", "phase_label"]

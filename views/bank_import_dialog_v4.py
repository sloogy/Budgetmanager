"""Bankimport V4 – review-first statt administrations-first.

Die aktive Oberfläche hat bewusst nur *eine* Auswahl: das Häkchen links.
Dieses Häkchen steuert sowohl den späteren Import als auch Massenaktionen.
Typ, KI-Details und Tag-Verwaltung sind aus der Haupttabelle entfernt:

1. Dateien hinzufügen.
2. Nur ``Zu prüfen`` korrigieren.
3. Importieren.

Die vorhandene Fachlogik (Duplikate, lokale Lern-KI, TWINT-Schutz,
Mehrdatei-Digests, Kategorie-Tags, Tag-Regeln und atomare Import-Batches)
bleibt erhalten.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from model.ai_learning_source import source_from_prediction_method
from model.bank_import_ai import ReimbursementMatch
from model.bank_import_analysis import (
    PHASE_READ,
    AnalysisRequest,
    AnalysisResult,
    LoadedSource,
    ReviewState,
    StateKey,
    state_key,
)
from model.bank_import_service import BankImportItem
from model.bank_import_snapshot import (
    BankImportAnalysisSnapshot,
    capture_analysis_snapshot,
)
from model.bank_statement_reader import BankTransaction
from model.tags_model import TagsModel
from model.twint_import_policy import (
    TYP_TWINT_AI,
    BankImportMarkerStore,
    TwintAwareBankImportService,
    TwintClassification,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME
from utils.accessibility import configure_dialog_tab_order
from utils.i18n import tr, trf
from utils.money import get_currency
from utils.notifications import show_info, show_warning
from views.bank_import_analysis_worker import BankImportAnalysisWorker, phase_label
from views.import_progress_area import ImportProgressArea

_CATEGORY_SEPARATOR = "\x1f"
_READY_CONFIDENCE = 0.80

# Wie lange das Schliessen auf den Analyse-Worker wartet, bevor der Thread
# geparkt wird. Grosszuegig, weil der Abbruch kooperativ ist: die Rechnung
# endet am naechsten Pruefpunkt, nicht mitten im Dateiparser.
_ANALYSIS_STOP_WAIT_MS = 8000

# Threads, die beim Schliessen ausnahmsweise noch liefen. Ohne diese Liste
# raeumt Python das QThread-Objekt zusammen mit dem Dialog ab, und Qt beendet
# den Prozess dann mit "QThread: Destroyed while thread is still running" -
# nach dem Schliessen, wenn niemand mehr hinsieht.
_PARKED_THREADS: set[QThread] = set()

# Vermerke in ``ReviewState.prediction_method``, die von einer Person stammen
# und nicht von der KI. Sie ueberleben deshalb das Umlegen des KI-Schalters -
# alles andere waere weggeworfene Handarbeit.
_HANDARBEIT = frozenset({"manual", "manual_bulk"})


class _KISchalterOhneDatei:
    """Notbehelf, wenn kein Einstellungsobjekt erreichbar ist.

    Der Dialog holt seine Schalter normalerweise vom Hauptfenster. In
    Testaufbauten und in den Audit-Werkzeugen wird er aber ohne Elternfenster
    erzeugt. Ein ``Settings()`` an dieser Stelle wuerde in die echte
    Einstellungsdatei des Benutzers schreiben - ein Testlauf duerfte niemals
    die Schalter des Anwenders umlegen. Dieser Stand-in verhaelt sich wie die
    Vorgabe (KI an, Lernen an) und vergisst alles beim Schliessen.
    """

    def __init__(self) -> None:
        self._werte: dict[str, object] = {}

    def get(self, key: str, default: object = None) -> object:
        return self._werte.get(key, default)

    def set(self, key: str, value: object) -> None:
        self._werte[key] = value


def _einstellungen_finden(widget: object) -> object:
    """Sucht das Einstellungsobjekt in der Elternkette des Dialogs.

    Dasselbe Muster wie ``views/import_progress_area.py::_theme_anchor``: In
    einem Dialog ist ``window()`` der Dialog selbst, das Hauptfenster steht
    erst weiter oben. Wer nur eine Ebene hoch schaut, findet nichts und
    bekaeme stillschweigend die Vorgabewerte.
    """
    knoten = widget
    tiefe = 0
    while knoten is not None and tiefe < 12:
        einstellungen = getattr(knoten, "settings", None)
        if einstellungen is not None and hasattr(einstellungen, "get"):
            return einstellungen
        eltern = getattr(knoten, "parent", None)
        knoten = eltern() if callable(eltern) else eltern
        tiefe += 1
    return _KISchalterOhneDatei()


def _park_until_finished(thread: QThread) -> None:
    """Haelt einen noch laufenden Thread am Leben, bis er wirklich endet."""
    _PARKED_THREADS.add(thread)
    thread.finished.connect(lambda: _PARKED_THREADS.discard(thread))
    thread.finished.connect(thread.deleteLater)


# ── Bloecke des finalen Imports ───────────────────────────────────
#
# Ein Block ist genau eine Datenbanktransaktion. ``_BATCH_TWINT_CREDIT`` und
# ``_BATCH_TWINT_AI`` tragen absichtlich die Werte, die
# ``mark_classifications(marker_kind=...)`` erwartet.
_BATCH_PLAN = "plan"
_BATCH_TWINT_CREDIT = "twint_credit"
_BATCH_TWINT_AI = "twint_ai"

# Was eine Schreibtransaktion realistisch werfen kann. Bewusst aufgezaehlt und
# nicht ``Exception``: Ein Programmierfehler soll sichtbar abstuerzen, statt als
# "Import teilweise fehlgeschlagen" zu erscheinen.
_IMPORT_WRITE_ERRORS = (sqlite3.Error, OSError, RuntimeError, TypeError, ValueError)

_BATCH_ERROR_TITLE = {
    _BATCH_PLAN: "bank_import_v4.partial_failure",
    _BATCH_TWINT_CREDIT: "bank_import_v4.ai_partial_failure",
    _BATCH_TWINT_AI: "bank_import_v4.ai_partial_failure",
}
_BATCH_ERROR_TEXT = {
    _BATCH_PLAN: "bank_import_v4.partial_failure_text",
    _BATCH_TWINT_CREDIT: "bank_import_v4.ai_partial_failure_text",
    _BATCH_TWINT_AI: "bank_import_v4.ai_partial_failure_text",
}


@dataclasses.dataclass(frozen=True)
class _ImportBatch:
    """Ein atomarer Schreibblock samt seiner Stelle in der Dateifolge."""

    kind: str
    digest: str
    rows: int
    file_position: int
    file_count: int


@dataclasses.dataclass
class _ImportOutcome:
    """Was die Schreibschleife tatsaechlich geschafft hat."""

    imported: int = 0
    skipped: int = 0
    learned: int = 0
    completed: int = 0
    cancelled: bool = False
    error: Exception | None = None
    error_title: str = "bank_import_v4.partial_failure"
    error_text: str = "bank_import_v4.partial_failure_text"


class SearchableCategoryCombo(QComboBox):
    """Kompakter Kategoriepicker mit Live-Suche im geöffneten Dropdown."""

    categoryChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setMaxVisibleItems(24)
        edit = self.lineEdit()
        if edit is not None:
            edit.setReadOnly(False)
            edit.setPlaceholderText(tr("bank_import_v4.category_search"))
            edit.textEdited.connect(self._filter_items)
        self.currentIndexChanged.connect(lambda _index: self.categoryChanged.emit())
        self.activated.connect(lambda _index: self.categoryChanged.emit())

    def showPopup(self) -> None:
        self._filter_items("")
        edit = self.lineEdit()
        if edit is not None:
            edit.clear()
            edit.setPlaceholderText(tr("bank_import_v4.category_search"))
        super().showPopup()
        if edit is not None:
            edit.setFocus()

    def hidePopup(self) -> None:
        super().hidePopup()
        self._filter_items("")
        edit = self.lineEdit()
        if edit is not None and self.currentIndex() >= 0:
            edit.setText(self.itemText(self.currentIndex()))

    def _filter_items(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        model = self.model()
        for row in range(model.rowCount()):
            label = str(model.index(row, 0).data() or "")
            self.view().setRowHidden(row, bool(query) and query not in label.casefold())


class TagSelectionDialog(QDialog):
    """Optionale Tags für eine oder mehrere angehakte Zeilen.

    Bei mehreren Zeilen bedeutet ein teilweise gesetztes Häkchen "gemischt /
    unverändert lassen". Kategorie-Tags werden außerhalb dieses Dialogs
    automatisch aus der Kategorie gezogen.
    """

    def __init__(
        self,
        tags: TagsModel,
        *,
        selected_all: set[str],
        selected_any: set[str],
        parent=None,
    ):
        super().__init__(parent)
        self.tags_model = tags
        self._selected_all = set(selected_all)
        self._selected_any = set(selected_any)
        self.setWindowTitle(tr("bank_import_v4.tags_title"))
        self.resize(430, 520)

        root = QVBoxLayout(self)
        note = QLabel(tr("bank_import_v4.tags_hint"))
        note.setWordWrap(True)
        root.addWidget(note)

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("search.placeholder"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        root.addWidget(self.search)

        self.list = QListWidget()
        root.addWidget(self.list, 1)
        self._reload()

        buttons = QHBoxLayout()
        self.btn_create = QPushButton(tr("bank_import_v4.create_tag"))
        self.btn_create.clicked.connect(self._create_tag)
        buttons.addWidget(self.btn_create)
        buttons.addStretch(1)
        cancel = QPushButton(tr("btn.cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(tr("btn.save"))
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _reload(self, preferred: str = "") -> None:
        current = self.tag_states() if hasattr(self, "list") else {}
        self.list.clear()
        for tag in sorted(
            self.tags_model.list_all(), key=lambda item: item.name.casefold()
        ):
            item = QListWidgetItem(tag.name)
            item.setData(Qt.ItemDataRole.UserRole, tag.name)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsUserTristate
            )
            if tag.name == preferred:
                state = Qt.CheckState.Checked
            elif tag.name in current:
                state = current[tag.name]
            elif tag.name in self._selected_all:
                state = Qt.CheckState.Checked
            elif tag.name in self._selected_any:
                state = Qt.CheckState.PartiallyChecked
            else:
                state = Qt.CheckState.Unchecked
            item.setCheckState(state)
            self.list.addItem(item)
        self._apply_filter(self.search.text())

    def _apply_filter(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for row in range(self.list.count()):
            item = self.list.item(row)
            name = str(item.data(Qt.ItemDataRole.UserRole) or "")
            item.setHidden(bool(query) and query not in name.casefold())

    def _create_tag(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            tr("tags.create_title"),
            tr("tags.create_name_label"),
        )
        name = str(name or "").strip()
        if not ok or not name:
            return
        if self.tags_model.name_exists(name):
            show_warning(self, tr("msg.error"), tr("bank_import_v4.tag_exists"))
            return
        try:
            self.tags_model.create_tag(name, action_text="")
        except (sqlite3.Error, ValueError) as exc:
            show_warning(self, tr("msg.error"), str(exc))
            return
        self._reload(preferred=name)

    def tag_states(self) -> dict[str, Qt.CheckState]:
        states: dict[str, Qt.CheckState] = {}
        for row in range(self.list.count()):
            item = self.list.item(row)
            name = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if name:
                states[name] = item.checkState()
        return states


class BankImportDialog(QDialog):
    """Aktiver, vereinfachter Bankimport mit einer einzigen Auswahlquelle."""

    COL_USE = 0
    COL_DATE = 1
    COL_TEXT = 2
    COL_AMOUNT = 3
    COL_CATEGORY = 4
    COL_SOURCE = 5
    COL_STATUS = 6

    def __init__(self, conn: sqlite3.Connection, parent=None, settings=None):
        super().__init__(parent)
        self.conn = conn
        # Die beiden KI-Schalter gehoeren den Einstellungen, nicht diesem
        # Dialog. Hier steht nur der Schnellzugriff darauf; das Zuruecksetzen
        # der Lerndaten bleibt bewusst den Einstellungen vorbehalten.
        self.settings = (
            settings if settings is not None else _einstellungen_finden(self)
        )
        # Kategorien liest die Analyse nur noch aus dem Snapshot; ``tags``
        # bleibt fuer den Tag-Auswahldialog, der auf dem GUI-Thread laeuft.
        self.tags = TagsModel(conn)
        self.service = TwintAwareBankImportService(conn)
        self.ai = self.service.ai
        self.marker_store = BankImportMarkerStore(conn)
        # Ab hier rechnet die Analyse ausschliesslich aus diesem Snapshot.
        # Die Modelle darueber bleiben fuer die Schreibwege (Import, Lernen)
        # und beruehren die Datenbank nur auf diesem Thread.
        self.snapshot: BankImportAnalysisSnapshot = self._capture_snapshot()

        self.sources: list[LoadedSource] = []
        self.transactions: list[BankTransaction] = []
        self._transaction_digests: list[str] = []
        self.duplicate_indexes: set[int] = set()
        self.twint_credit_indexes: set[int] = set()
        self.marked_twint_indexes: set[int] = set()
        self.ai_marker_indexes: set[int] = set()
        self.matches: dict[int, ReimbursementMatch] = {}
        self.matched_credit_indexes: set[int] = set()
        self.states: dict[int, ReviewState] = {}
        self._view_order: list[int] = []
        self._filter_key = "all"
        self._updating = False
        self._last_checkbox_row: int | None = None

        # Analyse-Worker. ``_analysis_active`` sagt, ob das Ergebnis des
        # laufenden Laufs noch erwuenscht ist; nach dem Schliessen ist es das
        # nicht mehr, auch wenn der Thread noch ein Signal nachschiebt.
        self._analysis_thread: QThread | None = None
        self._analysis_worker: BankImportAnalysisWorker | None = None
        self._analysis_active = False
        self._quit_hook_connected = False

        # Finaler Import. Er laeuft im Bedien-Thread; ``_import_running`` haelt
        # die Wiedereinstiege heraus, die das Pumpen der Ereignisschleife sonst
        # erlauben wuerde, ``_import_cancel_requested`` traegt den Abbruchwunsch
        # bis zur naechsten sicheren Blockgrenze.
        self._import_running = False
        self._import_cancel_requested = False

        self.setWindowTitle(tr("bank_import.window_title"))
        self.resize(1280, 760)
        self.setMinimumSize(980, 620)
        self._build_ui()
        self._refresh_ui()

    # ── Lokale Import-KI ──────────────────────────────────────────
    def ai_enabled(self) -> bool:
        """Darf die KI in diesem Lauf Kategorien vorschlagen?"""
        return bool(self.settings.get("bank_import_ai_enabled", True))

    def ai_learning_enabled(self) -> bool:
        """Darf dieser Import neues Wissen anlegen?"""
        return bool(self.settings.get("bank_import_ai_learning_enabled", True))

    def _forget_ai_predictions(self) -> None:
        """Wirft geratene Zuordnungen weg, von Hand gesetzte bleiben.

        Ohne das haette der Schalter beim Umlegen keine Wirkung: Ein
        Neuaufbau der Pruefliste uebernimmt die bisherigen Entscheidungen,
        und die geratene Kategorie stuende nach dem Ausschalten unveraendert
        da - bloss ohne Aussicht, je aktualisiert zu werden. Umgekehrt haette
        eine wieder eingeschaltete KI keine Gelegenheit, die leeren Zeilen zu
        fuellen.
        """
        for index in list(self.states):
            if self.states[index].prediction_method not in _HANDARBEIT:
                del self.states[index]

    def _ai_enabled_changed(self, checked: bool) -> None:
        self.settings.set("bank_import_ai_enabled", bool(checked))
        self._forget_ai_predictions()
        if self.sources:
            self._rebuild_from_sources()
        else:
            self._refresh_ui()

    def _ai_learning_changed(self, checked: bool) -> None:
        # Lernen wirkt erst beim Schreiben - die Pruefliste bleibt, wie sie
        # ist. Ein Neuaufbau waere hier reine Unruhe.
        self.settings.set("bank_import_ai_learning_enabled", bool(checked))

    def _capture_snapshot(self) -> BankImportAnalysisSnapshot:
        """Friert die Analysedaten auf dem besitzenden Thread ein."""
        self.snapshot = capture_analysis_snapshot(self.conn, ai_model=self.ai)
        return self.snapshot

    @staticmethod
    def _category_token(typ: str, category: str) -> str:
        return f"{typ}{_CATEGORY_SEPARATOR}{category}"

    @staticmethod
    def _decode_category_token(value: object) -> tuple[str, str]:
        text = str(value or "")
        if _CATEGORY_SEPARATOR not in text:
            return "", ""
        typ, category = text.split(_CATEGORY_SEPARATOR, 1)
        if typ not in {TYP_EXPENSES, TYP_INCOME}:
            return "", ""
        return typ, category

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(9)

        top = QHBoxLayout()
        self.btn_add_files = QPushButton(tr("bank_import_v4.add_files"))
        self.btn_add_files.clicked.connect(self.open_file)
        top.addWidget(self.btn_add_files)

        self.btn_sources = QToolButton()
        self.btn_sources.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_sources.setVisible(False)
        top.addWidget(self.btn_sources)

        self.lbl_headline = QLabel(tr("bank_import_v4.empty_hint"))
        top.addWidget(self.lbl_headline, 1)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("search.placeholder"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(230)
        self.search_input.textChanged.connect(self._apply_filters)
        top.addWidget(self.search_input)

        self.btn_options = QToolButton()
        self.btn_options.setText("⋯")
        self.btn_options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        options = QMenu(self.btn_options)
        # Schnellzugriff auf die beiden KI-Schalter. Bewusst nur diese zwei:
        # Das Zuruecksetzen der Lerndaten ist unwiderruflich und gehoert
        # deshalb an eine Stelle, an der man es sucht, nicht an eine, an der
        # man mitten im Import darueber stolpert.
        self.act_ai_enabled = QAction(tr("ai_settings.use_ai"), options)
        self.act_ai_enabled.setCheckable(True)
        self.act_ai_enabled.setChecked(self.ai_enabled())
        self.act_ai_enabled.toggled.connect(self._ai_enabled_changed)
        options.addAction(self.act_ai_enabled)
        self.act_ai_learning = QAction(
            tr("ai_settings.learn_from_corrections"), options
        )
        self.act_ai_learning.setCheckable(True)
        self.act_ai_learning.setChecked(self.ai_learning_enabled())
        self.act_ai_learning.toggled.connect(self._ai_learning_changed)
        options.addAction(self.act_ai_learning)
        self.act_ai_reset_hint = QAction(
            tr("ai_settings.reset_lives_in_settings"), options
        )
        self.act_ai_reset_hint.setEnabled(False)
        options.addAction(self.act_ai_reset_hint)
        options.addSeparator()
        self.act_net_twint = QAction(tr("bank_import_v4.net_twint"), options)
        self.act_net_twint.setCheckable(True)
        self.act_net_twint.setChecked(False)
        self.act_net_twint.toggled.connect(self._twint_option_changed)
        options.addAction(self.act_net_twint)
        options.addSeparator()
        sort_menu = options.addMenu(tr("bank_import_v4.sort"))
        for label_key, mode in (
            ("sort_original", "original"),
            ("sort_date_desc", "date_desc"),
            ("sort_date_asc", "date_asc"),
            ("sort_amount_desc", "amount_desc"),
            ("sort_amount_asc", "amount_asc"),
            ("sort_text_asc", "text_asc"),
            ("sort_category_asc", "category_asc"),
            ("sort_tags_asc", "tags_asc"),
            ("sort_source_asc", "source_asc"),
        ):
            action = QAction(tr(f"bank_import_v4.{label_key}"), sort_menu)
            action.triggered.connect(
                lambda _checked=False, selected_mode=mode: self._sort_view(
                    selected_mode
                )
            )
            sort_menu.addAction(action)
        self.btn_options.setMenu(options)
        top.addWidget(self.btn_options)
        root.addLayout(top)

        filters = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        self.filter_buttons: dict[str, QPushButton] = {}
        for key in ("all", "review", "ready", "duplicates", "twint"):
            button = QPushButton("")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, name=key: self._set_filter(name)
            )
            self.filter_group.addButton(button)
            self.filter_buttons[key] = button
            filters.addWidget(button)
        self.filter_buttons["all"].setChecked(True)
        filters.addStretch(1)
        self.btn_select_all_visible = QPushButton(tr("bank_import_v4.select_visible"))
        self.btn_select_all_visible.clicked.connect(
            lambda: self._set_visible_checked(True)
        )
        filters.addWidget(self.btn_select_all_visible)
        self.btn_clear_visible = QPushButton(tr("bank_import_v4.clear_visible"))
        self.btn_clear_visible.clicked.connect(lambda: self._set_visible_checked(False))
        filters.addWidget(self.btn_clear_visible)
        root.addLayout(filters)

        self.bulk_bar = QHBoxLayout()
        self.lbl_bulk = QLabel("")
        self.bulk_bar.addWidget(self.lbl_bulk)
        self.cmb_bulk_category = QComboBox()
        self.cmb_bulk_category.setMinimumWidth(260)
        self._fill_bulk_categories()
        self.bulk_bar.addWidget(self.cmb_bulk_category, 1)
        self.btn_set_category = QPushButton(tr("bank_import_v4.set_category"))
        self.btn_set_category.clicked.connect(self._bulk_set_category)
        self.bulk_bar.addWidget(self.btn_set_category)
        self.btn_tags = QPushButton(tr("bank_import_v4.tags_button"))
        self.btn_tags.clicked.connect(self._edit_tags_for_checked)
        self.bulk_bar.addWidget(self.btn_tags)
        self.btn_learn_only = QPushButton(tr("bank_import_v4.learn_only"))
        self.btn_learn_only.setToolTip(tr("bank_import_v4.learn_only_tip"))
        self.btn_learn_only.clicked.connect(self._toggle_learn_only)
        self.bulk_bar.addWidget(self.btn_learn_only)
        self.btn_skip = QPushButton(tr("bank_import_v4.skip_selected"))
        self.btn_skip.clicked.connect(lambda: self._set_checked_rows(False))
        self.bulk_bar.addWidget(self.btn_skip)
        self._set_bulk_visible(False)
        root.addLayout(self.bulk_bar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "✓",
                tr("header.date"),
                tr("bank_import_v4.booking"),
                tr("header.amount"),
                tr("header.category"),
                tr("header.source"),
                tr("bank_import_v4.status"),
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        for column, width in enumerate((46, 92, 350, 115, 260, 150, 210)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemClicked.connect(self._item_clicked)
        self.table.itemChanged.connect(self._item_changed)
        root.addWidget(self.table, 1)

        # Der Fortschrittsbereich sitzt zwischen Tabelle und Aktionsleiste:
        # unten im Fenster, mittig, und solange nichts laeuft vollstaendig
        # ausgeblendet. Bedient wird er vom Analyse-Worker.
        self.progress_area = ImportProgressArea(self)
        # Der Abbruchwunsch haengt am Dialog und nicht am jeweiligen Worker:
        # so gibt es genau eine Verbindung statt einer je Lauf, und sie zeigt
        # nie auf einen bereits abgeraeumten Worker.
        self.progress_area.cancel_requested.connect(self._on_progress_cancel_requested)
        root.addWidget(self.progress_area)

        bottom = QHBoxLayout()
        self.lbl_summary = QLabel("")
        bottom.addWidget(self.lbl_summary, 1)
        self.btn_close = QPushButton(tr("bank_import.close"))
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        self.btn_import = QPushButton(tr("bank_import_v4.import_button_empty"))
        self.btn_import.clicked.connect(self.import_selected)
        self.btn_import.setDefault(True)
        bottom.addWidget(self.btn_import)
        root.addLayout(bottom)

        self.shortcut_select_all = QShortcut(
            QKeySequence.StandardKey.SelectAll, self.table
        )
        self.shortcut_select_all.activated.connect(
            lambda: self._set_visible_checked(True)
        )

        # v3.0.6: Deterministische Tab-Kette. Der V4-Dialog war als einziger
        # der komplexen Dialoge nicht tastaturnavigierbar registriert
        # (final_release_audit d10_taborder_decl).
        configure_dialog_tab_order(self)

    def _set_bulk_visible(self, visible: bool) -> None:
        for index in range(self.bulk_bar.count()):
            widget = self.bulk_bar.itemAt(index).widget()
            if widget is not None:
                widget.setVisible(visible)

    def _fill_bulk_categories(self) -> None:
        self.cmb_bulk_category.clear()
        self.cmb_bulk_category.addItem(tr("bank_import_v4.choose_bulk_category"), "")
        for typ in (TYP_EXPENSES, TYP_INCOME):
            for display, name in self.snapshot.category_tree_for(typ):
                self.cmb_bulk_category.addItem(
                    f"{typ} · {display.strip()}", self._category_token(typ, name)
                )

    def _category_combo(self, index: int) -> SearchableCategoryCombo:
        state = self.states[index]
        tx = self.transactions[index]
        combo = SearchableCategoryCombo(self.table)
        combo.addItem(tr("bank_import.choose_placeholder"), "")

        preferred_type = state.category_typ or (
            TYP_INCOME if tx.amount > 0 else TYP_EXPENSES
        )
        types = (preferred_type,) + tuple(
            typ for typ in (TYP_EXPENSES, TYP_INCOME) if typ != preferred_type
        )
        for type_index, typ in enumerate(types):
            if type_index:
                combo.insertSeparator(combo.count())
            for display, name in self.snapshot.category_tree_for(typ):
                label = (
                    display.strip()
                    if typ == preferred_type
                    else f"{typ} · {display.strip()}"
                )
                combo.addItem(label, self._category_token(typ, name))

        wanted = self._category_token(state.category_typ, state.category)
        found = combo.findData(wanted) if state.category else -1
        if found >= 0:
            combo.setCurrentIndex(found)
        else:
            combo.setCurrentIndex(0)
        combo.categoryChanged.connect(
            lambda current=index: self._category_changed(current)
        )
        return combo

    def open_file(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("bank_import_v4.choose_files"),
            "",
            "Kontoauszüge (*.csv *.pdf);;CSV (*.csv);;PDF (*.pdf)",
        )
        if paths:
            self._add_paths(paths)

    def _add_paths(self, paths: list[str]) -> None:
        """Nimmt neu gewaehlte Dateien in die laufende Analyse auf."""
        self._start_analysis(new_paths=tuple(paths))

    def _rebuild_from_sources(self) -> None:
        """Rechnet die Pruefliste aus den bereits geladenen Quellen neu."""
        self._start_analysis()

    # ── Analyse-Worker ────────────────────────────────────────────
    # Die Rechnung selbst steht Qt-frei in ``model.bank_import_analysis`` und
    # laeuft in ``views.bank_import_analysis_worker`` in einem eigenen Thread.
    # Der Dialog gibt ihr nur den eingefrorenen Snapshot mit, zeigt Fortschritt
    # und uebernimmt am Ende das Ergebnis - alles Weitere bleibt hier draussen.

    def analysis_running(self) -> bool:
        """True, solange ein Analyse-Worker arbeitet."""
        return self._analysis_thread is not None

    def _previous_states(self) -> dict[StateKey, ReviewState]:
        """Bisherige Entscheidungen, damit ein Neuaufbau sie nicht wegwirft.

        Bewusst Kopien: die Originale gehoeren dem GUI-Thread und duerfen
        waehrend der Rechnung weiterleben, ohne dass der Worker mitliest.
        """
        previous: dict[StateKey, ReviewState] = {}
        for index, state in self.states.items():
            if not (0 <= index < len(self.transactions)):
                continue
            tx = self.transactions[index]
            previous[state_key(self._digest_for_index(index), tx)] = (
                dataclasses.replace(state, manual_tags=set(state.manual_tags))
            )
        return previous

    def _analysis_request(self, new_paths: tuple[str, ...]) -> AnalysisRequest:
        """Buendelt alles, was der Worker braucht - auf diesem Thread gelesen."""
        self._capture_snapshot()
        return AnalysisRequest(
            snapshot=self.snapshot,
            sources=tuple(self.sources),
            new_paths=new_paths,
            currency=get_currency().upper(),
            previous_states=self._previous_states(),
            same_file_message=tr("bank_import_v4.same_file_already_loaded"),
            ai_enabled=self.ai_enabled(),
        )

    def _start_analysis(self, *, new_paths: tuple[str, ...] = ()) -> None:
        if self.analysis_running():
            # Zwei gleichzeitige Laeufe haetten zwei Meinungen zur Pruefliste.
            return
        request = self._analysis_request(new_paths)

        thread = QThread()
        worker = BankImportAnalysisWorker(request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status_changed.connect(self.progress_area.set_activity)
        worker.progress_changed.connect(self.progress_area.set_percent)
        # Stueckzahlen ohne eigene Prozentrechnung: Der Balken zeigt den
        # gewichteten Gesamtfortschritt, nicht den der laufenden Phase.
        worker.item_progress.connect(self.progress_area.set_item_counts)
        worker.file_progress.connect(self.progress_area.set_file_progress)
        worker.indeterminate.connect(self.progress_area.set_indeterminate)
        worker.finished.connect(self._on_analysis_finished)
        worker.failed.connect(self._on_analysis_failed)
        worker.cancelled.connect(self._on_analysis_cancelled)
        for signal in (worker.finished, worker.failed, worker.cancelled):
            signal.connect(thread.quit)
            signal.connect(worker.deleteLater)
        thread.finished.connect(
            lambda beendeter=thread: self._on_analysis_thread_finished(beendeter)
        )

        self._analysis_thread = thread
        self._analysis_worker = worker
        self._analysis_active = True
        # Die Analyse ist jederzeit abbrechbar: Sie schreibt nichts in die
        # Datenbank, und ihr Ergebnis wird erst am Ende in einem Stueck
        # uebernommen. Ein Abbruch laesst die Pruefliste deshalb genau so
        # stehen, wie sie vor dem Lauf war.
        self.progress_area.start(phase_label(PHASE_READ), cancellable=True)
        self._refresh_ui()
        self._connect_quit_hook()
        thread.start()

    def _connect_quit_hook(self) -> None:
        """Auch ein globales ``quit()`` darf den Thread nicht zerlegen.

        Restore, Updater oder das Ende der Windows-Sitzung beenden die
        Anwendung, ohne diesen Dialog zu schliessen. Ohne diesen Haken faende
        Qt beim Abraeumen einen laufenden QThread vor und beendete den Prozess
        hart.
        """
        app = QApplication.instance()
        if app is None or self._quit_hook_connected:
            return
        app.aboutToQuit.connect(self._stop_analysis)
        self._quit_hook_connected = True

    @Slot()
    def request_analysis_cancel(self) -> None:
        """Bittet den laufenden Lauf zu enden - der Knopf im Fortschrittsbereich.

        Bewusst ein direkter Aufruf und keine Signalverbindung zum Worker: Der
        Worker lebt im Fremd-Thread, eine automatische Verbindung waere queued
        und wuerde erst abgearbeitet, wenn dessen Ereignisschleife wieder
        drankommt. Die steht aber still, solange ``run()`` rechnet - der
        Abbruch traefe also genau dann nicht ein, wenn er gebraucht wird.
        ``request_cancel()`` setzt nur ein ``threading.Event`` und ist von
        jedem Thread aus sicher aufrufbar.

        Der Dialog wartet hier **nicht** auf das Ende. Das Fenster bleibt
        bedienbar, der Worker meldet sich mit ``cancelled()``, und erst dann
        verschwindet der Balken.
        """
        worker = self._analysis_worker
        if worker is not None:
            worker.request_cancel()

    @Slot()
    def _stop_analysis(self) -> None:
        """Beendet einen laufenden Worker kooperativ und wartet auf ihn."""
        thread = self._analysis_thread
        worker = self._analysis_worker
        self._analysis_active = False
        self._analysis_thread = None
        self._analysis_worker = None
        if thread is None:
            return
        if worker is not None:
            worker.request_cancel()
        thread.quit()
        if thread.wait(_ANALYSIS_STOP_WAIT_MS):
            thread.deleteLater()
            return
        # Der Thread haengt laenger als erwartet. Ihn jetzt abzuraeumen waere
        # der harte Prozessabbruch; stattdessen bleibt er am Leben, bis er von
        # selbst endet.
        _park_until_finished(thread)

    def _on_analysis_thread_finished(self, thread: QThread) -> None:
        if thread is not self._analysis_thread:
            # Ein bereits abgeloester Lauf meldet sich nach - etwa ein beim
            # Schliessen geparkter Thread. Er darf einen inzwischen frisch
            # gestarteten Lauf nicht als beendet markieren.
            thread.deleteLater()
            return
        self._analysis_thread = None
        self._analysis_worker = None
        self._analysis_active = False
        thread.deleteLater()
        # Letzte Instanz gegen einen stehengebliebenen Balken: wer hier
        # ankommt, hat den Lauf hinter sich - egal ob mit Ergebnis, Fehler
        # oder einer Ausnahme, die den Worker vorzeitig beendet hat.
        if self.progress_area.is_active():
            self.progress_area.stop()
        self._refresh_ui()

    @Slot(object)
    def _on_analysis_finished(self, result: AnalysisResult) -> None:
        if not self._analysis_active:
            return
        self.progress_area.stop()
        self._apply_analysis(result)

    @Slot(str)
    def _on_analysis_failed(self, message: str) -> None:
        if not self._analysis_active:
            return
        self.progress_area.stop()
        self._refresh_ui()
        show_warning(self, tr("bank_import_v4.load_failed"), message)

    @Slot()
    def _on_analysis_cancelled(self) -> None:
        if not self._analysis_active:
            return
        self.progress_area.stop()
        self._refresh_ui()

    def _apply_analysis(self, result: AnalysisResult) -> None:
        """Uebernimmt das Worker-Ergebnis in die Pruefliste."""
        self.sources = list(result.sources)
        self.transactions = list(result.transactions)
        self._transaction_digests = list(result.transaction_digests)
        self.duplicate_indexes = set(result.duplicate_indexes)
        self.twint_credit_indexes = set(result.twint_credit_indexes)
        self.marked_twint_indexes = set(result.marked_twint_indexes)
        self.ai_marker_indexes = set(result.ai_marker_indexes)
        self.matches = dict(result.matches)
        self.matched_credit_indexes = set(result.matched_credit_indexes)
        self.states = dict(result.states)
        self._view_order = list(range(len(self.transactions)))
        self._populate_table()
        self._rebuild_sources_menu()
        self._refresh_ui()
        if result.errors:
            show_warning(
                self,
                (
                    tr("bank_import_v4.some_files_skipped")
                    if self.sources
                    else tr("bank_import_v4.load_failed")
                ),
                "\n".join(result.errors),
            )

    # ── Ende des Dialogs ──────────────────────────────────────────

    def done(self, result: int) -> None:
        # Sammelpunkt fuer accept(), reject() und den Fensterschliesser: der
        # Worker muss enden, bevor Qt diesen Dialog abraeumt.
        if self._import_running:
            # Die Schreibschleife pumpt die Ereignisse; ein Escape oder ein
            # Klick auf das Fensterkreuz kaeme genau hier an und wuerde den
            # Dialog mitten in einer offenen Transaktion abraeumen. Der Wunsch
            # wird als Abbruch verbucht und an der naechsten Blockgrenze
            # beachtet.
            self._import_cancel_requested = True
            return
        self._stop_analysis()
        super().done(result)

    def closeEvent(self, event) -> None:
        if self._import_running:
            self._import_cancel_requested = True
            event.ignore()
            return
        self._stop_analysis()
        super().closeEvent(event)

    def _is_learned(self, index: int) -> bool:
        """True, wenn die Zeile bereits als reines Lernsignal markiert ist."""
        return index in self.marked_twint_indexes or index in self.ai_marker_indexes

    def _populate_table(self) -> None:
        self._updating = True
        try:
            self.table.setRowCount(0)
            for index in self._view_order:
                row = self.table.rowCount()
                self.table.insertRow(row)
                tx = self.transactions[index]
                state = self.states[index]

                use_item = QTableWidgetItem()
                use_item.setData(Qt.ItemDataRole.UserRole, index)
                use_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                )
                use_item.setCheckState(
                    Qt.CheckState.Checked if state.use else Qt.CheckState.Unchecked
                )
                if index in self.duplicate_indexes or self._is_learned(index):
                    use_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    use_item.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row, self.COL_USE, use_item)

                self.table.setItem(
                    row,
                    self.COL_DATE,
                    QTableWidgetItem(tx.booking_date.strftime("%d.%m.%Y")),
                )
                text = (
                    tx.description
                    or tx.counterparty
                    or tr("bank_import_v4.unknown_booking")
                )
                text_item = QTableWidgetItem(text)
                detail = "\n".join(
                    part
                    for part in (tx.counterparty, tx.description, tx.source_name)
                    if part
                )
                text_item.setToolTip(detail)
                self.table.setItem(row, self.COL_TEXT, text_item)

                sign = "+" if float(tx.amount) > 0 else "−"
                amount_item = QTableWidgetItem(
                    f"{sign}{abs(float(tx.amount)):.2f} {tx.currency}"
                )
                amount_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row, self.COL_AMOUNT, amount_item)

                category_combo = self._category_combo(index)
                if index in self.duplicate_indexes or self._is_learned(index):
                    category_combo.setEnabled(False)
                self.table.setCellWidget(row, self.COL_CATEGORY, category_combo)
                self.table.setItem(
                    row, self.COL_SOURCE, QTableWidgetItem(tx.source_name or "")
                )
                self.table.setItem(row, self.COL_STATUS, QTableWidgetItem(""))
                self._update_row(row, index)
        finally:
            self._updating = False
        self._apply_filters()

    def _digest_for_index(self, index: int) -> str:
        if 0 <= index < len(self._transaction_digests):
            return self._transaction_digests[index]
        return ""

    def _row_for_index(self, index: int) -> int:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_USE)
            if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == index:
                return row
        return -1

    def _category_changed(self, index: int) -> None:
        if self._updating:
            return
        row = self._row_for_index(index)
        if row < 0:
            return
        combo = self.table.cellWidget(row, self.COL_CATEGORY)
        if not isinstance(combo, QComboBox):
            return
        typ, category = self._decode_category_token(combo.currentData())
        state = self.states[index]
        state.category_typ = typ
        state.category = category
        if category:
            state.confidence = 1.0
            state.prediction_method = "manual"
        if state.typ != TYP_TWINT_AI and typ:
            state.typ = typ
        self._update_row(row, index)
        self._refresh_ui()
        self._apply_filters()

    def _item_clicked(self, item: QTableWidgetItem) -> None:
        if item.column() != self.COL_USE:
            return
        row = item.row()
        if (
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
            and self._last_checkbox_row is not None
        ):
            checked = item.checkState() == Qt.CheckState.Checked
            start, end = sorted((self._last_checkbox_row, row))
            self._updating = True
            try:
                for current in range(start, end + 1):
                    if self.table.isRowHidden(current):
                        continue
                    use_item = self.table.item(current, self.COL_USE)
                    if use_item is None or not (
                        use_item.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    ):
                        continue
                    use_item.setCheckState(
                        Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                    )
                    index = int(use_item.data(Qt.ItemDataRole.UserRole))
                    self.states[index].use = checked
            finally:
                self._updating = False
        self._last_checkbox_row = row
        self._refresh_ui()

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != self.COL_USE:
            return
        index = int(item.data(Qt.ItemDataRole.UserRole))
        self.states[index].use = item.checkState() == Qt.CheckState.Checked
        self._refresh_ui()

    def _category_tags(self, index: int) -> set[str]:
        state = self.states[index]
        if not state.category_typ or not state.category:
            return set()
        return self.snapshot.tags_for_category(state.category_typ, state.category)

    def _all_tags(self, index: int) -> tuple[str, ...]:
        state = self.states[index]
        return tuple(
            sorted(
                self._category_tags(index) | set(state.manual_tags), key=str.casefold
            )
        )

    def _effective_amount(self, index: int) -> tuple[float, str]:
        tx = self.transactions[index]
        state = self.states[index]
        if state.typ == TYP_TWINT_AI:
            return 0.0, "twint_ai"
        base = abs(float(tx.amount))
        if state.typ == TYP_EXPENSES and self.act_net_twint.isChecked():
            match = self.matches.get(index)
            if match is not None:
                return max(0.0, base - match.reimbursement_amount), "twint"
        try:
            allocation, source_tag = self.snapshot.allocation_for_tags(
                self._all_tags(index)
            )
        except ValueError:
            allocation, source_tag = None, ""
        if state.typ == TYP_EXPENSES and allocation is not None:
            return base * allocation / 100.0, source_tag
        return base, ""

    def _state_kind(self, index: int) -> str:
        state = self.states[index]
        if index in self.duplicate_indexes or self._is_learned(index):
            return "duplicates"
        if state.typ == TYP_TWINT_AI:
            return "twint" if state.category else "review"
        if not state.category:
            return "review"
        if index in self.matches and not self.act_net_twint.isChecked():
            return "review"
        if state.confidence and state.confidence < _READY_CONFIDENCE:
            return "review"
        return "ready"

    def _status_text(self, index: int) -> str:
        state = self.states[index]
        kind = self._state_kind(index)
        if index in self.duplicate_indexes:
            return tr("bank_import_v4.status_duplicate")
        if self._is_learned(index):
            return tr("bank_import_v4.status_learned")
        if state.typ == TYP_TWINT_AI:
            return (
                tr("bank_import_v4.status_twint_ready")
                if state.category
                else tr("bank_import_v4.status_choose_category")
            )
        if not state.category:
            return tr("bank_import_v4.status_choose_category")
        match = self.matches.get(index)
        if match is not None:
            if not self.act_net_twint.isChecked():
                return tr("bank_import_v4.status_twint_review")
            effective, _source = self._effective_amount(index)
            return tr("bank_import_v4.status_twint_net").format(
                amount=f"{effective:.2f}"
            )
        effective, source = self._effective_amount(index)
        if source and source not in {"twint", "twint_ai"}:
            return tr("bank_import_v4.status_share_rule").format(
                tag=source, amount=f"{effective:.2f}"
            )
        if kind == "review":
            if state.category and state.confidence:
                return tr("bank_import_v4.status_suggestion").format(
                    confidence=f"{state.confidence * 100:.0f}"
                )
            return tr("bank_import_v4.status_review")
        return tr("bank_import_v4.status_ready")

    def _update_row(self, row: int, index: int) -> None:
        status_item = self.table.item(row, self.COL_STATUS)
        if status_item is not None:
            status_item.setText(self._status_text(index))
            tags = self._all_tags(index)
            if tags:
                status_item.setToolTip(
                    tr("bank_import_v4.tags_tooltip").format(tags=", ".join(tags))
                )
        use_item = self.table.item(row, self.COL_USE)
        if use_item is not None:
            self.states[index].use = use_item.checkState() == Qt.CheckState.Checked

    def _set_filter(self, key: str) -> None:
        self._filter_key = key
        self._apply_filters()

    def _apply_filters(self, _text: str = "") -> None:
        query = (
            self.search_input.text().strip().casefold()
            if hasattr(self, "search_input")
            else ""
        )
        for row in range(self.table.rowCount()):
            use_item = self.table.item(row, self.COL_USE)
            if use_item is None:
                continue
            index = int(use_item.data(Qt.ItemDataRole.UserRole))
            tx = self.transactions[index]
            state = self.states[index]
            kind = self._state_kind(index)
            matches_filter = self._filter_key == "all" or kind == self._filter_key
            if self._filter_key == "twint":
                matches_filter = state.typ == TYP_TWINT_AI or index in self.matches
            haystack = " ".join(
                (
                    tx.booking_date.isoformat(),
                    tx.booking_date.strftime("%d.%m.%Y"),
                    f"{abs(float(tx.amount)):.2f} {tx.currency}",
                    tx.description,
                    tx.counterparty,
                    tx.source_name,
                    state.category,
                    state.category_typ,
                    " ".join(self._all_tags(index)),
                    self._status_text(index),
                )
            ).casefold()
            matches_search = not query or query in haystack
            self.table.setRowHidden(row, not (matches_filter and matches_search))
        self._refresh_ui()

    def _set_visible_checked(self, checked: bool) -> None:
        self._updating = True
        try:
            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    continue
                item = self.table.item(row, self.COL_USE)
                if item is None or not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    continue
                item.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
                index = int(item.data(Qt.ItemDataRole.UserRole))
                self.states[index].use = checked
        finally:
            self._updating = False
        self._refresh_ui()

    def _checked_indexes(self) -> list[int]:
        return [
            index
            for index, state in self.states.items()
            if state.use
            and index not in self.duplicate_indexes
            and not self._is_learned(index)
        ]

    def _set_checked_rows(self, checked: bool) -> None:
        selected = set(self._checked_indexes())
        self._updating = True
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, self.COL_USE)
                if item is None:
                    continue
                index = int(item.data(Qt.ItemDataRole.UserRole))
                if index not in selected or not (
                    item.flags() & Qt.ItemFlag.ItemIsUserCheckable
                ):
                    continue
                item.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
                self.states[index].use = checked
        finally:
            self._updating = False
        self._refresh_ui()

    def _bulk_set_category(self) -> None:
        typ, category = self._decode_category_token(
            self.cmb_bulk_category.currentData()
        )
        if not category:
            return
        checked = self._checked_indexes()
        if not checked:
            return
        self._updating = True
        try:
            for index in checked:
                state = self.states[index]
                state.category_typ = typ
                state.category = category
                state.confidence = 1.0
                state.prediction_method = "manual_bulk"
                if state.typ != TYP_TWINT_AI:
                    state.typ = typ
                row = self._row_for_index(index)
                if row >= 0:
                    combo = self.table.cellWidget(row, self.COL_CATEGORY)
                    if isinstance(combo, QComboBox):
                        wanted = combo.findData(self._category_token(typ, category))
                        if wanted >= 0:
                            combo.setCurrentIndex(wanted)
                    self._update_row(row, index)
        finally:
            self._updating = False
        self._refresh_ui()
        self._apply_filters()

    def _learn_only_candidates(self) -> list[int]:
        """Angehakte Zeilen, deren Typ manuell umschaltbar ist.

        Echte TWINT-Eingaenge bleiben ausgenommen: sie sind per Fachregel immer
        ``TWINT (KI)`` und duerfen nie zu einer Budgetbuchung werden.
        """
        return [
            index
            for index in self._checked_indexes()
            if index not in self.twint_credit_indexes
        ]

    def _toggle_learn_only(self) -> None:
        """Schaltet angehakte Zeilen zwischen "buchen" und "nur lernen" um.

        V4 hat bewusst kein Typ-Steuerelement je Zeile. Ohne diese Massenaktion
        bliebe nur das Abwaehlen der Zeile - dabei geht die Kategorie fuer
        ``ai_twint_memory`` verloren.
        """
        candidates = self._learn_only_candidates()
        if not candidates:
            return
        back_to_booking = all(
            self.states[index].typ == TYP_TWINT_AI for index in candidates
        )
        for index in candidates:
            state = self.states[index]
            if back_to_booking:
                fallback = (
                    TYP_INCOME
                    if float(self.transactions[index].amount) > 0
                    else TYP_EXPENSES
                )
                state.typ = state.category_typ or fallback
            else:
                state.typ = TYP_TWINT_AI
            row = self._row_for_index(index)
            if row >= 0:
                self._update_row(row, index)
        self._refresh_ui()
        self._apply_filters()

    def _edit_tags_for_checked(self) -> None:
        checked = self._checked_indexes()
        if not checked:
            return
        manual_sets = [set(self.states[index].manual_tags) for index in checked]
        selected_any = set().union(*manual_sets) if manual_sets else set()
        selected_all = set.intersection(*manual_sets) if manual_sets else set()
        dialog = TagSelectionDialog(
            self.tags,
            selected_all=selected_all,
            selected_any=selected_any,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        # Der Tag-Dialog darf neue Tags anlegen. Ohne diesen frischen Snapshot
        # kennt die Analyse sie nicht, und der Import bräche mit "Tag existiert
        # nicht" ab, obwohl der Nutzer ihn gerade selbst erstellt hat.
        self._capture_snapshot()
        decisions = dialog.tag_states()
        for index in checked:
            manual = set(self.states[index].manual_tags)
            for name, decision in decisions.items():
                if decision == Qt.CheckState.Checked:
                    manual.add(name)
                elif decision == Qt.CheckState.Unchecked:
                    manual.discard(name)
            self.states[index].manual_tags = manual
            row = self._row_for_index(index)
            if row >= 0:
                self._update_row(row, index)
        self._refresh_ui()
        self._apply_filters()

    def _twint_option_changed(self, _checked: bool) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_USE)
            if item is not None:
                self._update_row(row, int(item.data(Qt.ItemDataRole.UserRole)))
        self._apply_filters()

    def _sort_view(self, mode: str) -> None:
        if not self.transactions:
            return

        def key(index: int):
            tx = self.transactions[index]
            state = self.states[index]
            if mode in {"date_desc", "date_asc"}:
                return tx.booking_date
            if mode in {"amount_desc", "amount_asc"}:
                return abs(float(tx.amount))
            if mode == "text_asc":
                return str(tx.description or tx.counterparty or "").casefold()
            if mode == "category_asc":
                return str(state.category or "").casefold()
            if mode == "tags_asc":
                return ", ".join(self._all_tags(index)).casefold()
            if mode == "source_asc":
                return str(tx.source_name or "").casefold()
            return index

        reverse = mode in {"date_desc", "amount_desc"}
        self._view_order = sorted(
            range(len(self.transactions)), key=key, reverse=reverse
        )
        self._last_checkbox_row = None
        self._populate_table()

    def _rebuild_sources_menu(self) -> None:
        menu = QMenu(self.btn_sources)
        for source in self.sources:
            action = QAction(
                f"✕  {Path(source.path).name}  ({len(source.transactions)})", menu
            )
            action.triggered.connect(
                lambda _checked=False, path=source.path: self._remove_source(path)
            )
            menu.addAction(action)
        if self.sources:
            menu.addSeparator()
        add_more = QAction(tr("bank_import_v4.add_more_files"), menu)
        add_more.triggered.connect(self.open_file)
        menu.addAction(add_more)
        self.btn_sources.setMenu(menu)
        count = len(self.sources)
        self.btn_sources.setText(
            tr("bank_import_v4.files_loaded").format(
                files=count, rows=len(self.transactions)
            )
        )
        self.btn_sources.setVisible(bool(self.sources))

    def _remove_source(self, path: str) -> None:
        self.sources = [source for source in self.sources if source.path != path]
        if not self.sources:
            self.transactions = []
            self._transaction_digests = []
            self.duplicate_indexes.clear()
            self.twint_credit_indexes.clear()
            self.marked_twint_indexes.clear()
            self.ai_marker_indexes.clear()
            self.matches.clear()
            self.states.clear()
            self._view_order = []
            self.table.setRowCount(0)
            self.btn_sources.setVisible(False)
            self._refresh_ui()
            return
        self._rebuild_from_sources()

    def _refresh_ui(self) -> None:
        counts = {
            "all": len(self.transactions),
            "review": 0,
            "ready": 0,
            "duplicates": 0,
            "twint": 0,
        }
        for index in range(len(self.transactions)):
            kind = self._state_kind(index) if index in self.states else "review"
            if kind in counts:
                counts[kind] += 1
            if index in self.states and (
                self.states[index].typ == TYP_TWINT_AI or index in self.matches
            ):
                counts["twint"] += 1
        labels = {
            "all": tr("bank_import_v4.filter_all"),
            "review": tr("bank_import_v4.filter_review"),
            "ready": tr("bank_import_v4.filter_ready"),
            "duplicates": tr("bank_import_v4.filter_duplicates"),
            "twint": tr("bank_import_v4.filter_twint"),
        }
        for key, button in self.filter_buttons.items():
            button.setText(f"{labels[key]} {counts[key]}")

        checked = self._checked_indexes()
        budget_count = sum(
            1 for index in checked if self.states[index].typ != TYP_TWINT_AI
        )
        twint_count = sum(
            1 for index in checked if self.states[index].typ == TYP_TWINT_AI
        )
        unresolved = sum(1 for index in checked if not self.states[index].category)
        self._set_bulk_visible(bool(checked))
        candidates = self._learn_only_candidates()
        learn_only_active = bool(candidates) and all(
            self.states[index].typ == TYP_TWINT_AI for index in candidates
        )
        self.btn_learn_only.setEnabled(bool(candidates))
        self.btn_learn_only.setText(
            tr("bank_import_v4.book_again")
            if learn_only_active
            else tr("bank_import_v4.learn_only")
        )
        self.lbl_bulk.setText(
            tr("bank_import_v4.selected_count").format(count=len(checked))
        )
        self.btn_import.setEnabled(bool(checked) and unresolved == 0)
        if checked:
            self.btn_import.setText(
                tr("bank_import_v4.import_button").format(
                    count=budget_count, ai=twint_count
                )
            )
        else:
            self.btn_import.setText(tr("bank_import_v4.import_button_empty"))
        self.lbl_summary.setText(
            tr("bank_import_v4.summary").format(
                total=len(self.transactions),
                review=counts["review"],
                ready=counts["ready"],
                duplicate=counts["duplicates"],
            )
        )
        self.lbl_headline.setText(
            tr("bank_import_v4.review_hint").format(count=counts["review"])
            if self.transactions
            else tr("bank_import_v4.empty_hint")
        )
        self.btn_add_files.setText(
            tr("bank_import_v4.add_more")
            if self.sources
            else tr("bank_import_v4.add_files")
        )

        # Waehrend der Analyse bleibt das Fenster bedienbar - Rollen, Suchen,
        # Sortieren gehen weiter. Nur was die Pruefliste selbst umbaut, ruht
        # solange, sonst liefen zwei Rechnungen gegeneinander.
        # Waehrend des finalen Imports ruht dagegen alles: Die Schleife pumpt
        # die Ereignisse, damit der Abbrechen-Knopf ankommt - jeder andere
        # Klick traefe eine Pruefliste, die gerade geschrieben wird.
        busy = self.analysis_running()
        self.btn_add_files.setEnabled(not busy and not self._import_running)
        self.btn_sources.setEnabled(not busy and not self._import_running)
        if busy or self._import_running:
            self.btn_import.setEnabled(False)
        if self._import_running:
            self.table.setEnabled(False)
            self.btn_learn_only.setEnabled(False)
        else:
            self.table.setEnabled(True)

    def _build_item(self, index: int) -> BankImportItem | None:
        state = self.states[index]
        if (
            not state.use
            or state.typ == TYP_TWINT_AI
            or index in self.duplicate_indexes
        ):
            return None
        if not state.category or state.category_typ not in {TYP_EXPENSES, TYP_INCOME}:
            raise ValueError(tr("bank_import_v4.error_category").format(row=index + 1))
        tx = self.transactions[index]
        amount, allocation_source = self._effective_amount(index)
        if amount <= 0:
            return None
        tags = self._all_tags(index)
        details = tx.description
        if tx.counterparty and tx.counterparty.casefold() not in details.casefold():
            details = f"{details} | {tx.counterparty}"
        if tx.source_kind == "credit_card_csv":
            original_amount = str(tx.raw.get("OriginalAmount", "") or "").strip()
            original_currency = str(tx.raw.get("OriginalCurrency", "") or "").strip()
            transaction_id = str(tx.raw.get("TransactionId", "") or "").strip()
            if original_amount or original_currency:
                details += f" | Original {original_amount} {original_currency}".rstrip()
            if transaction_id:
                details += f" | Karten-ID {transaction_id}"
        match = self.matches.get(index)
        if state.typ == TYP_EXPENSES and match and self.act_net_twint.isChecked():
            details += (
                f" | Bankimport: Original {abs(float(tx.amount)):.2f} {tx.currency}; "
                f"TWINT-Erstattung {match.reimbursement_amount:.2f}; "
                f"Eigenanteil {match.personal_share_percent:.2f}%"
            )
        elif (
            state.typ == TYP_EXPENSES
            and allocation_source
            and allocation_source != "twint"
        ):
            allocation, _tag = self.snapshot.allocation_for_tags(tags)
            if allocation is not None:
                details += (
                    f" | Bankimport: Original {abs(float(tx.amount)):.2f} {tx.currency}; "
                    f"Tag-Regel {allocation_source} {allocation:.2f}%"
                )
        return BankImportItem(
            transaction=tx,
            typ=state.category_typ,
            category=state.category,
            tags=tags,
            amount=amount,
            details=details,
            # Der Prueflistenvermerk ist der einzige Beleg dafuer, wie diese
            # Kategorie zustande kam. Was daraus als Lernquelle folgt, steht
            # in model/ai_learning_source.py - der Dialog erfindet hier nichts.
            learn_source=source_from_prediction_method(state.prediction_method),
        )

    def import_selected(self) -> None:
        if self._import_running:
            # Waehrend des Imports pumpt die Schleife die Ereignisse, damit der
            # Abbrechen-Knopf ankommt. Ein zweiter Klick auf "Importieren"
            # kaeme denselben Weg - und wuerde die Bloecke doppelt schreiben.
            return
        checked = self._checked_indexes()
        if not checked:
            show_info(
                self,
                tr("bank_import.window_title"),
                tr("bank_import_v4.nothing_selected"),
            )
            return
        plan_groups: dict[str, list[BankImportItem]] = defaultdict(list)
        twint_groups: dict[str, list[TwintClassification]] = defaultdict(list)
        ai_groups: dict[str, list[TwintClassification]] = defaultdict(list)
        try:
            for index in checked:
                state = self.states[index]
                digest = self._digest_for_index(index)
                if state.typ == TYP_TWINT_AI:
                    if not state.category:
                        raise ValueError(
                            tr("bank_import_v4.error_twint_category").format(
                                row=index + 1
                            )
                        )
                    # Echte TWINT-Eingaenge tragen ``twint_credit``; manuell auf
                    # "nur lernen" gesetzte Zeilen tragen ``twint_ai``. Der
                    # Primaerschluessel laesst genau einen Marker je Zeile zu.
                    eintrag = (
                        self.transactions[index],
                        state.category_typ,
                        state.category,
                        source_from_prediction_method(state.prediction_method),
                    )
                    if index in self.twint_credit_indexes:
                        twint_groups[digest].append(eintrag)
                    else:
                        ai_groups[digest].append(eintrag)
                    continue
                item = self._build_item(index)
                if item is not None:
                    plan_groups[digest].append(item)
        except ValueError as exc:
            show_warning(self, tr("bank_import_v4.review_title"), str(exc))
            return

        budget_count = sum(len(group) for group in plan_groups.values())
        twint_count = sum(len(group) for group in twint_groups.values()) + sum(
            len(group) for group in ai_groups.values()
        )
        answer = QMessageBox.question(
            self,
            tr("bank_import_v4.confirm_title"),
            tr("bank_import_v4.confirm_text").format(
                budget=budget_count, ai=twint_count
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        batches = self._plan_import_batches(plan_groups, twint_groups, ai_groups)
        outcome = self._run_import_batches(
            batches, plan_groups, twint_groups, ai_groups
        )

        if outcome.error is not None:
            show_warning(
                self,
                tr(outcome.error_title),
                trf(
                    outcome.error_text,
                    imported=outcome.imported,
                    batches=outcome.completed,
                    error=outcome.error,
                ),
            )
            return
        if outcome.cancelled:
            show_info(
                self,
                tr("bank_import_v4.cancel_title"),
                trf(
                    "bank_import_v4.cancel_text",
                    imported=outcome.imported,
                    batches=outcome.completed,
                    learned=outcome.learned,
                ),
            )
            return

        show_info(
            self,
            tr("bank_import_v4.done_title"),
            tr("bank_import_v4.done_text").format(
                imported=outcome.imported,
                skipped=outcome.skipped,
                learned=outcome.learned,
            ),
        )
        self.accept()

    # ── Finaler Import: ehrlicher Fortschritt ohne zweiten Thread ──
    #
    # Der Import bleibt bewusst im Bedien-Thread. Er schreibt in dieselbe
    # SQLite-Connection, die dieser Thread besitzt; sie in einen Worker zu
    # reichen, verbietet Regel 1.4, und sie fuer den Import aufzutrennen hiesse,
    # eine zweite DB-Architektur neben Autosave und Verschluesselung zu bauen.
    # Ehrlich wird der Fortschritt deshalb anders:
    #
    # * Ein Block ist genau eine Transaktion. Waehrend er laeuft, gibt es
    #   keine seriose Restmenge - also unbestimmter Balken plus die Aussage,
    #   dass der aktuelle Block sicher gespeichert wird (Regel 1.7).
    # * Zwischen zwei Bloecken steht ein gesicherter Stand. Erst dort wird der
    #   Prozentwert gesetzt und der Abbruchwunsch gelesen (Regel 1.8).
    # * Die Bloecke sind nach Datei gruppiert. Ein Abbruch laesst damit ganze
    #   Dateien zurueck, nie eine halbe.

    def import_running(self) -> bool:
        """True, solange die Schreibschleife des finalen Imports laeuft."""
        return self._import_running

    @Slot()
    def _on_progress_cancel_requested(self) -> None:
        """Ein Knopf, zwei Vorgaenge: Analyse-Worker oder Schreibschleife."""
        if self._import_running:
            # Nur ein Wunsch. Gelesen wird er zwischen zwei Bloecken; mitten in
            # einer offenen Transaktion gaebe es nichts Sicheres zu tun.
            self._import_cancel_requested = True
            return
        self.request_analysis_cancel()

    def _plan_import_batches(
        self,
        plan_groups: dict[str, list[BankImportItem]],
        twint_groups: dict[str, list[TwintClassification]],
        ai_groups: dict[str, list[TwintClassification]],
    ) -> list[_ImportBatch]:
        """Ordnet die Schreibbloecke nach Quelle statt nach Art.

        Nach Art gruppiert - erst alle Buchungen, dann alle Marker - waere ein
        Abbruch in der Mitte genau der verbotene Fall: jede Datei halb fertig.
        Nach Quelle gruppiert ist eine Datei vollstaendig geschrieben, bevor die
        naechste beginnt.
        """
        digests: list[str] = []
        for gruppe in (plan_groups, twint_groups, ai_groups):
            for digest in gruppe:
                if digest not in digests:
                    digests.append(digest)
        batches: list[_ImportBatch] = []
        for position, digest in enumerate(digests, start=1):
            for kind, gruppe in (
                (_BATCH_PLAN, plan_groups),
                (_BATCH_TWINT_CREDIT, twint_groups),
                (_BATCH_TWINT_AI, ai_groups),
            ):
                rows = gruppe.get(digest) or []
                if not rows:
                    continue
                batches.append(
                    _ImportBatch(
                        kind=kind,
                        digest=digest,
                        rows=len(rows),
                        file_position=position,
                        file_count=len(digests),
                    )
                )
        return batches

    def _run_import_batches(
        self,
        batches: list[_ImportBatch],
        plan_groups: dict[str, list[BankImportItem]],
        twint_groups: dict[str, list[TwintClassification]],
        ai_groups: dict[str, list[TwintClassification]],
    ) -> _ImportOutcome:
        """Schreibt Block fuer Block und meldet dazwischen den Stand."""
        total = sum(batch.rows for batch in batches)
        outcome = _ImportOutcome()
        self._import_running = True
        self._import_cancel_requested = False
        self.progress_area.start(
            tr("import_progress.phase_import"), cancellable=True, percent=0
        )
        self._refresh_ui()
        geschrieben = 0
        try:
            for batch in batches:
                self._pump_ui()
                if self._import_cancel_requested:
                    outcome.cancelled = True
                    break
                self._show_batch_running(batch)
                try:
                    self._write_batch(
                        batch, plan_groups, twint_groups, ai_groups, outcome
                    )
                except _IMPORT_WRITE_ERRORS as exc:
                    # Der gescheiterte Block ist als Ganzes zurueckgerollt;
                    # dafuer sorgt ``db_transaction``. Was davor liegt, steht
                    # committet und bleibt stehen - jede Datei ganz oder gar nicht.
                    outcome.error = exc
                    outcome.error_title = _BATCH_ERROR_TITLE[batch.kind]
                    outcome.error_text = _BATCH_ERROR_TEXT[batch.kind]
                    break
                outcome.completed += 1
                geschrieben += batch.rows
                self._show_batch_done(batch, geschrieben, total)
        finally:
            self._import_running = False
            self._import_cancel_requested = False
            self.progress_area.stop()
            self._refresh_ui()
        return outcome

    def _write_batch(
        self,
        batch: _ImportBatch,
        plan_groups: dict[str, list[BankImportItem]],
        twint_groups: dict[str, list[TwintClassification]],
        ai_groups: dict[str, list[TwintClassification]],
        outcome: _ImportOutcome,
    ) -> None:
        """Genau eine Transaktion - hier wird nichts aufgeteilt."""
        learn = self.ai_learning_enabled()
        if batch.kind == _BATCH_PLAN:
            result = self.service.import_items(
                plan_groups[batch.digest], document_digest=batch.digest, learn=learn
            )
            outcome.imported += result.imported
            outcome.skipped += result.skipped_duplicates
            return
        gruppe = twint_groups if batch.kind == _BATCH_TWINT_CREDIT else ai_groups
        outcome.learned += self.marker_store.mark_classifications(
            gruppe[batch.digest],
            batch.digest,
            marker_kind=batch.kind,
            learn=learn,
        )

    def _show_batch_running(self, batch: _ImportBatch) -> None:
        """Unbestimmter Balken: waehrend der Transaktion gibt es keine Quote."""
        self.progress_area.set_file_progress(batch.file_position, batch.file_count)
        self.progress_area.set_activity(tr("import_progress.phase_commit"))
        self.progress_area.set_indeterminate()
        self._pump_ui()

    def _show_batch_done(self, batch: _ImportBatch, done: int, total: int) -> None:
        """Zwischen zwei Bloecken steht ein gesicherter Stand - hier zaehlt es."""
        self.progress_area.set_file_progress(batch.file_position, batch.file_count)
        self.progress_area.set_activity(tr("import_progress.phase_import"))
        self.progress_area.set_item_counts(done, total)
        self.progress_area.set_percent(round(done * 100 / total) if total else 100)
        self._pump_ui()

    def _pump_ui(self) -> None:
        """Laesst Qt zeichnen und den Abbrechen-Klick zustellen.

        Der einzige Ersatz fuer einen Worker-Thread, den es hier geben darf.
        Reentranz ist abgesichert: ``import_selected`` kehrt sofort zurueck,
        solange ``_import_running`` steht, ``_refresh_ui`` sperrt die Knoepfe,
        und ``done()`` verweigert das Schliessen waehrend eines Blocks.
        """
        app = QApplication.instance()
        if app is not None:
            app.processEvents()


# ``LoadedSource`` und ``ReviewState`` wohnen seit dem Analyse-Worker im
# Modell; hier bleiben sie als Name stehen, damit bestehende Aufrufer und
# Tests sie weiterhin ueber den Dialog beziehen koennen.
__all__ = [
    "BankImportDialog",
    "LoadedSource",
    "ReviewState",
    "SearchableCategoryCombo",
    "TagSelectionDialog",
]

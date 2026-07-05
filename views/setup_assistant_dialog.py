from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from datetime import date
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QPushButton, QCheckBox, QRadioButton, QButtonGroup, QGroupBox,
    QFileDialog, QMessageBox, QFrame, QFormLayout, QSpinBox, QDoubleSpinBox,
    QListWidget, QListWidgetItem
)

from views.category_excel_io import (
    export_category_template_xlsx,
    import_categories_from_xlsx,
    export_category_template_csv,
    import_categories_from_csv,
)
from views.budget_fill_dialog import BudgetFillDialog
from model.category_model import CategoryModel
from model.budget_model import BudgetModel
from model.crypto import suspend_after_commit_autosave
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS
from utils.icons import get_icon
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from utils.money import (
    get_symbol, format_money,
    NUMBER_FORMATS, NUMBER_FORMAT_CODES,
    set_number_format, get_number_format,
    LANGUAGE_NUMBER_FORMAT_DEFAULTS,
)


@dataclass
class _Step:
    title: str
    widget: QWidget
    on_enter: callable | None = None
    is_blocking: bool = False  # wenn True: Next nur, wenn self._step_done[idx] True ist
    hint_key: str | None = None  # i18n-Key: erklärt, warum "Weiter" gesperrt ist


class SetupAssistantDialog(QDialog):
    """Kurzer First-Start-Guide (nicht modal), der durch Setup & Kernfunktionen führt."""

    def __init__(
        self,
        main_window,
        conn: sqlite3.Connection,
        settings,
        *,
        db_existed_before: bool,
    ):
        super().__init__(main_window)
        self.main_window = main_window
        self.conn = conn
        self.settings = settings
        from model.app_paths import configured_db_path
        self.db_path = configured_db_path(self.settings.get("database_path", "budgetmanager.db"))
        self.db_existed_before = bool(db_existed_before)
        self._cat_model = CategoryModel(conn)
        self._budget_model = BudgetModel(conn)
        self._tracking_model = TrackingModel(conn)

        self._cats_done = False
        self._budget_done = False
        self._budget_opened_once = False
        self._budget_done = False

        self.setWindowTitle(tr("dlg.setup_assistant"))
        self.setMinimumWidth(520)
        # Setup-Assistent bewusst NICHT "immer im Vordergrund" halten.
        # Externe Dialoge wie Kategorien-Manager oder Budget-Fenster sollen
        # normal davor liegen können und nicht vom Setup verdeckt werden.
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setModal(False)

        root = QHBoxLayout(self)

        # ── Linke Seite: Schritt-Übersicht (Sidebar) ──────────────
        self.step_list = QListWidget()
        self.step_list.setFixedWidth(190)
        self.step_list.setFocusPolicy(Qt.NoFocus)
        self.step_list.itemClicked.connect(self._on_sidebar_clicked)

        # ── Rechte Seite: Header, Seiten, Navigation ──────────────
        right = QVBoxLayout()

        self.lbl_header = QLabel()
        self.lbl_header.setWordWrap(True)
        self.lbl_header.setTextFormat(Qt.RichText)

        self.stack = QStackedWidget()

        # Hinweis, warum "Weiter" gesperrt ist (nur sichtbar bei Blockern)
        self.lbl_next_hint = QLabel()
        self.lbl_next_hint.setWordWrap(True)
        self.lbl_next_hint.setTextFormat(Qt.RichText)
        self.lbl_next_hint.setVisible(False)

        nav = QHBoxLayout()
        self.btn_back = QPushButton(tr("setup.zurueck"))
        self.btn_next = QPushButton(tr("setup.btn_next"))
        self.btn_finish = QPushButton(tr("setup.btn_finish"))
        self.btn_finish.setVisible(False)

        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_finish.clicked.connect(self._finish)

        # v2.2.5 (Führung): "Weiter"/"Fertig" sind Default-Buttons – Enter löst
        # sie aus und sie werden als primäre Aktion hervorgehoben. "Zurück"
        # darf nie versehentlich per Enter feuern.
        self.btn_next.setDefault(True)
        self.btn_next.setAutoDefault(True)
        self.btn_finish.setDefault(True)
        self.btn_finish.setAutoDefault(True)
        self.btn_back.setAutoDefault(False)

        nav.addWidget(self.btn_back)
        nav.addStretch(1)
        nav.addWidget(self.btn_next)
        nav.addWidget(self.btn_finish)

        right.addWidget(self.lbl_header)
        right.addWidget(self._hline())
        right.addWidget(self.stack, 1)
        right.addWidget(self._hline())
        right.addWidget(self.lbl_next_hint)
        right.addLayout(nav)

        root.addWidget(self.step_list)
        root.addLayout(right, 1)

        # Steps
        self.steps: list[_Step] = []
        self._step_done: list[bool] = []
        self._visited: set[int] = set()
        self._finishing: bool = False

        self._build_steps()

        for st in self.steps:
            self.stack.addWidget(st.widget)

        self._build_sidebar()

        # Branch-Sichtbarkeit (Kategorien-Manager vs. Excel-Import) live nachführen
        self.rb_cat_manager.toggled.connect(lambda _: self._refresh_sidebar())

        self._set_step(0)

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    # ---------------------------------------------------------------------
    # Sidebar (Schritt-Übersicht)
    # ---------------------------------------------------------------------
    # Indizes der beiden alternativen Kategorien-Schritte (Branch)
    # Schritt-Indizes (symbolisch statt hartcodiert – robust gegen Reihenfolge-Änderungen)
    # 0=mode 1=db 2=number_format 3=cat_method 4=cat_manager 5=cat_excel 6=budget_starter ...
    _IDX_CAT_METHOD = 3
    _IDX_CAT_MANAGER = 4
    _IDX_CAT_EXCEL = 5
    _IDX_BUDGET_STARTER = 6
    _IDX_BUDGET_LOAD = 7
    _IDX_TRACKING_FIRST = 9

    def _branch_hidden_idx(self) -> int:
        """Index des aktuell NICHT gewählten Kategorien-Schritts."""
        if getattr(self, "rb_cat_excel", None) is not None and self.rb_cat_excel.isChecked():
            return self._IDX_CAT_MANAGER
        return self._IDX_CAT_EXCEL

    def _visible_indices(self) -> list[int]:
        """Schritt-Indizes in Navigationsreihenfolge ohne den inaktiven Branch."""
        hidden = self._branch_hidden_idx()
        return [i for i in range(len(self.steps)) if i != hidden]

    def _build_sidebar(self) -> None:
        self.step_list.clear()
        for i, st in enumerate(self.steps):
            item = QListWidgetItem(st.title)
            item.setData(Qt.UserRole, i)
            self.step_list.addItem(item)
        self._refresh_sidebar()

    def _refresh_sidebar(self) -> None:
        """Aktualisiert Haken, Hervorhebung, Branch-Sichtbarkeit und Klickbarkeit."""
        cur = self._current_idx()
        hidden = self._branch_hidden_idx()
        visible = self._visible_indices()
        for row in range(self.step_list.count()):
            item = self.step_list.item(row)
            idx = int(item.data(Qt.UserRole))
            st = self.steps[idx]

            item.setHidden(idx == hidden)

            pos = (visible.index(idx) + 1) if idx in visible else 0
            done = bool(self._step_done[idx]) and idx in self._visited
            mark = "✓" if done else f"{pos}."
            item.setText(f"{mark}  {st.title}")

            f = item.font()
            f.setBold(idx == cur)
            item.setFont(f)

            # Nur bereits besuchte Schritte sind anklickbar (Zurückspringen)
            clickable = idx in self._visited and idx != cur
            flags = Qt.ItemIsEnabled if clickable or idx == cur else Qt.NoItemFlags
            item.setFlags(flags)

        # Aktuellen Schritt in der Liste markieren (ohne Selektion zu erlauben)
        for row in range(self.step_list.count()):
            item = self.step_list.item(row)
            if int(item.data(Qt.UserRole)) == cur:
                self.step_list.setCurrentItem(item)
                break

    def _on_sidebar_clicked(self, item: QListWidgetItem) -> None:
        idx = int(item.data(Qt.UserRole))
        if idx in self._visited and idx != self._current_idx():
            self._set_step(idx)

    @contextmanager
    def _setup_hidden_while_child_open(self):
        """Versteckt den Setup-Assistenten kurz, solange ein Kinddialog offen ist.

        Der Setup-Assistent ist ein Begleiter, nicht der eigentliche Arbeitsdialog.
        Wenn daraus z. B. Kategorien-Manager, Budget-Fenster oder Tracking-Dialog
        geöffnet werden, soll dieses Fenster nicht davor liegen und die Arbeit
        verdecken. Nach dem Schließen des Kinddialogs erscheint der Assistent wieder.
        """
        was_visible = self.isVisible()
        try:
            if was_visible:
                self.hide()
            yield
        finally:
            if was_visible and not getattr(self, "_finishing", False):
                self.show()
                self.raise_()
                self.activateWindow()

    def _mk_page(self, title: str, body_html: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        t = QLabel(trf('auto.views_setup_assistant_dialog.239_h3_value_0_h3_63ad18ac', value_0=(title)))
        t.setTextFormat(Qt.RichText)
        lay.addWidget(t)

        b = QLabel(body_html)
        b.setTextFormat(Qt.RichText)
        b.setWordWrap(True)
        lay.addWidget(b)
        lay.addStretch(1)
        return w

    # ---------------------------------------------------------------------
    # Build pages
    # ---------------------------------------------------------------------
    def _build_steps(self) -> None:
        self._build_step_mode()
        self._build_step_db()
        self._build_step_number_format()
        self._build_step_cat_method()
        self._build_step_cat_manager()
        self._build_step_cat_excel()
        self._build_step_budget_starter()
        self._build_step_budget_load()
        self._build_step_budget_explain()
        self._build_step_tracking_first()
        self._build_step_tracking_fix()
        self._build_step_finish()

        self._step_done = [False] * len(self.steps)
        for i, st in enumerate(self.steps):
            self._step_done[i] = not st.is_blocking

        self._verify_step_indices()

    def _verify_step_indices(self) -> None:
        """Warnt früh, falls symbolische Schritt-Indizes nicht mehr zur UI-Reihenfolge passen."""
        expected = {
            self._IDX_CAT_METHOD: getattr(self, "page_cat_method", None),
            self._IDX_CAT_MANAGER: getattr(self, "page_cat_manager", None),
            self._IDX_CAT_EXCEL: getattr(self, "page_cat_excel", None),
            self._IDX_BUDGET_STARTER: getattr(self, "page_budget_starter", None),
            self._IDX_BUDGET_LOAD: getattr(self, "page_budget_load", None),
            self._IDX_TRACKING_FIRST: getattr(self, "page_tracking_first", None),
        }
        for idx, page in expected.items():
            if page is None or idx >= len(self.steps) or self.steps[idx].widget is not page:
                logger.warning("Setup-Assistent: Step-Index %d passt nicht zur erwarteten Seite.", idx)

    # ── Step-Builder ─────────────────────────────────────────────

    def _build_step_mode(self) -> None:
        """1) Guided vs. unguided."""
        self.page_mode = QWidget()
        lay = QVBoxLayout(self.page_mode)
        lay.addWidget(QLabel("<h3>" + tr("setup.setup_mode_title") + "</h3>"))
        info = QLabel(tr("setup.setup_mode_intro"))
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        lay.addWidget(info)
        self.cb_guided = QCheckBox(tr("chk.guided_setup"))
        self.cb_guided.setChecked(True)
        self.cb_show_on_start = QCheckBox(tr("chk.show_onboarding"))
        self.cb_show_on_start.setChecked(bool(self.settings.get("show_onboarding", True)))
        lay.addWidget(self.cb_guided)
        lay.addWidget(self.cb_show_on_start)
        lay.addStretch(1)
        # v2.2.2 (open-tasks): Express-Einrichtung – für "erst tracken,
        # Budget später lernen": Standard-Kategorien (falls DB leer),
        # Lernmodus an, alle optionalen Schritte übersprungen.
        self.btn_express = QPushButton("⚡ " + tr("setup.express_button"))
        self.btn_express.setToolTip(tr("setup.express_tip"))
        self.btn_express.clicked.connect(self._express_setup)
        lay.addWidget(self.btn_express)

        self.steps.append(_Step(tr("setup.nav_mode"), self.page_mode))

    def _build_step_db(self) -> None:
        """2) Datenbank-Check."""
        self.page_db = QWidget()
        lay = QVBoxLayout(self.page_db)
        lay.addWidget(QLabel("<h3>" + tr("setup.step2_title") + "</h3>"))
        exists_txt = tr("setup.setup_db_exists") if self.db_existed_before else tr("setup.setup_db_not_exists")
        self.lbl_db = QLabel(
            f"<b>{tr('setup.setup_db_path')}:</b> {self.db_path}<br>"
            f"<b>{tr('setup.setup_db_existed')}:</b> {exists_txt}<br><br>"
            + tr("setup.setup_db_desc")
        )
        self.lbl_db.setTextFormat(Qt.RichText)
        self.lbl_db.setWordWrap(True)
        lay.addWidget(self.lbl_db)
        
        # Restore + Reset buttons
        from PySide6.QtWidgets import QPushButton, QHBoxLayout
        btn_row = QHBoxLayout()
        btn_restore = QPushButton(tr("setup.setup_db_restore"))
        btn_restore.setIcon(get_icon("💾"))
        btn_restore.clicked.connect(self._do_restore_backup)
        btn_reset = QPushButton(tr("setup.setup_db_reset"))
        btn_reset.setIcon(get_icon("🗑️"))
        btn_reset.clicked.connect(self._do_reset_database)
        btn_row.addWidget(btn_restore)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_db"), self.page_db))

    def _build_step_number_format(self) -> None:
        """2b) Zahlenformat (Dezimal-/Tausendertrennung) wählen."""
        from PySide6.QtWidgets import QComboBox
        self.page_number_format = QWidget()
        lay = QVBoxLayout(self.page_number_format)
        lay.addWidget(QLabel("<h3>" + tr("setup.numfmt_title") + "</h3>"))

        info = QLabel(tr("setup.numfmt_intro"))
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        lay.addWidget(info)

        form = QFormLayout()
        self.cmb_number_format = QComboBox()
        for code in NUMBER_FORMAT_CODES:
            self.cmb_number_format.addItem(NUMBER_FORMATS[code]["label"], code)

        # Vorauswahl: gespeicherter Wert, sonst Sprach-Default
        current = str(self.settings.get("number_format", "") or "")
        if current not in NUMBER_FORMATS:
            lang = str(self.settings.get("language", "de") or "de").lower()[:2]
            current = LANGUAGE_NUMBER_FORMAT_DEFAULTS.get(lang, "swiss")
        idx = self.cmb_number_format.findData(current)
        self.cmb_number_format.setCurrentIndex(max(0, idx))

        form.addRow(tr("setup.numfmt_label"), self.cmb_number_format)
        lay.addLayout(form)

        # Live-Vorschau
        self.lbl_numfmt_preview = QLabel()
        self.lbl_numfmt_preview.setTextFormat(Qt.RichText)
        self.lbl_numfmt_preview.setStyleSheet("padding: 8px; font-size: 14px;")
        lay.addWidget(self.lbl_numfmt_preview)

        self.cmb_number_format.currentIndexChanged.connect(self._on_number_format_changed)
        # initial anwenden (persistiert sofort, damit auch bei direktem Weiter korrekt)
        self._on_number_format_changed()

        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_number_format"), self.page_number_format))

    def _on_number_format_changed(self, *_args) -> None:
        """Wendet das gewählte Zahlenformat sofort an und aktualisiert die Vorschau."""
        code = self.cmb_number_format.currentData() or "swiss"
        set_number_format(code)
        try:
            from utils.qt_translator import apply_number_locale
            apply_number_locale(code)
        except Exception as e:
            logger.debug("QLocale konnte nicht gesetzt werden: %s", e)
        try:
            self.settings.set("number_format", code)
        except Exception as e:
            logger.debug("number_format konnte nicht gespeichert werden: %s", e)
        sample = format_money(1234567.89, currency=str(self.settings.get("currency", "CHF")))
        sample_neg = format_money(-49.5, currency=str(self.settings.get("currency", "CHF")))
        self.lbl_numfmt_preview.setText(
            f"<b>{tr('setup.numfmt_preview')}:</b> {sample} &nbsp;·&nbsp; {sample_neg}"
        )

    def _build_step_cat_method(self) -> None:
        """3) Kategorien-Methode wählen."""
        self.page_cat_method = QWidget()
        lay = QVBoxLayout(self.page_cat_method)
        lay.addWidget(QLabel("<h3>" + tr("setup.step3_title") + "</h3>"))
        try:
            cnt = self._cat_model.count()
        except Exception:
            cnt = 0
        hint = QLabel(tr("setup.cat_method_hint"))
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        lay.addWidget(hint)
        gb = QGroupBox(tr("setup.cat_method_box"))
        vb = QVBoxLayout(gb)
        self.rb_cat_manager = QRadioButton(tr("radio.cat_manager"))
        self.rb_cat_excel = QRadioButton(tr("radio.cat_excel"))
        self.rb_cat_manager.setChecked(True)
        vb.addWidget(self.rb_cat_manager)
        vb.addWidget(self.rb_cat_excel)
        lay.addWidget(gb)
        self.cb_clean_start = QCheckBox(trf("setup.clean_start_vorhandene_kategorien", cnt=cnt))
        allow_clean = self._is_safe_to_reset()
        self.cb_clean_start.setEnabled(bool(allow_clean and cnt > 0))
        if not allow_clean and cnt > 0:
            self.cb_clean_start.setToolTip(tr("setup.dein_budgettracking_enthaelt_bereits"))
        lay.addWidget(self.cb_clean_start)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_cat_method"), self.page_cat_method))

    def _build_step_cat_manager(self) -> None:
        """4.1) Kategorien-Manager."""
        self.page_cat_manager = QWidget()
        lay = QVBoxLayout(self.page_cat_manager)
        lay.addWidget(QLabel("<h3>" + tr("setup.step4_cat_manager") + "</h3>"))
        desc = QLabel(tr("setup.klicke_auf_boeffnenb_lege"))
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_open_cat_manager = QPushButton(tr("setup.open_cat_manager"))
        self.btn_open_cat_manager.clicked.connect(self._open_category_manager)
        lay.addWidget(self.btn_open_cat_manager)
        self.lbl_cat_done_1 = QLabel(tr("setup.smallnoch_nicht_abgeschlossensmall"))
        self.lbl_cat_done_1.setTextFormat(Qt.RichText)
        self.lbl_cat_done_1.setWordWrap(True)
        lay.addWidget(self.lbl_cat_done_1)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_cat_manager"), self.page_cat_manager,
                                is_blocking=True, hint_key="setup.hint_locked_cat_manager"))

    def _build_step_cat_excel(self) -> None:
        """4.2) Excel-Import."""
        self.page_cat_excel = QWidget()
        lay = QVBoxLayout(self.page_cat_excel)
        lay.addWidget(QLabel("<h3>" + tr("setup.step4_excel") + "</h3>"))
        desc = QLabel(tr("setup.excel_desc"))
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_export_template = QPushButton(tr("setup.export_template"))
        self.btn_export_template.clicked.connect(self._export_template)
        lay.addWidget(self.btn_export_template)
        self.btn_export_template_csv = QPushButton(tr("setup.export_template") + " (CSV)")
        self.btn_export_template_csv.clicked.connect(self._export_template_csv)
        lay.addWidget(self.btn_export_template_csv)
        self.btn_import_template = QPushButton(tr("setup.import_template"))
        self.btn_import_template.clicked.connect(self._import_from_excel)
        lay.addWidget(self.btn_import_template)
        self.lbl_cat_done_2 = QLabel(tr("setup.smallnoch_nicht_abgeschlossensmall"))
        self.lbl_cat_done_2.setTextFormat(Qt.RichText)
        self.lbl_cat_done_2.setWordWrap(True)
        lay.addWidget(self.lbl_cat_done_2)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_cat_excel"), self.page_cat_excel,
                                is_blocking=True, hint_key="setup.hint_locked_cat_excel"))

    def _build_step_budget_starter(self) -> None:
        """5) Budget-Grundgerüst/Vorlage anlegen."""
        self.page_budget_starter = QWidget()
        lay = QVBoxLayout(self.page_budget_starter)
        lay.addWidget(QLabel(tr("setup.budget_starter_title")))

        desc = QLabel(tr("setup.budget_starter_desc"))
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        form = QFormLayout()
        self.spin_budget_year = QSpinBox()
        self.spin_budget_year.setRange(2000, 2100)
        self.spin_budget_year.setValue(date.today().year)
        form.addRow(tr("setup.budget_year"), self.spin_budget_year)

        self.cb_seed_all_budget = QCheckBox(tr("setup.seed_all_budget_rows"))
        self.cb_seed_all_budget.setChecked(True)
        form.addRow("", self.cb_seed_all_budget)

        self.cb_overwrite_budget = QCheckBox(tr("setup.overwrite_existing_budget"))
        self.cb_overwrite_budget.setChecked(False)
        form.addRow("", self.cb_overwrite_budget)
        lay.addLayout(form)

        learning_box = QGroupBox(tr("budget_learning.setup.title"))
        learning_form = QFormLayout(learning_box)
        self.cb_setup_learning_enabled = QCheckBox(tr("settings.tracking_budget_learning"))
        self.cb_setup_learning_enabled.setChecked(bool(self.settings.get("tracking_budget_learning_enabled", True)))
        self.cb_setup_learning_enabled.setToolTip(tr("settings.tracking_budget_learning_tip"))
        # v2.1.7 Blocker-Fix: Bei aktivem Lernmodus darf der Budget-Ausfüllschritt
        # nicht hart blockieren ("erst tracken, Budget später lernen").
        self.cb_setup_learning_enabled.toggled.connect(
            lambda _=None: self._recompute_budget_done()
        )
        learning_form.addRow("", self.cb_setup_learning_enabled)

        self.spn_setup_learning_proposal = QSpinBox()
        self.spn_setup_learning_proposal.setRange(1, 12)
        self.spn_setup_learning_proposal.setValue(int(self.settings.get("tracking_budget_learning_proposal_months", 2) or 2))
        self.spn_setup_learning_proposal.setSuffix(" " + tr("settings.months_suffix"))
        learning_form.addRow(tr("settings.tracking_learning_proposal"), self.spn_setup_learning_proposal)

        self.spn_setup_learning_stable = QSpinBox()
        self.spn_setup_learning_stable.setRange(1, 12)
        self.spn_setup_learning_stable.setValue(int(self.settings.get("tracking_budget_learning_stable_months", 3) or 3))
        self.spn_setup_learning_stable.setSuffix(" " + tr("settings.months_suffix"))
        learning_form.addRow(tr("settings.tracking_learning_stable"), self.spn_setup_learning_stable)

        self.cb_setup_learning_projection = QCheckBox(tr("settings.tracking_learning_projection"))
        self.cb_setup_learning_projection.setChecked(bool(self.settings.get("tracking_budget_learning_include_current_month_projection", True)))
        learning_form.addRow("", self.cb_setup_learning_projection)

        hint = QLabel(tr("budget_learning.setup.hint"))
        hint.setWordWrap(True)
        learning_form.addRow(hint)
        lay.addWidget(learning_box)

        amounts_box = QGroupBox(tr("setup.budget_quick_amounts"))
        amounts = QFormLayout(amounts_box)

        self.spn_income_salary = self._money_spin(0)
        self.spn_exp_rent = self._money_spin(0)
        self.spn_exp_health = self._money_spin(0)
        self.spn_exp_groceries = self._money_spin(0)
        self.spn_exp_taxes = self._money_spin(0)
        self.spn_exp_phone = self._money_spin(0)
        self.spn_exp_transport = self._money_spin(0)
        self.spn_save_emergency = self._money_spin(0)
        self.spn_save_vacation = self._money_spin(0)

        amounts.addRow(tr("setup.amount_salary"), self.spn_income_salary)
        amounts.addRow(tr("setup.amount_rent"), self.spn_exp_rent)
        amounts.addRow(tr("setup.amount_health"), self.spn_exp_health)
        amounts.addRow(tr("setup.amount_groceries"), self.spn_exp_groceries)
        amounts.addRow(tr("setup.amount_taxes"), self.spn_exp_taxes)
        amounts.addRow(tr("setup.amount_phone"), self.spn_exp_phone)
        amounts.addRow(tr("setup.amount_transport"), self.spn_exp_transport)
        amounts.addRow(tr("setup.amount_emergency"), self.spn_save_emergency)
        amounts.addRow(tr("setup.amount_vacation"), self.spn_save_vacation)
        lay.addWidget(amounts_box)

        btn_row = QHBoxLayout()
        self.btn_create_empty_budget_year = QPushButton(tr("setup.create_empty_budget_year"))
        self.btn_create_empty_budget_year.clicked.connect(self._create_empty_budget_year)
        self.btn_apply_budget_template = QPushButton(tr("setup.apply_budget_template"))
        self.btn_apply_budget_template.clicked.connect(self._apply_budget_template)
        btn_row.addWidget(self.btn_create_empty_budget_year)
        btn_row.addWidget(self.btn_apply_budget_template)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.lbl_budget_starter_status = QLabel(tr("setup.budget_starter_status_idle"))
        self.lbl_budget_starter_status.setTextFormat(Qt.RichText)
        self.lbl_budget_starter_status.setWordWrap(True)
        lay.addWidget(self.lbl_budget_starter_status)
        lay.addStretch(1)

        self.steps.append(_Step(tr("setup.nav_budget_starter"), self.page_budget_starter))

    def _save_learning_settings_from_setup(self) -> None:
        """Persistiert Lernmodus-Optionen aus dem Erststart-Assistenten."""
        if not hasattr(self, "cb_setup_learning_enabled"):
            return
        self.settings.set("tracking_budget_learning_enabled", bool(self.cb_setup_learning_enabled.isChecked()))
        self.settings.set("tracking_budget_learning_proposal_months", int(self.spn_setup_learning_proposal.value()))
        stable = max(int(self.spn_setup_learning_proposal.value()), int(self.spn_setup_learning_stable.value()))
        self.settings.set("tracking_budget_learning_stable_months", stable)
        self.settings.set("tracking_budget_learning_include_current_month_projection", bool(self.cb_setup_learning_projection.isChecked()))
        self.settings.set("tracking_budget_learning_show_in_report", True)
        self.settings.set("tracking_budget_learning_auto_end", False)

    def _money_spin(self, value: float = 0.0) -> QDoubleSpinBox:
        """Geldbetrag-Feld für den Setup-Assistenten."""
        spn = QDoubleSpinBox()
        spn.setRange(0.0, 999999.0)
        spn.setDecimals(2)
        spn.setSingleStep(50.0)
        spn.setSuffix(f" {get_symbol(str(self.settings.get('currency', 'CHF')))}")
        spn.setValue(float(value))
        return spn

    def _build_step_budget_load(self) -> None:
        """5) Budget-Fenster öffnen."""
        self.page_budget_load = QWidget()
        lay = QVBoxLayout(self.page_budget_load)
        lay.addWidget(QLabel(tr("setup.h36_budget_ausfuellenh3")))
        desc = QLabel(tr("setup.budget_load_desc"))
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_open_budget_window = QPushButton(tr("setup.open_budget_window"))
        self.btn_open_budget_window.clicked.connect(self._open_budget_window)
        lay.addWidget(self.btn_open_budget_window)
        self.lbl_budget_done = QLabel(tr("setup.smallnoch_nicht_geoeffnetsmall"))
        self.lbl_budget_done.setTextFormat(Qt.RichText)
        self.lbl_budget_done.setWordWrap(True)
        lay.addWidget(self.lbl_budget_done)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_budget_fill"), self.page_budget_load,
                                on_enter=self._enter_budget_tab_and_open_budget_window_once,
                                is_blocking=True, hint_key="setup.hint_locked_budget"))

    def _build_step_budget_explain(self) -> None:
        """6) Budget-Tab Erklärung."""
        self.page_budget_explain = self._mk_page(
            tr("setup.step6_title"),
            tr("setup.budget_explain_body"),
        )
        self.steps.append(_Step(tr("setup.nav_budget_explain"), self.page_budget_explain, on_enter=self._enter_budget_tab))

    def _build_step_tracking_first(self) -> None:
        """7) Tracking — erste Buchung."""
        self.page_tracking_first = QWidget()
        lay = QVBoxLayout(self.page_tracking_first)
        lay.addWidget(QLabel("<h3>" + tr("setup.step7_title") + "</h3>"))
        desc = QLabel(tr("setup.tracking_first_desc"))
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_add_first = QPushButton(tr("setup.add_first_booking"))
        self.btn_add_first.clicked.connect(self._open_first_booking)
        lay.addWidget(self.btn_add_first)
        self.lbl_tracking_done = QLabel(tr("setup.tracking_entry_missing"))
        self.lbl_tracking_done.setTextFormat(Qt.RichText)
        self.lbl_tracking_done.setWordWrap(True)
        lay.addWidget(self.lbl_tracking_done)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_tracking_first"), self.page_tracking_first,
                                on_enter=self._enter_tracking_first,
                                is_blocking=True, hint_key="setup.hint_locked_tracking"))

    def _build_step_tracking_fix(self) -> None:
        """8) Tracking — Fixkosten / Wiederkehrend."""
        self.page_tracking_fix = QWidget()
        lay = QVBoxLayout(self.page_tracking_fix)
        lay.addWidget(QLabel("<h3>" + tr("setup.step8_title") + "</h3>"))
        desc = QLabel(tr("setup.tracking_fix_desc"))
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_open_fix = QPushButton(tr("setup.book_fixcosts"))
        self.btn_open_fix.clicked.connect(self._open_fix_dialog)
        lay.addWidget(self.btn_open_fix)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_tracking_fix"), self.page_tracking_fix, on_enter=self._enter_tracking_tab))

    def _build_step_finish(self) -> None:
        """Abschluss-Seite."""
        self.page_finish = QWidget()
        lay = QVBoxLayout(self.page_finish)
        lay.addWidget(QLabel("<h3>" + tr("setup.finished") + "</h3>"))
        done = QLabel(tr("setup.finish_body"))
        done.setTextFormat(Qt.RichText)
        done.setWordWrap(True)
        lay.addWidget(done)
        self.cb_show_on_start_end = QCheckBox(tr("chk.show_onboarding_end"))
        self.cb_show_on_start_end.setChecked(False)
        lay.addWidget(self.cb_show_on_start_end)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.nav_finish"), self.page_finish))

    # ---------------------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------------------
    def _set_step(self, idx: int) -> None:
        idx = max(0, min(idx, len(self.steps) - 1))
        self.stack.setCurrentIndex(idx)
        self._visited.add(idx)
        st = self.steps[idx]
        visible = self._visible_indices()
        pos = (visible.index(idx) + 1) if idx in visible else idx + 1
        total = len(visible)
        self.lbl_header.setText(
            f"<b>{st.title}</b> &nbsp;<small>"
            + trf("setup.progress_step_of", pos=pos, total=total)
            + "</small>"
        )
        if st.on_enter:
            try:
                st.on_enter()
            except Exception as e:
                logger.debug("%s", e)
                # Wizard must not crash UI
                pass
        self._update_nav()
        self._refresh_sidebar()

    def _current_idx(self) -> int:
        return int(self.stack.currentIndex())

    def _update_nav(self) -> None:
        idx = self._current_idx()
        self.btn_back.setEnabled(idx > 0)
        last = idx == (len(self.steps) - 1)
        self.btn_next.setVisible(not last)
        self.btn_finish.setVisible(last)

        # Next enabled?
        can_next = True
        # page 0: if unguided, allow Next (will finish)
        if idx == 0:
            can_next = True
        else:
            can_next = bool(self._step_done[idx])
        self.btn_next.setEnabled(can_next)

        # Erklären, WARUM "Weiter" gesperrt ist – statt nur eines toten Buttons.
        st = self.steps[idx]
        if not can_next and not last:
            hint = tr(st.hint_key) if st.hint_key else tr("setup.hint_locked_generic")
            self.lbl_next_hint.setText(trf('auto.views_setup_assistant_dialog.598_small_value_0_small_c3c36140', value_0=(hint)))
            self.lbl_next_hint.setVisible(True)
        else:
            self.lbl_next_hint.setVisible(False)

        # v2.2.5 (Führung): Default-Button je Seite frisch setzen, damit Enter
        # zuverlässig die primäre Aktion auslöst (Fokus "klebt" sonst nach
        # einem Button-Klick auf der vorigen Seite).
        try:
            if last and self.btn_finish.isEnabled():
                self.btn_finish.setDefault(True)
                self.btn_finish.setFocus()
            elif self.btn_next.isEnabled():
                self.btn_next.setDefault(True)
                self.btn_next.setFocus()
        except Exception as e:
            logger.debug("default button focus: %s", e)

    def _go_back(self) -> None:
        idx = self._current_idx()

        # handle branching back: from cat manager/excel to method page
        if idx in (self._IDX_CAT_MANAGER, self._IDX_CAT_EXCEL):
            self._set_step(self._IDX_CAT_METHOD)
            return

        # from budget starter go back to the selected category path
        if idx == self._IDX_BUDGET_STARTER:
            self._set_step(self._IDX_CAT_EXCEL if self.rb_cat_excel.isChecked() else self._IDX_CAT_MANAGER)
            return

        self._set_step(idx - 1)

    def _go_next(self) -> None:
        idx = self._current_idx()

        # page 0: unguided -> close
        if idx == 0 and not self.cb_guided.isChecked():
            self.settings.set("show_onboarding", bool(self.cb_show_on_start.isChecked()))
            self.settings.set("setup_completed", True)
            self._save_learning_settings_from_setup()
            self.close()
            return

        # category-method page -> branch
        if idx == self._IDX_CAT_METHOD:
            if self.cb_clean_start.isChecked():
                self._reset_categories()
            self._set_step(self._IDX_CAT_EXCEL if self.rb_cat_excel.isChecked() else self._IDX_CAT_MANAGER)
            return

        # after category pages -> budget starter
        if idx in (self._IDX_CAT_MANAGER, self._IDX_CAT_EXCEL):
            self._set_step(self._IDX_BUDGET_STARTER)
            return

        self._set_step(idx + 1)

    def _express_setup(self) -> None:
        """Express-Pfad (v2.2.2): Minimal-Setup ohne die optionalen Seiten.

        - Legt Standard-Kategorien an, falls noch keine existieren.
        - Aktiviert den Tracking-Lernmodus (Budgets entstehen später aus
          echten Buchungen; der Budget-Schritt gilt damit als erfüllt).
        - Markiert alle Schritte als besucht/erledigt und springt zur
          Abschluss-Seite – der Nutzer bestätigt dort mit "Fertig".
        """
        try:
            if QMessageBox.question(
                self,
                tr("setup.express_button"),
                tr("setup.express_confirm"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            ) != QMessageBox.Yes:
                return
            # Standard-Kategorien nur bei leerer Kategorienliste anlegen.
            try:
                n_cats = int(
                    self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
                )
            except Exception:
                n_cats = 0
            if n_cats == 0:
                from model.default_categories import insert_default_categories

                insert_default_categories(self.conn)
                self.conn.commit()
            # Lernmodus aktivieren (erfüllt den Budget-Schritt).
            if getattr(self, "cb_setup_learning_enabled", None) is not None:
                self.cb_setup_learning_enabled.setChecked(True)
            # Alle Schritte als erledigt/besucht markieren, zur letzten Seite.
            for i in range(len(self._step_done)):
                self._step_done[i] = True
                self._visited.add(i)
            self._recompute_budget_done()
            self._recompute_tracking_done()
            for i in range(len(self._step_done)):
                self._step_done[i] = True
            self._set_step(len(self.steps) - 1)
        except Exception as e:
            logger.warning("express setup: %s", e)
            QMessageBox.warning(self, tr("msg.error"), str(e))

    def _finish(self) -> None:
        # Verhindert, dass _setup_hidden_while_child_open() den Dialog
        # nach dem Abschluss wieder anzeigt (Flag wurde bisher nie gesetzt).
        self._finishing = True
        # mark completed and apply "show on start"
        self.settings.set("show_onboarding", bool(self.cb_show_on_start_end.isChecked()))
        self.settings.set("setup_completed", True)
        self._save_learning_settings_from_setup()
        QMessageBox.information(self, tr("msg.info"), tr("setup.finish_done_msg"))
        self.close()


    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        """Beim Schließen: Einstellung tr("chk.show_onboarding") persistieren.

        Wichtig:
        - Nicht automatisch als abgeschlossen markieren (setup_completed bleibt False),
          außer der User hat aktiv 'Fertig' geklickt.
        """
        try:
            if hasattr(self, "cb_show_on_start_end") and self.stack.currentWidget() is self.page_finish:
                self.settings.set("show_onboarding", bool(self.cb_show_on_start_end.isChecked()))
            elif hasattr(self, "cb_show_on_start"):
                self.settings.set("show_onboarding", bool(self.cb_show_on_start.isChecked()))
        except Exception as e:
            logger.debug("if hasattr(self, 'cb_show_on_start_end') and self.: %s", e)
        return super().closeEvent(event)

    # ---------------------------------------------------------------------
    # Enter hooks
    # ---------------------------------------------------------------------
    def keyPressEvent(self, event):  # noqa: N802 (Qt naming)
        """v2.2.5 (Führung): Enter/Return bewegt den Assistenten vorwärts.

        Bisher war "Weiter" kein Default-Button, deshalb passierte auf der
        Willkommensseite (ohne fokussiertes Eingabefeld) bei Enter nichts – der
        Nutzer musste zur Maus greifen. Jetzt löst Enter je nach Seite "Weiter"
        bzw. auf der letzten Seite "Fertig" aus.

        Ausnahme: Steht der Fokus in einem mehrzeiligen Textfeld (QTextEdit/
        QPlainTextEdit), bleibt Enter ein Zeilenumbruch. Modifier (Shift/Strg/
        Alt) werden ebenfalls durchgelassen.
        """
        try:
            from PySide6.QtCore import Qt as _Qt
            from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

            if event.key() in (_Qt.Key_Return, _Qt.Key_Enter) and (
                event.modifiers() == _Qt.NoModifier
            ):
                focus = self.focusWidget()
                if not isinstance(focus, (QTextEdit, QPlainTextEdit)):
                    if self.btn_finish.isVisible() and self.btn_finish.isEnabled():
                        self._finish()
                        return
                    if self.btn_next.isVisible() and self.btn_next.isEnabled():
                        self._go_next()
                        return
                    # Weiter ist gesperrt (Blocker): Hinweis sichtbar lassen,
                    # aber Enter nicht ins Leere laufen lassen.
                    return
        except Exception as e:
            logger.debug("keyPressEvent enter: %s", e)
        super().keyPressEvent(event)

    def _enter_budget_tab(self) -> None:
        try:
            if hasattr(self.main_window, "_goto_tab"):
                self.main_window._goto_tab(self.main_window.budget_tab)
            else:
                self.main_window.tabs.setCurrentWidget(self.main_window.budget_tab)
            # reload view
            if hasattr(self.main_window.budget_tab, "load"):
                self.main_window.budget_tab.load()
            elif hasattr(self.main_window.budget_tab, "refresh"):
                self.main_window.budget_tab.refresh()
        except Exception as e:
            logger.debug("if hasattr(self.main_window, '_goto_tab'):: %s", e)

    def _enter_tracking_tab(self) -> None:
        try:
            if hasattr(self.main_window, "_goto_tab"):
                self.main_window._goto_tab(self.main_window.tracking_tab)
            else:
                self.main_window.tabs.setCurrentWidget(self.main_window.tracking_tab)
            if hasattr(self.main_window.tracking_tab, "refresh"):
                self.main_window.tracking_tab.refresh()
        except Exception as e:
            logger.debug("if hasattr(self.main_window, '_goto_tab'):: %s", e)

    def _enter_tracking_first(self) -> None:
        """Wechselt zur ersten Buchung und berechnet den Pflichtschritt neu.

        Regression v2.0.8 Cockpit: Der Schritt verwies auf diesen Enter-Hook,
        die Methode fehlte jedoch. Dadurch konnte der Setup-Assistent beim
        Erststart nicht konstruiert werden.
        """
        self._enter_tracking_tab()
        self._recompute_tracking_done()

    # ---------------------------------------------------------------------
    # Actions (pages)
    # ---------------------------------------------------------------------
    def _open_category_manager(self) -> None:
        try:
            with self._setup_hidden_while_child_open():
                self.main_window._show_category_manager()
            # manager is modal; when it closes, consider done if there is at least one category
            cnt = self._cat_model.count()
            if cnt <= 0:
                QMessageBox.information(self, tr("msg.info"), tr("setup.no_categories_yet"))
            self._cats_done = True
            self._step_done[self._IDX_CAT_MANAGER] = True
            self.lbl_cat_done_1.setText(tr("setup.cat_manager_done"))
            self._update_nav()
            self.main_window._schedule_refresh_all_tabs(reason="setup assistant changed data") if hasattr(self.main_window, "_schedule_refresh_all_tabs") else self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_cat_manager_failed", e=e))

    def _export_template(self) -> None:
        try:
            folder = QFileDialog.getExistingDirectory(
                self,
                tr("setup.ordner_waehlen_excelvorlage_speichern"),
                str(Path.home()),
            )
            if not folder:
                return
            out = Path(folder) / "Budgetmanager_Kategorien_Template.xlsx"
            export_category_template_xlsx(out)
            QMessageBox.information(
                self,
                tr("msg.info"),
                trf("msg.vorlage_gespeichert", out=out),
            )
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("setup.export_failed", e=e))

    def _export_template_csv(self) -> None:
        try:
            folder = QFileDialog.getExistingDirectory(
                self,
                tr("setup.ordner_waehlen_excelvorlage_speichern"),
                str(Path.home()),
            )
            if not folder:
                return
            out = Path(folder) / "Budgetmanager_Kategorien_Template.csv"
            export_category_template_csv(out)
            QMessageBox.information(
                self,
                tr("msg.info"),
                trf("msg.vorlage_gespeichert", out=out),
            )
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("setup.export_failed", e=e))

    def _import_from_excel(self) -> None:
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                tr("setup.kategorienexcel_auswaehlen"),
                str(Path.home()),
                tr("setup.categories_file_filter"),
            )
            if not file_path:
                return
            if Path(file_path).suffix.lower() == ".csv":
                res = import_categories_from_csv(self.conn, Path(file_path))
            else:
                res = import_categories_from_xlsx(self.conn, Path(file_path))
            msg = trf(
                "setup.import_summary",
                inserted=res.inserted, updated=res.updated, skipped=res.skipped,
            )
            if res.warnings:
                msg += "\n\n" + tr("setup.import_warnings") + "\n- " + "\n- ".join(res.warnings[:12])
                if len(res.warnings) > 12:
                    msg += "\n" + trf("setup.import_more_warnings", n=len(res.warnings) - 12)
            QMessageBox.information(self, tr("msg.info"), msg)

            # Kontrolle im Kategorien-Manager
            QMessageBox.information(self, tr("setup.kontrolle_title"), tr("setup.zur_kontrolle_oeffnet_sich"))
            with self._setup_hidden_while_child_open():
                self.main_window._show_category_manager()

            self._cats_done = True
            self._step_done[self._IDX_CAT_EXCEL] = True
            self.lbl_cat_done_2.setText(tr("setup.excel_import_done"))
            self._update_nav()
            self.main_window._schedule_refresh_all_tabs(reason="setup assistant changed data") if hasattr(self.main_window, "_schedule_refresh_all_tabs") else self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("setup.import_failed", e=e))

    def _open_first_booking(self) -> None:
        try:
            # tracking_tab.add() öffnet den Dialog und speichert bei OK
            if hasattr(self.main_window.tracking_tab, "add"):
                with self._setup_hidden_while_child_open():
                    self.main_window.tracking_tab.add()
                self.main_window.tracking_tab.refresh()
                self._recompute_tracking_done()
            else:
                QMessageBox.information(self, tr("msg.info"), tr("msg.setup_tracking_unavailable"))
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_dialog_failed", e=e))

    def _open_fix_dialog(self) -> None:
        try:
            if hasattr(self.main_window.tracking_tab, "add_fixcosts"):
                with self._setup_hidden_while_child_open():
                    self.main_window.tracking_tab.add_fixcosts()
            else:
                QMessageBox.information(self, tr("msg.info"), tr("msg.setup_fixrecurring_unavailable"))
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_dialog_failed", e=e))

    # ---------------------------------------------------------------------
    # Budget starter helpers
    # ---------------------------------------------------------------------

    def _find_category_id(self, typ: str, name: str) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM categories WHERE typ=? AND name=?",
            (typ, name),
        ).fetchone()
        if not row:
            return None
        return int(row["id"] if hasattr(row, "keys") else row[0])

    def _ensure_setup_category(
        self,
        typ: str,
        name: str,
        *,
        is_fix: bool = False,
        is_recurring: bool = False,
        recurring_day: int = 1,
        parent_name: str | None = None,
        sort_order: int = 0,
    ) -> int:
        parent_id = None
        if parent_name:
            parent_id = self._find_category_id(typ, parent_name)
            if parent_id is None:
                self._cat_model.upsert(
                    typ,
                    parent_name,
                    False,
                    False,
                    1,
                    parent_id=None,
                    sort_order=max(0, sort_order - 1),
                )
                parent_id = self._find_category_id(typ, parent_name)

        self._cat_model.upsert(
            typ,
            name,
            bool(is_fix),
            bool(is_recurring),
            int(recurring_day or 1),
            parent_id=parent_id,
            sort_order=int(sort_order),
        )
        cat_id = self._find_category_id(typ, name)
        if cat_id is None:
            raise RuntimeError(f"Kategorie konnte nicht angelegt werden: {typ} / {name}")
        return cat_id

    def _ensure_default_categories_for_budget_setup(self) -> None:
        if self._cat_model.count() <= 0:
            # Falls Kategorien gelöscht wurden, kann das alte defaults_loaded-Flag
            # trotzdem noch gesetzt sein. Deshalb Flag zurücksetzen und dann Defaults laden.
            self._cat_model.reset_defaults_flag()
            self._cat_model.ensure_defaults()

    def _seed_all_budget_rows_for_year(self, year: int) -> None:
        """Legt für alle Kategorien 12 Monatszeilen mit 0 CHF an, ohne Werte zu überschreiben."""
        self._ensure_default_categories_for_budget_setup()
        by_typ: dict[str, list[str]] = {}
        for cat in self._cat_model.list(None):
            by_typ.setdefault(cat.typ, []).append(cat.name)
        with suspend_after_commit_autosave(self.conn):
            for typ, names in by_typ.items():
                self._budget_model.seed_year_from_categories(int(year), typ, names, amount=0.0)

    def _set_monthly_budget_amount(
        self,
        *,
        year: int,
        typ: str,
        category: str,
        amount: float,
        overwrite: bool,
    ) -> tuple[int, int]:
        """Setzt einen Monatsbetrag für alle 12 Monate. Returns: (changed, skipped)."""
        changed = 0
        skipped = 0
        amount = float(amount or 0.0)
        if amount <= 0:
            return changed, skipped

        with suspend_after_commit_autosave(self.conn):
            for month in range(1, 13):
                row = self.conn.execute(
                    "SELECT amount FROM budget WHERE year=? AND month=? AND typ=? AND category=?",
                    (int(year), int(month), typ, category),
                ).fetchone()
                existing = float(row["amount"] or 0.0) if row else 0.0
                if row is not None and existing != 0.0 and not overwrite:
                    skipped += 1
                    continue
                self._budget_model.set_amount(int(year), int(month), typ, category, amount)
                changed += 1
        return changed, skipped

    def _create_empty_budget_year(self) -> None:
        try:
            year = int(self.spin_budget_year.value())
            self._seed_all_budget_rows_for_year(year)
            self.lbl_budget_starter_status.setText(
                trf("setup.empty_budget_year_created", year=year)
            )
            if hasattr(self.main_window, "_refresh_all_tabs"):
                self.main_window._schedule_refresh_all_tabs(reason="setup assistant changed data") if hasattr(self.main_window, "_schedule_refresh_all_tabs") else self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_budget_template_failed", e=e))

    def _apply_budget_template(self) -> None:
        """Erstellt ein einfaches Budget-Grundgerüst aus den Formularwerten."""
        try:
            year = int(self.spin_budget_year.value())
            overwrite = bool(self.cb_overwrite_budget.isChecked())

            self._ensure_default_categories_for_budget_setup()
            if self.cb_seed_all_budget.isChecked():
                self._seed_all_budget_rows_for_year(year)

            # Sicherstellen, dass die wichtigsten Kategorien vorhanden sind.
            self._ensure_setup_category(
                TYP_INCOME, "Lohn (Netto)", is_recurring=True, recurring_day=25, sort_order=0
            )
            self._ensure_setup_category(
                TYP_EXPENSES, "Miete/Hypothek", is_fix=True, is_recurring=True, recurring_day=1,
                parent_name="Wohnen", sort_order=0
            )
            self._ensure_setup_category(
                TYP_EXPENSES, "Krankenkasse", is_fix=True, is_recurring=True, recurring_day=1,
                parent_name="Versicherungen", sort_order=0
            )
            self._ensure_setup_category(
                TYP_EXPENSES, "Lebensmittel", parent_name="Lebenshaltung", sort_order=0
            )
            self._ensure_setup_category(
                TYP_EXPENSES, "Steuern", is_fix=True, is_recurring=True, recurring_day=1, sort_order=0
            )
            self._ensure_setup_category(
                TYP_EXPENSES, "Telefon/Internet", is_fix=True, is_recurring=True, recurring_day=1,
                parent_name="Kommunikation & Medien", sort_order=0
            )
            self._ensure_setup_category(
                TYP_EXPENSES, "ÖV (Abo/Billette)", parent_name="Mobilität", sort_order=0
            )
            self._ensure_setup_category(
                TYP_SAVINGS, "Notgroschen", is_recurring=True, recurring_day=25, sort_order=0
            )
            self._ensure_setup_category(
                TYP_SAVINGS, "Ferien", is_recurring=False, recurring_day=25, parent_name="Rücklagen", sort_order=0
            )

            mapping = [
                (TYP_INCOME, "Lohn (Netto)", self.spn_income_salary.value()),
                (TYP_EXPENSES, "Miete/Hypothek", self.spn_exp_rent.value()),
                (TYP_EXPENSES, "Krankenkasse", self.spn_exp_health.value()),
                (TYP_EXPENSES, "Lebensmittel", self.spn_exp_groceries.value()),
                (TYP_EXPENSES, "Steuern", self.spn_exp_taxes.value()),
                (TYP_EXPENSES, "Telefon/Internet", self.spn_exp_phone.value()),
                (TYP_EXPENSES, "ÖV (Abo/Billette)", self.spn_exp_transport.value()),
                (TYP_SAVINGS, "Notgroschen", self.spn_save_emergency.value()),
                (TYP_SAVINGS, "Ferien", self.spn_save_vacation.value()),
            ]

            changed = 0
            skipped = 0
            filled_categories = 0
            for typ, category, amount in mapping:
                if float(amount or 0.0) <= 0:
                    continue
                c, s = self._set_monthly_budget_amount(
                    year=year, typ=typ, category=category, amount=float(amount), overwrite=overwrite
                )
                changed += c
                skipped += s
                filled_categories += 1

            self.lbl_budget_starter_status.setText(
                trf(
                    "setup.budget_template_applied",
                    year=year,
                    categories=filled_categories,
                    changed=changed,
                    skipped=skipped,
                )
            )
            if hasattr(self.main_window, "_refresh_all_tabs"):
                self.main_window._schedule_refresh_all_tabs(reason="setup assistant changed data") if hasattr(self.main_window, "_schedule_refresh_all_tabs") else self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_budget_template_failed", e=e))

    def _enter_budget_tab_and_open_budget_window_once(self) -> None:
        """Wechselt in den Budget-Tab und öffnet beim ersten Eintritt das Budget-Fenster."""
        self._enter_budget_tab()
        self._recompute_budget_done()
        if not self._budget_opened_once:
            self._open_budget_window(auto=True)

    # ── harte Mindestdaten-Prüfung für den Erststart ─────────────
    def _has_budget_value(self) -> bool:
        """True, wenn mindestens ein Budgetwert > 0 existiert."""
        try:
            row = self.conn.execute("SELECT COUNT(*) FROM budget WHERE amount > 0").fetchone()
            return bool(row and row[0] > 0)
        except Exception:
            return False

    def _recompute_budget_done(self) -> None:
        has_val = self._has_budget_value()
        # v2.1.7 Blocker-Fix: Aktiver Lernmodus erfüllt den Schritt ebenfalls –
        # der Nutzer darf erst nur tracken und Budgets später lernen lassen.
        learning_active = bool(
            getattr(self, "cb_setup_learning_enabled", None)
            and self.cb_setup_learning_enabled.isChecked()
        )
        done = has_val or learning_active
        self._budget_done = done
        if len(self._step_done) > self._IDX_BUDGET_LOAD:
            self._step_done[self._IDX_BUDGET_LOAD] = done
        if hasattr(self, "lbl_budget_done"):
            if has_val:
                self.lbl_budget_done.setText(tr("setup.budget_value_present"))
            elif learning_active:
                self.lbl_budget_done.setText(tr("setup.budget_learning_skip_ok"))
            else:
                self.lbl_budget_done.setText(tr("setup.budget_value_missing"))
        self._update_nav()

    def _has_tracking_entry(self) -> bool:
        try:
            row = self.conn.execute("SELECT COUNT(*) FROM tracking").fetchone()
            return bool(row and row[0] > 0)
        except Exception:
            return False

    def _recompute_tracking_done(self) -> None:
        has_entry = self._has_tracking_entry()
        if len(self._step_done) > self._IDX_TRACKING_FIRST:
            self._step_done[self._IDX_TRACKING_FIRST] = has_entry
        if hasattr(self, "lbl_tracking_done"):
            self.lbl_tracking_done.setText(
                tr("setup.tracking_entry_present") if has_entry
                else tr("setup.tracking_entry_missing")
            )
        self._update_nav()

    def _open_budget_window(self, *, auto: bool = False) -> None:
        """Öffnet ein separates Budget-Fenster zum direkten Ausfüllen."""
        try:
            dlg = BudgetFillDialog(self.main_window, self.conn, title=tr("setup.budget_ausfuellen_setup"))
            with self._setup_hidden_while_child_open():
                dlg.exec()

            self._budget_opened_once = True
            self._recompute_budget_done()

            # Tabs neu laden (Budget/Übersicht hängen davon ab)
            if hasattr(self.main_window, "_refresh_all_tabs"):
                self.main_window._schedule_refresh_all_tabs(reason="setup assistant changed data") if hasattr(self.main_window, "_schedule_refresh_all_tabs") else self.main_window._refresh_all_tabs()
        except Exception as e:
            # Auto-Open soll UI nicht nerven – Button-Open darf Fehler zeigen
            if not auto:
                QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_budget_window_failed", e=e))

    # ---------------------------------------------------------------------
    # Safety helpers
    # ---------------------------------------------------------------------

    def _do_restore_backup(self) -> None:
        """Backup wiederherstellen aus dem Setup-Assistenten.

        Wichtig: Der BackupRestoreDialog erwartet die aktive DB-Umgebung
        (db_path/settings/encrypted_session/active_user). Der alte Aufruf mit
        einem nicht existierenden Direktpfad-Parameter passte nicht zur Signatur
        und brach den geführten Starter beim Klick auf „Backup wiederherstellen" ab.
        """
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            from model.app_paths import resolve_in_app, configured_db_path

            path, _ = QFileDialog.getOpenFileName(
                self,
                tr("setup.setup_db_restore"),
                "",
                tr("setup.backup_file_filter"),
            )
            if not path:
                return

            from views.backup_restore_dialog import BackupRestoreDialog

            encrypted_session = getattr(self.main_window, "_encrypted_session", None)
            active_user = getattr(self.main_window, "_active_user", None)
            db_path = None
            if encrypted_session is None:
                db_path = str(configured_db_path(self.settings.database_path))

            dlg = BackupRestoreDialog(
                self,
                self.conn,
                db_path,
                self.settings,
                encrypted_session=encrypted_session,
                active_user=active_user,
            )
            changed = dlg.restore_external_path(path)

            if changed:
                # Ein Restore im Setup-Assistenten bedeutet: Es existiert bereits
                # eine echte BudgetManager-Datenbank. Deshalb nicht weiter als
                # leeren Erststart behandeln und die Einführung künftig nicht
                # automatisch öffnen.
                try:
                    self.settings.set("show_onboarding", False)
                    self.settings.set("setup_completed", True)
                    self.settings.set("tracking_budget_learning_enabled", bool(self.settings.get("tracking_budget_learning_enabled", True)))
                    self.settings.set("tracking_budget_learning_show_in_report", bool(self.settings.get("tracking_budget_learning_show_in_report", True)))
                    self.settings.set("auto_generate_budget_warnings", bool(self.settings.get("auto_generate_budget_warnings", True)))
                except Exception as settings_err:
                    logger.warning("Setup-Restore-Settings konnten nicht finalisiert werden: %s", settings_err)

            if changed and hasattr(self.main_window, "_refresh_all_tabs"):
                try:
                    self.main_window._schedule_refresh_all_tabs(reason="setup assistant changed data") if hasattr(self.main_window, "_schedule_refresh_all_tabs") else self.main_window._refresh_all_tabs()
                except Exception as refresh_err:
                    logger.warning("Tab-Refresh nach Setup-Restore fehlgeschlagen: %s", refresh_err)

            # DB-Info aktualisieren
            try:
                self.lbl_db.setText(
                    f"<b>{tr('setup.setup_db_path')}:</b> {self.db_path}<br>"
                    + tr("setup.setup_db_desc")
                )
            except Exception as e:
                logger.debug("Setup-DB-Label konnte nicht gesetzt werden: %s", e)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, tr("msg.error"), str(e))

    def _do_reset_database(self) -> None:
        """Datenbank zurücksetzen aus dem Setup-Assistenten."""
        try:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                tr("setup.setup_db_reset"),
                tr("dlg.datenbank_reset_wirklich"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            # v2.2.1 (Bericht-Punkt 1): Vorher öffnete die Bestätigung nur den
            # DB-Verwaltungsdialog – der Reset passierte NICHT, obwohl der
            # Nutzer ihn gerade bestätigt hatte. Jetzt wird er direkt und mit
            # automatischem Backup ausgeführt; das Ergebnis wird angezeigt.
            from model.database_management_model import DatabaseManagementModel

            mgmt = DatabaseManagementModel(str(self.db_path), conn=self.conn)
            ok, message = mgmt.reset_database(create_backup=True, keep_user_data=False)
            if ok:
                msg_text = tr(message) if isinstance(message, str) else tr("database.msg.reset_all")
                QMessageBox.information(self, tr("setup.setup_db_reset"), msg_text)
                # Setup-Zustand neu bewerten (Kategorien/Budget/Tracking geändert)
                try:
                    self._recompute_budget_done()
                    self._recompute_tracking_done()
                except Exception as e2:
                    logger.debug("recompute after reset: %s", e2)
            else:
                info = message
                if isinstance(message, tuple):
                    key, params = message
                    info = trf(key, **(params or {}))
                QMessageBox.critical(self, tr("msg.error"), str(info))
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, tr("msg.error"), str(e))

    def _is_safe_to_reset(self) -> bool:
        try:
            b = self._budget_model.count()
        except Exception:
            b = 0
        try:
            t = self._tracking_model.count()
        except Exception:
            t = 0
        # nur wenn Budget+Tracking leer sind
        return (b == 0 and t == 0)

    def _reset_categories(self) -> None:
        try:
            if not self._is_safe_to_reset():
                QMessageBox.warning(self, tr("setup.nicht_moeglich"), tr("setup.dein_budgettracking_enthaelt_bereits"))
                return
            if QMessageBox.question(
                self,
                tr("setup.clean_start_title"),
                tr("setup.wirklich_alle_kategorien_loeschen"),
            ) != QMessageBox.Yes:
                self.cb_clean_start.setChecked(False)
                return

            self._cat_model.delete_all()
            self.conn.commit()
            QMessageBox.information(self, tr("msg.info"), tr("setup.kategorien_wurden_geloescht"))
            self.main_window._schedule_refresh_all_tabs(reason="setup assistant changed data") if hasattr(self.main_window, "_schedule_refresh_all_tabs") else self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("setup.reset_failed", e=e))

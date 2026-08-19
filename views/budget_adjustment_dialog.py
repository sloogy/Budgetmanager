from __future__ import annotations

from utils.accessibility import configure_dialog_tab_order
from utils.notifications import show_info
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
    QGroupBox,
    QTextEdit,
    QComboBox,
    QMenu,
)
from PySide6.QtGui import QColor

from model.budget_warnings_model_extended import BudgetWarningsModelExtended
from model.budget_overview_model import BudgetOverviewModel, BudgetSuggestion
from model.typ_constants import TYP_INCOME
from settings import Settings
from utils.money import format_money, parse_money
from model.budget_learning import (
    ALL_LEARNING_BUDGET_KINDS,
    apply_learning_budget_kind,
    budget_kind_label,
)
from views.ui_colors import ui_colors


import logging
from utils.i18n import tr, trf, display_typ, db_typ_from_display

logger = logging.getLogger(__name__)


class _LearningBudgetKindDialog(QDialog):
    """Bestätigung der Budgetart beim Übernehmen eines Lernvorschlags."""

    def __init__(self, parent, suggestion: BudgetSuggestion):
        super().__init__(parent)
        self.suggestion = suggestion
        self.decision = "observe"
        self.setWindowTitle(tr("budget_learning.dialog.title"))
        self.setModal(True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        title = QLabel(
            trf(
                "budget_learning.dialog.heading",
                category=suggestion.category,
                amount=format_money(suggestion.suggested_amount),
            )
        )
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: bold;")
        root.addWidget(title)

        info = QLabel(suggestion.message)
        info.setWordWrap(True)
        root.addWidget(info)

        if getattr(suggestion, "tracking_data", ""):
            tracking = QLabel(
                trf("budget_learning.dialog.tracking", data=suggestion.tracking_data)
            )
            tracking.setWordWrap(True)
            root.addWidget(tracking)

        form = QFormLayout()
        self.kind_combo = QComboBox()
        current_kind = str(getattr(suggestion, "budget_kind", "") or "variable_pot")
        for kind in ALL_LEARNING_BUDGET_KINDS:
            self.kind_combo.addItem(budget_kind_label(kind), kind)
        idx = self.kind_combo.findData(current_kind)
        self.kind_combo.setCurrentIndex(max(0, idx))
        self.kind_combo.setToolTip(tr("budget_learning.dialog.kind_tip"))
        form.addRow(tr("budget_learning.dialog.kind_label"), self.kind_combo)
        root.addLayout(form)

        btns = QHBoxLayout()
        self.btn_accept = QPushButton(tr("budget_learning.action.accept"))
        self.btn_observe = QPushButton(tr("budget_learning.action.observe"))
        self.btn_ignore = QPushButton(tr("budget_learning.action.ignore"))
        self.btn_accept.setDefault(True)
        btns.addStretch(1)
        btns.addWidget(self.btn_observe)
        btns.addWidget(self.btn_ignore)
        btns.addWidget(self.btn_accept)
        root.addLayout(btns)

        self.btn_accept.clicked.connect(self._accept_budget)
        self.btn_observe.clicked.connect(self._observe)
        self.btn_ignore.clicked.connect(self._ignore)
        configure_dialog_tab_order(self)

    def _accept_budget(self) -> None:
        self.decision = "accept"
        self.accept()

    def _observe(self) -> None:
        self.decision = "observe"
        self.reject()

    def _ignore(self) -> None:
        self.decision = "ignore"
        self.accept()

    def selected_kind(self) -> str:
        return str(self.kind_combo.currentData() or "variable_pot")


class BudgetAdjustmentDialog(QDialog):
    """
    Dialog zur Anzeige von Budget-Abweichungen mit Anpassungsvorschlägen

    Zeigt:
    - Kategorien mit häufigen Überschreitungen
    - Historische Daten (wie oft überschritten)
    - Intelligente Budget-Vorschläge
    - Option zur direkten Anpassung
    """

    def __init__(
        self,
        parent,
        warnings_model: BudgetWarningsModelExtended,
        budget_model,
        year: int,
        month: int,
    ):
        super().__init__(parent)
        self.warnings_model = warnings_model
        self.budget_model = budget_model
        self.year = year
        self.month = month
        self.data_changed = False

        self.setWindowTitle(tr("dlg.budget_adjustment"))
        self.setModal(True)
        self.resize(1000, 700)

        # Settings: wie weit wir für Vorschläge/Häufigkeit zurückschauen.
        # Wir verwenden bewusst dieselbe Einstellung wie in der Übersicht,
        # damit der User nur einen Regler hat, der erwartbar wirkt.
        # Achtung: Dieser Dialog soll *denselben* Regler nutzen wie die Übersicht,
        # sonst wirkt das Verhalten "zufällig" (z.B. immer 6 Monate).
        try:
            self._lookback_months = int(
                Settings().get("budget_suggestion_months", 3) or 3
            )
        except Exception:
            self._lookback_months = 3

        self._already_loaded = False
        self._applied_categories: set[tuple[str, str]] = (
            set()
        )  # (typ, category) bereits angepasst
        self._setup_ui()
        self._load_exceedances()
        configure_dialog_tab_order(self)

    def showEvent(self, event):
        """Bei erneutem Öffnen frisch laden – aber NICHT beim ersten Anzeigen
        (der __init__ hat bereits _load_exceedances() aufgerufen).

        Manche Nutzer öffnen den Budgetwarner mehrfach pro Session.
        Ohne Reload wirkt es so, als ob keine Vorschläge existieren,
        obwohl sich die DB (Tracking/Budget) geändert hat.
        """
        super().showEvent(event)
        if self._already_loaded:
            # Nur bei echtem Re-Show (z.B. nach Minimieren) neu laden
            try:
                self._load_exceedances()
            except Exception:
                import traceback

                traceback.print_exc()
        else:
            # Erster showEvent nach __init__ – Daten sind bereits geladen
            self._already_loaded = True

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Titel und Info
        title = QLabel(
            trf("dlg.budgetabweichungen_fuer", month=self.month, year=self.year)
        )
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        info = QLabel("ℹ️ " + tr("dlg.dlg_banner_hint"))
        info.setWordWrap(True)
        _c0 = ui_colors(self)
        info.setStyleSheet(
            f"padding: 10px; background-color: {_c0.warning_bg}; border-left: 4px solid {_c0.warning}; "
            f"border-radius: 4px; color: {_c0.warning};"
        )
        layout.addWidget(info)

        # Tabelle für Überschreitungen
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                tr("header.header_typ"),
                tr("header.category"),
                tr("header.header_budget"),
                tr("header.header_spent"),
                tr("header.header_diff"),
                tr("header.header_pct"),
                trf("dlg.haeufigkeit", months=self._lookback_months),
                tr("lbl.suggestion"),
                tr("header.header_adjust"),
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_learning_context_menu)
        self._apply_stable_column_widths()
        layout.addWidget(self.table)

        # Informativ: Typ-Gesamt-Vorschläge (nicht editierbar)
        self.type_info_group = QGroupBox(tr("dlg.dlg_recommendations"))
        type_info_layout = QVBoxLayout(self.type_info_group)
        self.type_info_text = QTextEdit()
        self.type_info_text.setReadOnly(True)
        self.type_info_text.setMaximumHeight(110)
        type_info_layout.addWidget(self.type_info_text)
        self.type_info_group.setVisible(False)
        layout.addWidget(self.type_info_group)

        # Statistik-Bereich
        stats_group = QGroupBox(tr("dlg.dlg_recommendations"))
        stats_layout = QVBoxLayout(stats_group)

        self.recommendation_text = QTextEdit()
        self.recommendation_text.setReadOnly(True)
        self.recommendation_text.setMaximumHeight(150)
        stats_layout.addWidget(self.recommendation_text)

        layout.addWidget(stats_group)

        # Buttons
        btn_layout = QHBoxLayout()

        self.btn_select_all = QPushButton(tr("btn.select_all"))
        self.btn_deselect_all = QPushButton(tr("btn.deselect_all"))
        self.btn_apply = QPushButton(tr("dlg.ausgewaehlte_anwenden"))
        self.btn_apply.setStyleSheet(
            f"QPushButton {{ background-color: {_c0.ok}; color: white; padding: 8px 16px; "
            f"font-weight: bold; }} QPushButton:hover {{ opacity: 0.9; }}"
        )
        self.btn_close = QPushButton(tr("btn.close"))

        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        # Signals
        self.btn_select_all.clicked.connect(lambda: self._toggle_all(True))
        self.btn_deselect_all.clicked.connect(lambda: self._toggle_all(False))
        self.btn_apply.clicked.connect(self._on_apply_adjustments)
        self.btn_close.clicked.connect(self.reject)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    @staticmethod
    def _is_learning_suggestion(sug: BudgetSuggestion | None) -> bool:
        return bool(sug is not None and getattr(sug, "direction", "") == "initial")

    def _suggestion_for_row(self, row: int) -> BudgetSuggestion | None:
        for col in (7, 1):
            item = self.table.item(row, col)
            if item is not None:
                data = item.data(Qt.UserRole + 1)
                if isinstance(data, BudgetSuggestion):
                    return data
        return None

    def _overview_for_learning_actions(self) -> BudgetOverviewModel:
        model = getattr(self, "_overview_model", None)
        if model is None:
            model = BudgetOverviewModel(self.warnings_model.conn)
            self._overview_model = model
        return model

    def _set_learning_action_for_row(self, row: int, action: str) -> None:
        sug = self._suggestion_for_row(row)
        if not self._is_learning_suggestion(sug):
            return
        try:
            self._overview_for_learning_actions().set_learning_action(
                sug.typ,
                sug.category,
                action,
                year=self.year,
                month=self.month,
            )
        except Exception as exc:
            logger.warning("learning action failed: %s", exc)

    def _show_learning_context_menu(self, pos) -> None:
        """Kontextmenü für Lernvorschläge: beobachten, ignorieren, unregelmäßig."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        sug = self._suggestion_for_row(row)
        if not self._is_learning_suggestion(sug):
            return

        menu = QMenu(self)
        act_watch = menu.addAction(tr("budget_learning.action.observe"))
        act_irregular = menu.addAction(tr("budget_learning.action.mark_irregular"))
        act_ignore = menu.addAction(tr("budget_learning.action.ignore"))
        menu.addSeparator()
        act_reset = menu.addAction(tr("budget_learning.action.reset"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_watch:
            self._set_learning_action_for_row(row, "watch_later")
        elif chosen == act_irregular:
            self._set_learning_action_for_row(row, "irregular")
        elif chosen == act_ignore:
            self._set_learning_action_for_row(row, "ignore")
        elif chosen == act_reset:
            self._set_learning_action_for_row(row, "reset")
        self._load_exceedances()

    def _load_exceedances(self):
        """Lädt alle Budget-Abweichungen – primäre Quelle: BudgetOverviewModel.get_suggestions()

        Einheitliche Logik mit dem Vorschläge-Banner in der Übersicht:
        - Suggestions kommen aus BudgetOverviewModel (gleiche Engine wie Banner)
        - Ergänzt mit BudgetWarnings für aktuelle Monatsdaten (Budget/Ist/Häufigkeit)
        - Banner-Anzahl stimmt immer mit Dialog-Anzahl überein
        """
        self.table.setRowCount(0)

        # Ungültiges Jahr abfangen (z.B. year=0 wenn DB leer oder year_combo noch nicht befüllt)
        if not self.year or self.year < 1:
            from datetime import date as _date

            self.year = _date.today().year

        try:
            self.warnings_model.conn.rollback()
        except Exception as e:
            logger.debug("%s", e)

        # ── Primäre Quelle: BudgetOverviewModel (wie der Übersicht-Banner) ──
        # Liefert Vorschläge aus dem Rolling-Window-Algorithmus (Median, sign-ratio, etc.)
        try:
            overview_model = BudgetOverviewModel(self.warnings_model.conn)
            cat_suggestions = overview_model.get_suggestions(
                year=self.year,
                current_month=self.month,
                min_consecutive_months=self._lookback_months,
            )

            # Manuell geöffneter Dialog: Lernvorschläge dürfen nicht durch die
            # reine Report-/Banner-Option verschwinden. Nach Restore kann diese
            # Einstellung aus einem alten Profil kommen; der Button "Vorschläge"
            # soll trotzdem aktiv prüfen. Ignorierte Kategorien bleiben weiterhin
            # ignoriert, weil get_tracking_budget_suggestions den Lernstatus liest.
            try:
                explicit_learning = overview_model.get_tracking_budget_suggestions(
                    year=self.year,
                    current_month=self.month,
                    show_in_report=True,
                )
                existing_learning_keys = {(s.typ, s.category) for s in cat_suggestions}
                for ls in explicit_learning:
                    key = (ls.typ, ls.category)
                    if key not in existing_learning_keys:
                        cat_suggestions.append(ls)
                        existing_learning_keys.add(key)
            except Exception as learning_exc:
                logger.debug("explicit learning suggestions failed: %s", learning_exc)

            type_suggestions = overview_model.get_type_suggestions(
                year=self.year,
                current_month=self.month,
                min_consecutive_months=self._lookback_months,
            )
            balance_suggestions = overview_model.get_balance_suggestions(
                year=self.year,
                current_month=self.month,
                min_consecutive_months=self._lookback_months,
            )
            # Nur echte Kategorie-Vorschläge gehören in die editierbare Tabelle.
            # Carryover-/Restdefizit-Hinweise bleiben separat informativ, damit
            # keine Kunst-Kategorien wie „Carryover" in die DB geschrieben werden.
            all_suggestions: list[BudgetSuggestion] = [
                s for s in cat_suggestions if (s.category or "").strip()
            ]
            existing_keys = {(s.typ, s.category) for s in all_suggestions}
            for s in balance_suggestions:
                key = (s.typ, s.category)
                if s.current_budget > 0 and key not in existing_keys:
                    all_suggestions.append(s)
                    existing_keys.add(key)
                else:
                    type_suggestions.append(s)
        except Exception as e:
            logger.warning("BudgetOverviewModel suggestions failed: %s", e)
            all_suggestions = []
            type_suggestions = []

        self._render_type_suggestions(type_suggestions)

        # ── Sekundäre Quelle: BudgetWarnings für aktuellen Monat (Budget/Ist) ──
        # Enthält Kategorien die diesen Monat über-Budget sind (auch wenn kein Rolling-Window)
        try:
            exceedances_map = {
                (exc.typ, exc.category): exc
                for exc in self.warnings_model.check_warnings_extended(
                    self.year, self.month, lookback_months=self._lookback_months
                )
            }
        except Exception as e:
            logger.debug("check_warnings_extended: %s", e)
            exceedances_map = {}

        # ── Union: Alle Kategorien aus beiden Quellen ──
        # Reihenfolge: Übersicht-Vorschläge zuerst, dann nur-Warnungen
        seen_keys: set[tuple[str, str]] = set()
        merged_rows = []

        for sug in all_suggestions:
            key = (sug.typ, sug.category)
            seen_keys.add(key)
            exc = exceedances_map.get(key)
            merged_rows.append((sug, exc))

        # Kategorien nur aus Warnungen (aktuell überschritten, aber noch kein Rolling-Window)
        for (typ, cat), exc in exceedances_map.items():
            if (typ, cat) not in seen_keys:
                merged_rows.append((None, exc))

        # Vorschläge ausblenden die diesen Monat bereits angenommen wurden
        # (persistent aus DB + session-intern aus _applied_categories)
        def _row_key(sug, exc):
            if sug is not None:
                return (sug.typ, sug.category)
            if exc is not None:
                return (exc.typ, exc.category)
            return None

        try:
            accepted_this_month = self.warnings_model.get_accepted_for_month(
                self.year, self.month
            )
        except Exception:
            accepted_this_month = set()

        excluded = self._applied_categories | accepted_this_month
        if excluded:
            merged_rows = [
                (sug, exc)
                for (sug, exc) in merged_rows
                if _row_key(sug, exc) not in excluded
            ]

        if not merged_rows:
            _c0 = ui_colors(self)
            self.recommendation_text.setHtml(
                "<p style='color: "
                + _c0.ok
                + "; font-weight: bold;'>✓ "
                + tr("dlg.dlg_all_green")
                + "</p>"
            )
            return

        # Auto-Generierung kennzeichnen: Wenn keine gespeicherten Warnungsregeln,
        # wurden die Einträge automatisch aus dem Budget erzeugt → transparent für Nutzer.
        _auto = getattr(self.warnings_model, "_auto_generated", False)
        if _auto:
            _ci = ui_colors(self)
            # Info-Banner über die Tabelle (falls noch kein solches Widget vorhanden)
            if not getattr(self, "_lbl_auto_info", None):
                from PySide6.QtWidgets import QLabel as _QLabel

                self._lbl_auto_info = _QLabel()
                self._lbl_auto_info.setWordWrap(True)
                # Einfügen direkt über der Tabelle
                lyt = self.layout()
                tbl_idx = lyt.indexOf(self.table)
                if tbl_idx >= 0:
                    lyt.insertWidget(tbl_idx, self._lbl_auto_info)
            self._lbl_auto_info.setText("ℹ️ " + tr("dlg.dlg_check_info"))
            self._lbl_auto_info.setStyleSheet(
                f"padding: 6px 10px; background-color: {_ci.info_bg}; "
                f"border-left: 3px solid {_ci.accent}; border-radius: 3px; "
                f"color: {_ci.text}; font-size: 11px;"
            )
            self._lbl_auto_info.setVisible(True)
        elif getattr(self, "_lbl_auto_info", None):
            self._lbl_auto_info.setVisible(False)

        # Sortieren: Vorschläge mit deficit zuerst, dann surplus, dann reine Warnungen
        def _sort_key(item):
            sug, exc = item
            if sug is None:
                return (3, exc.exceed_count * -1 if exc else 0)
            if sug.direction == "initial":
                return (0, sug.observed_months * -1, sug.consecutive_months * -1)
            return (1 if sug.direction == "deficit" else 2, sug.consecutive_months * -1)

        merged_rows.sort(key=_sort_key)

        total_adjustment = 0
        chronic_categories = []
        c = ui_colors(self)

        for sug, exc in merged_rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Typ + Kategorie aus der besten verfügbaren Quelle
            typ = sug.typ if sug else exc.typ
            category = sug.category if sug else exc.category
            budget = sug.current_budget if sug else (exc.budget if exc else 0.0)
            if exc:
                spent = exc.spent
            elif sug:
                # Vorschlags-only-Zeilen haben keine aktuelle Monatswarnung.
                # ``avg_deviation`` ist die Abweichung, nicht der Ist-Wert.
                # Für Ausgaben/Ersparnisse gilt: Abweichung = Budget - Ist;
                # für Einkommen: Abweichung = Ist - Budget. So zeigen wir eine
                # plausible Durchschnitts-Ist-Basis statt irreführend nur 50 CHF
                # Differenz als "Getrackt".
                if typ == TYP_INCOME:
                    spent = max(0.0, float(budget) + float(sug.avg_deviation))
                else:
                    spent = max(0.0, float(budget) - float(sug.avg_deviation))
            else:
                spent = 0.0
            percent_used = (
                exc.percent_used
                if exc
                else (0.0 if budget <= 0 else (spent / budget * 100.0))
            )
            exceed_count = exc.exceed_count if exc else 0
            # Vorschlag aus BudgetOverviewModel (einheitliche Quelle)
            suggestion = (
                sug.suggested_amount if sug else (exc.suggestion if exc else None)
            )

            # Konflikt-Erkennung: Engine schaut nur in Vormonate (use_current_month=False).
            # Wenn der aktuelle Monat klar überschritten ist (spent > budget), die Engine
            # aber aufgrund historischer Unter-Nutzung eine SENKUNG vorschlägt (suggestion < budget),
            # dann ist das Signal widersprüchlich → Vorschlag ausblenden.
            if suggestion is not None and spent > budget * 1.05 and suggestion < budget:
                suggestion = (
                    None  # Widerspruch: aktuell über Budget, Vorschlag aber runter
                )

            # Typ
            typ_display = display_typ(typ)
            if sug is not None and getattr(sug, "learning_kind", ""):
                # v2.2.1: Lernvorschläge sichtbar von Anpassungen trennen.
                typ_display = f"🆕 {typ_display}"
            typ_item = QTableWidgetItem(typ_display)
            typ_item.setData(Qt.UserRole, typ)
            self.table.setItem(row, 0, typ_item)

            # Kategorie
            cat_item = QTableWidgetItem(category)
            # v2.2.1 (KILLCRITIC): "Warum dieser Vorschlag?" – Rechenweg als
            # Tooltip aus den vorhandenen Engine-Daten, ohne neue Berechnung.
            if sug is not None:
                try:
                    if getattr(sug, "learning_kind", ""):
                        why = trf(
                            "suggestion.why_learning",
                            n=sug.consecutive_months,
                            amount=format_money(abs(sug.avg_deviation)),
                            suggested=format_money(sug.suggested_amount),
                        )
                    else:
                        why_key = (
                            "suggestion.why_deficit"
                            if sug.direction == "deficit"
                            else "suggestion.why_surplus"
                        )
                        why = trf(
                            why_key,
                            n=sug.consecutive_months,
                            amount=format_money(abs(sug.avg_deviation)),
                            current=format_money(sug.current_budget),
                            suggested=format_money(sug.suggested_amount),
                        )
                    cat_item.setToolTip(why)
                except Exception as e:
                    logger.debug("why tooltip: %s", e)
            if sug:
                cat_item.setData(Qt.UserRole + 1, sug)
            if sug and getattr(sug, "message", ""):
                cat_item.setToolTip(sug.message)
            # "Chronischer Überschreiter" = wiederholt ÜBER Budget. exceed_count
            # zählt genau die Monate mit spent >= budget. Die frühere Oder-
            # Bedingung über consecutive_months war richtungsblind und markierte
            # auch dauerhaft UNTER-Budget-Kategorien fälschlich als Überschreiter.
            is_chronic = exceed_count >= 3
            if is_chronic:
                cat_item.setBackground(QColor(c.error_bg))
                chronic_categories.append(category)
            self.table.setItem(row, 1, cat_item)

            # Budget
            budget_item = QTableWidgetItem(format_money(budget))
            budget_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, budget_item)

            # Ausgegeben
            spent_item = QTableWidgetItem(format_money(spent))
            spent_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            spent_item.setForeground(
                QColor(c.negative if (budget > 0 and spent > budget) else c.ok)
            )
            self.table.setItem(row, 3, spent_item)

            # Differenz
            diff = spent - budget
            diff_item = QTableWidgetItem(format_money(diff, force_sign=True))
            diff_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if diff > 0.01:
                diff_item.setForeground(QColor(c.negative))
                diff_item.setBackground(QColor(c.error_bg))
            elif diff < -0.01:
                diff_item.setForeground(QColor(c.ok))
                diff_item.setBackground(QColor(c.success_bg))
            self.table.setItem(row, 4, diff_item)

            # Überschritten (%)
            if budget <= 0 and suggestion is not None:
                percent_item = QTableWidgetItem(
                    tr("budget_adjustment.new_budget_label")
                )
            else:
                percent_item = QTableWidgetItem(
                    trf(
                        "auto.views_budget_adjustment_dialog.366_value_0_e619e83b",
                        value_0=(percent_used),
                    )
                )
            percent_item.setTextAlignment(Qt.AlignCenter)
            if percent_used >= 150:
                percent_item.setBackground(QColor(c.error_bg))
            elif percent_used >= 110:
                percent_item.setBackground(QColor(c.warning_bg))
            self.table.setItem(row, 5, percent_item)

            # Häufigkeit / Konsekutive Monate (innerhalb des Fensters,
            # daher Zähler stets ≤ Fenster – kein "5/3" mehr).
            if sug and sug.direction == "initial":
                _fnum = int(sug.consecutive_months or 0)
                _fden = int(getattr(sug, "observed_months", 0) or self._lookback_months)
            elif sug and sug.consecutive_months > 0:
                _fnum = min(sug.consecutive_months, self._lookback_months)
                _fden = self._lookback_months
            else:
                _fnum = min(exceed_count, self._lookback_months)
                _fden = self._lookback_months
            freq_text = f"{_fnum}/{_fden}"
            freq_item = QTableWidgetItem(freq_text)
            freq_item.setTextAlignment(Qt.AlignCenter)
            if exceed_count >= 4 or (sug and sug.consecutive_months >= 4):
                freq_item.setBackground(QColor(c.error_bg))
                freq_item.setForeground(QColor(c.error_text))
            elif exceed_count >= 2 or (sug and sug.consecutive_months >= 2):
                freq_item.setBackground(QColor(c.warning_bg))
            self.table.setItem(row, 6, freq_item)

            # Vorschlag (aus BudgetOverviewModel – gleiche Quelle wie Banner)
            if suggestion is None:
                sugg_item = QTableWidgetItem("-")
                sugg_item.setTextAlignment(Qt.AlignCenter)
                sugg_item.setForeground(QColor(c.text_dim))
                self.table.setItem(row, 7, sugg_item)
            else:
                sugg_item = QTableWidgetItem(format_money(suggestion))
                sugg_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if sug:
                    sugg_item.setData(Qt.UserRole + 1, sug)
                if sug and sug.direction == "initial":
                    sugg_item.setBackground(QColor(c.info_bg))
                    sugg_item.setForeground(QColor(c.accent))
                    if getattr(sug, "budget_kind", ""):
                        sugg_item.setToolTip(budget_kind_label(sug.budget_kind))
                elif suggestion < budget:
                    sugg_item.setBackground(QColor(c.success_bg))
                    sugg_item.setForeground(QColor(c.success_text))
                elif suggestion > budget:
                    sugg_item.setBackground(QColor(c.warning_bg))
                    sugg_item.setForeground(QColor(c.warning_text))
                self.table.setItem(row, 7, sugg_item)

            # Checkbox: auto-check bei Vorschlag vorhanden + chronisch
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            is_surplus = budget > 0 and spent <= budget and suggestion is not None
            is_chronic_deficit = (exceed_count >= 3) or (
                sug and sug.consecutive_months >= 3 and sug.direction == "deficit"
            )
            auto = (suggestion is not None) and (is_surplus or is_chronic_deficit)
            if sug and sug.direction == "initial":
                auto = False
            chk.setCheckState(Qt.Checked if auto else Qt.Unchecked)
            self.table.setItem(row, 8, chk)

            if suggestion is not None and auto:
                total_adjustment += suggestion - budget

        self._apply_stable_column_widths()

        # Empfehlungstext generieren – exceedances aus merged_rows für Rückwärtskompatibilität
        exc_list = [exc for _, exc in merged_rows if exc is not None]
        self._generate_recommendations(exc_list, chronic_categories, total_adjustment)

    def _apply_stable_column_widths(self) -> None:
        """Verhindert springende Spaltenbreiten nach Reload/Settings-Änderungen."""
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        widths = {
            0: 120,  # Typ
            1: 220,  # Kategorie
            2: 105,  # Budget
            3: 105,  # Getrackt
            4: 105,  # Differenz
            5: 80,  # Prozent / neu
            6: 95,  # Häufigkeit
            7: 120,  # Vorschlag
            8: 70,  # Auswahl
        }
        for col, width in widths.items():
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)

    def _render_type_suggestions(
        self, type_suggestions: list[BudgetSuggestion]
    ) -> None:
        """Zeigt Typ-Gesamt-Vorschläge separat und nicht editierbar an."""
        if not type_suggestions:
            self.type_info_group.setVisible(False)
            self.type_info_text.clear()
            return
        rows = []
        for sug in type_suggestions:
            if getattr(sug, "message", ""):
                rows.append(f"• {sug.message}")
            else:
                rows.append(
                    f"• {display_typ(sug.typ)}: {format_money(sug.current_budget)} → {format_money(sug.suggested_amount)}"
                )
        self.type_info_text.setPlainText("\n".join(rows))
        self.type_info_group.setVisible(True)

    def _generate_recommendations(
        self, exceedances: list, chronic_categories: list, total_adjustment: float
    ):
        """Generiert Empfehlungstext basierend auf den Daten"""
        _c = ui_colors(self)
        html = "<div style='font-family: Arial; font-size: 12px;'>"

        # Überschrift – differenziert nach Überschreitung und Unterschreitung
        exceeded_cats = [e for e in exceedances if e.spent > e.budget]
        surplus_cats = [
            e for e in exceedances if e.spent <= e.budget and e.suggestion is not None
        ]
        header_parts = []
        if exceeded_cats:
            header_parts.append(
                f"⚠️ " + trf("suggestion.exceeded_n", n=len(exceeded_cats))
            )
        if surplus_cats:
            header_parts.append(
                f"💡 " + trf("suggestion.surplus_n", n=len(surplus_cats))
            )
        header_txt = (
            " &nbsp;|&nbsp; ".join(header_parts)
            if header_parts
            else trf("budget_adjustment.header.info_n", n=len(exceedances))
        )
        html += f"<h3 style='margin-top: 0;'>{header_txt}</h3>"

        # Chronische Überschreiter
        if chronic_categories:
            html += f"<p><strong>{trf('suggestion.chronic_label')}</strong> "
            html += ", ".join(chronic_categories)
            html += "<br/>💡 <em>" + tr("suggestion.chronic_text") + "</em></p>"

        # Gesamtanpassung
        if total_adjustment > 0:
            html += f"<p><strong>{tr('suggestion.total_increase_label')}</strong> "
            html += f"<span style='color: {_c.success_text}; font-weight: bold;'>"
            html += f"{format_money(total_adjustment, force_sign=True)}"
            html += "</span></p>"

        # Einkommens-Check: Übersteigen die Vorschläge das Einkommen?
        try:
            typ_sums = self.budget_model.sum_by_typ(self.year, self.month)
            # DB-Schlüssel verwenden (sprachunabhängig)
            from model.typ_constants import (
                TYP_INCOME as _TI,
                TYP_EXPENSES as _TE,
                TYP_SAVINGS as _TS,
            )

            income_budget = typ_sums.get(_TI, 0.0)

            if income_budget > 0 and total_adjustment > 0:
                # Aktuelle Ausgaben+Ersparnisse Budgets
                current_total = typ_sums.get(_TE, 0.0) + typ_sums.get(_TS, 0.0)
                new_total = current_total + total_adjustment

                if new_total > income_budget:
                    deficit = new_total - income_budget
                    html += (
                        f"<div style='background-color: {_c.warning_bg}; border: 2px solid {_c.warning}; "
                        f"border-radius: 6px; padding: 10px; margin: 10px 0;'>"
                        f"<h3 style='color: {_c.warning}; margin-top: 0;'>"
                        f"{tr('budget_adjustment.income_warning.title')}</h3>"
                        f"<p>{tr('budget_adjustment.income_warning.text')}</p>"
                        f"<table style='margin: 5px 0;'>"
                        f"<tr><td>{tr('budget_adjustment.income_warning.income')}:</td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"<strong>{format_money(income_budget)}</strong></td></tr>"
                        f"<tr><td>{tr('budget_adjustment.income_warning.current')}:</td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"{format_money(current_total)}</td></tr>"
                        f"<tr><td>{tr('budget_adjustment.income_warning.after')}:</td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"<span style='color: {_c.negative}; font-weight: bold;'>"
                        f"{format_money(new_total)}</span></td></tr>"
                        f"<tr><td><strong>{tr('budget_adjustment.income_warning.deficit')}:</strong></td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"<span style='color: {_c.negative}; font-weight: bold;'>"
                        f"{format_money(deficit)}</span></td></tr>"
                        f"</table>"
                        f"<p style='color: {_c.warning};'><strong>"
                        f"{tr('budget_adjustment.income_warning.action')}</strong></p>"
                        "</div>"
                    )
        except Exception as e:
            logger.debug("%s", e)

        # Allgemeine Tipps
        html += f"<hr/><p><strong>{tr('budget_adjustment.recommendations.title')}:</strong></p><ul>"

        avg_exceed_count = (
            (sum(e.exceed_count for e in exceedances) / len(exceedances))
            if exceedances
            else 0
        )

        if avg_exceed_count >= 3:
            html += (
                "<li>"
                + trf(
                    "budget_adjustment.recommendations.critical",
                    text=tr("dlg.dlg_urgent_check"),
                )
                + "</li>"
            )
        elif avg_exceed_count >= 2:
            html += "<li>" + tr("budget_adjustment.recommendations.attention") + "</li>"
        else:
            html += (
                "<li>"
                + trf(
                    "budget_adjustment.recommendations.hint",
                    text=tr("dlg.dlg_structural_changes"),
                )
                + "</li>"
            )

        # Spezifische Tipps basierend auf aktuellen Überschreitungen.
        # Regression v2.0.8: Der Dialog kann reine Verlaufsvorschläge enthalten,
        # ohne dass im aktuellen Monat eine echte Überschreitung vorliegt.
        # Dann ist ``exceedances`` leer und max([]) darf nicht crashen.
        max_exceedance = (
            max(exceeded_cats, key=lambda x: x.percent_used) if exceeded_cats else None
        )
        if max_exceedance is not None and max_exceedance.percent_used >= 150:
            html += (
                "<li>"
                + trf(
                    "budget_adjustment.recommendations.category_exceeded",
                    category=max_exceedance.category,
                    percent=f"{max_exceedance.percent_used:.0f}",
                )
                + "</li>"
            )

        html += "</ul>"
        html += "</div>"

        self.recommendation_text.setHtml(html)

    def _toggle_all(self, checked: bool):
        """Wählt alle/keine Checkboxen aus"""
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 8)
            if chk:
                chk.setCheckState(state)

    def _on_selection_changed(self):
        """Reagiert auf Selektion in der Tabelle"""
        pass

    def _on_apply_adjustments(self):
        """Wendet die ausgewählten Budget-Anpassungen an"""
        # Zähle ausgewählte Einträge
        selected_rows = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 8)
            if chk and chk.checkState() == Qt.Checked:
                selected_rows.append(row)

        if not selected_rows:
            show_info(
                self, tr("dlg.keine_auswahl"), tr("dlg.dlg_no_min_warnings_selected")
            )
            return

        # Frage: Nur diesen Monat oder restliche Monate?
        remaining_months_count = 12 - self.month + 1

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(tr("dlg.confirm"))
        msg.setText(
            tr("dlg.dlg_adjust_period_question")
            + "\n\n"
            + trf(
                "budget_adjustment.apply.period_lines",
                month=self.month,
                year=self.year,
                count=remaining_months_count,
            )
        )

        btn_this_month = msg.addButton(
            f"{tr('dlg.dlg_only_this_month').format(month=self.month, year=self.year)}",
            QMessageBox.AcceptRole,
        )
        btn_remaining = msg.addButton(
            f"{tr('dlg.dlg_remaining_months').format(n=remaining_months_count)}",
            QMessageBox.AcceptRole,
        )
        btn_cancel = msg.addButton(tr("btn.cancel"), QMessageBox.RejectRole)

        msg.setDefaultButton(btn_this_month)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == btn_cancel:
            return

        apply_remaining = clicked == btn_remaining

        applied_count = 0
        total_increase = 0
        total_months_affected = 0

        for row in selected_rows:
            typ_item = self.table.item(row, 0)
            typ = typ_item.data(Qt.UserRole) if typ_item else None
            if not typ:
                typ = db_typ_from_display(typ_item.text() if typ_item else "")
            category = self.table.item(row, 1).text()
            new_budget_str = self.table.item(row, 7).text()
            if not new_budget_str or new_budget_str.strip() in {"-", "–"}:
                continue
            new_budget = float(parse_money(new_budget_str))

            old_budget_str = self.table.item(row, 2).text()
            old_budget = float(parse_money(old_budget_str))

            sug = self._suggestion_for_row(row)
            if self._is_learning_suggestion(sug):
                kind_dlg = _LearningBudgetKindDialog(self, sug)
                kind_dlg.exec()
                if kind_dlg.decision == "observe":
                    self._set_learning_action_for_row(row, "watch_later")
                    continue
                if kind_dlg.decision == "ignore":
                    self._set_learning_action_for_row(row, "ignore")
                    self._applied_categories.add((typ, category))
                    try:
                        self.warnings_model.mark_suggestion_accepted(
                            typ, category, self.year, self.month
                        )
                    except Exception as e:
                        logger.debug("mark_suggestion_accepted(ignore): %s", e)
                    continue
                try:
                    apply_learning_budget_kind(
                        self.warnings_model.conn,
                        typ,
                        category,
                        kind_dlg.selected_kind(),
                    )
                except Exception as e:
                    logger.warning("Budgetart konnte nicht gespeichert werden: %s", e)

            # Budget anwenden
            months_affected = self.warnings_model.apply_budget_suggestion(
                typ,
                category,
                self.year,
                self.month,
                new_budget,
                remaining_months=apply_remaining,
            )

            # Als angepasst markieren → session-intern + persistent (nächster Monat wieder sichtbar)
            self._applied_categories.add((typ, category))
            try:
                self.warnings_model.mark_suggestion_accepted(
                    typ, category, self.year, self.month
                )
            except Exception as e:
                logger.debug("mark_suggestion_accepted: %s", e)

            applied_count += 1
            total_increase += new_budget - old_budget
            total_months_affected += months_affected

        if applied_count > 0:
            self.data_changed = True
            scope_text = (
                trf(
                    "budget_adjustment.apply.scope_remaining",
                    month=self.month,
                    year=self.year,
                    count=total_months_affected,
                )
                if apply_remaining
                else trf(
                    "budget_adjustment.apply.scope_month",
                    month=self.month,
                    year=self.year,
                )
            )
            show_info(
                self,
                tr("header.budgets_adjusted"),
                trf(
                    "auto.views_budget_adjustment_dialog.634_value_0_budget_s_wurden_erfolgreich_e65aecbd",
                    value_0=(applied_count),
                    value_1=(scope_text),
                    value_2=(
                        tr("dlg.dlg_increase_per_month").format(
                            amount=format_money(total_increase, force_sign=True)
                        )
                    ),
                ),
            )
            # Tabs sofort aktualisieren: sonst wirkt ein übernommener
            # Lernvorschlag so, als sei er nicht in das Budget übernommen worden,
            # obwohl der INSERT bereits gespeichert ist.
            try:
                parent = self.parent()
                if parent is not None and hasattr(parent, "_schedule_refresh_all_tabs"):
                    # fmt: off
                    parent._schedule_refresh_all_tabs(reason="budget adjustment applied")
                    # fmt: on
                elif parent is not None and hasattr(parent, "_refresh_all_tabs"):
                    QTimer.singleShot(0, parent._refresh_all_tabs)
            except Exception as refresh_exc:
                logger.debug("refresh after budget adjustment: %s", refresh_exc)
            # Dialog NICHT schliessen – stattdessen Tabelle neu laden ohne die bereits
            # angepassten Kategorien. So sieht der Nutzer direkt, was noch offen ist.
            self._load_exceedances()

    @staticmethod
    def check_and_show_if_needed(
        parent,
        warnings_model: BudgetWarningsModelExtended,
        budget_model,
        year: int,
        month: int,
        auto_show_threshold: int = 2,
    ) -> bool:
        """
        Prüft ob Budget-Anpassungen nötig sind und zeigt Dialog ggf. automatisch.
        Verwendet dieselbe lookback_months-Einstellung wie der interaktiv geöffnete Dialog,
        damit check_and_show_if_needed und manuelles Öffnen konsistente Ergebnisse liefern.

        Args:
            auto_show_threshold: Ab wie vielen Überschreitungen Dialog automatisch zeigen

        Returns:
            True wenn Dialog gezeigt wurde
        """
        # lookback aus Settings lesen – NICHT hardcoded 6 verwenden
        try:
            lookback = int(Settings().get("budget_suggestion_months", 3) or 3)
        except Exception:
            lookback = 3

        exceedances = warnings_model.check_warnings_extended(
            year, month, lookback_months=lookback
        )

        # Zähle chronische Überschreiter (≥ threshold)
        chronic_count = sum(
            1 for exc in exceedances if exc.exceed_count >= auto_show_threshold
        )

        if chronic_count > 0:
            dialog = BudgetAdjustmentDialog(
                parent, warnings_model, budget_model, year, month
            )
            dialog.exec()
            return True

        return False

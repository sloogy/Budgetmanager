from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QAbstractItemView, QGroupBox,
    QTextEdit
)
from PySide6.QtGui import QColor

from model.budget_warnings_model_extended import BudgetWarningsModelExtended
from model.budget_overview_model import BudgetOverviewModel, BudgetSuggestion
from settings import Settings
from utils.money import format_money, parse_money
from views.ui_colors import ui_colors


import logging
from utils.i18n import tr, trf, display_typ, db_typ_from_display
logger = logging.getLogger(__name__)

class BudgetAdjustmentDialog(QDialog):
    """
    Dialog zur Anzeige von Budget-Abweichungen mit Anpassungsvorschlägen
    
    Zeigt:
    - Kategorien mit häufigen Überschreitungen
    - Historische Daten (wie oft überschritten)
    - Intelligente Budget-Vorschläge
    - Option zur direkten Anpassung
    """
    
    def __init__(self, parent, warnings_model: BudgetWarningsModelExtended, 
                 budget_model, year: int, month: int):
        super().__init__(parent)
        self.warnings_model = warnings_model
        self.budget_model = budget_model
        self.year = year
        self.month = month
        
        self.setWindowTitle(tr("dlg.budget_adjustment"))
        self.setModal(True)
        self.resize(1000, 700)

        # Settings: wie weit wir für Vorschläge/Häufigkeit zurückschauen.
        # Wir verwenden bewusst dieselbe Einstellung wie in der Übersicht,
        # damit der User nur einen Regler hat, der erwartbar wirkt.
        # Achtung: Dieser Dialog soll *denselben* Regler nutzen wie die Übersicht,
        # sonst wirkt das Verhalten "zufällig" (z.B. immer 6 Monate).
        try:
            self._lookback_months = int(Settings().get("budget_suggestion_months", 3) or 3)
        except Exception:
            self._lookback_months = 3
        
        self._already_loaded = False
        self._applied_categories: set[tuple[str, str]] = set()  # (typ, category) bereits angepasst
        self._setup_ui()
        self._load_exceedances()

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
        title = QLabel(trf("dlg.budgetabweichungen_fuer", month=self.month, year=self.year))
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        info = QLabel(
            "ℹ️ " + tr("dlg.dlg_banner_hint")
        )
        info.setWordWrap(True)
        _c0 = ui_colors(self)
        info.setStyleSheet(
            f"padding: 10px; background-color: {_c0.warning_bg}; border-left: 4px solid {_c0.warning}; "
            f"border-radius: 4px; color: {_c0.warning};"
        )
        layout.addWidget(info)
        
        # Tabelle für Überschreitungen
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            tr("header.header_typ"),
            tr("header.category"),
            tr("header.header_budget"),
            tr("header.header_spent"),
            tr("header.header_diff"),
            tr("header.header_pct"),
            trf("dlg.haeufigkeit", months=self._lookback_months),
            tr("lbl.suggestion"),
            tr("header.header_adjust"),
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(7, 120)
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
            type_suggestions = overview_model.get_type_suggestions(
                year=self.year,
                current_month=self.month,
                min_consecutive_months=self._lookback_months,
            )
            # Nur Kategorie-Vorschläge gehören in die editierbare Tabelle.
            all_suggestions: list[BudgetSuggestion] = [
                s for s in cat_suggestions if (s.category or "").strip()
            ]
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
            accepted_this_month = self.warnings_model.get_accepted_for_month(self.year, self.month)
        except Exception:
            accepted_this_month = set()

        excluded = self._applied_categories | accepted_this_month
        if excluded:
            merged_rows = [
                (sug, exc) for (sug, exc) in merged_rows
                if _row_key(sug, exc) not in excluded
            ]

        if not merged_rows:
            _c0 = ui_colors(self)
            self.recommendation_text.setHtml(
                "<p style='color: " + _c0.ok + "; font-weight: bold;'>✓ " + tr("dlg.dlg_all_green") + "</p>"
            )
            return

        # Auto-Generierung kennzeichnen: Wenn keine gespeicherten Warnungsregeln,
        # wurden die Einträge automatisch aus dem Budget erzeugt → transparent für Nutzer.
        _auto = getattr(self.warnings_model, '_auto_generated', False)
        if _auto:
            _ci = ui_colors(self)
            # Info-Banner über die Tabelle (falls noch kein solches Widget vorhanden)
            if not getattr(self, '_lbl_auto_info', None):
                from PySide6.QtWidgets import QLabel as _QLabel
                self._lbl_auto_info = _QLabel()
                self._lbl_auto_info.setWordWrap(True)
                # Einfügen direkt über der Tabelle
                lyt = self.layout()
                tbl_idx = lyt.indexOf(self.table)
                if tbl_idx >= 0:
                    lyt.insertWidget(tbl_idx, self._lbl_auto_info)
            self._lbl_auto_info.setText(
                "ℹ️ " + tr("dlg.dlg_check_info")
            )
            self._lbl_auto_info.setStyleSheet(
                f"padding: 6px 10px; background-color: {_ci.info_bg}; "
                f"border-left: 3px solid {_ci.accent}; border-radius: 3px; "
                f"color: {_ci.text}; font-size: 11px;"
            )
            self._lbl_auto_info.setVisible(True)
        elif getattr(self, '_lbl_auto_info', None):
            self._lbl_auto_info.setVisible(False)

        # Sortieren: Vorschläge mit deficit zuerst, dann surplus, dann reine Warnungen
        def _sort_key(item):
            sug, exc = item
            if sug is None:
                return (2, exc.exceed_count * -1 if exc else 0)
            return (0 if sug.direction == "deficit" else 1, sug.consecutive_months * -1)
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
            spent = exc.spent if exc else 0.0
            percent_used = exc.percent_used if exc else 0.0
            exceed_count = exc.exceed_count if exc else 0
            # Vorschlag aus BudgetOverviewModel (einheitliche Quelle)
            suggestion = sug.suggested_amount if sug else (exc.suggestion if exc else None)

            # Konflikt-Erkennung: Engine schaut nur in Vormonate (use_current_month=False).
            # Wenn der aktuelle Monat klar überschritten ist (spent > budget), die Engine
            # aber aufgrund historischer Unter-Nutzung eine SENKUNG vorschlägt (suggestion < budget),
            # dann ist das Signal widersprüchlich → Vorschlag ausblenden.
            if (suggestion is not None and spent > budget * 1.05
                    and suggestion < budget):
                suggestion = None  # Widerspruch: aktuell über Budget, Vorschlag aber runter

            # Typ
            self.table.setItem(row, 0, QTableWidgetItem(display_typ(typ)))

            # Kategorie
            cat_item = QTableWidgetItem(category)
            is_chronic = (exceed_count >= 3) or (sug and sug.consecutive_months >= 3)
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
            spent_item.setForeground(QColor(c.negative if spent > budget else c.ok))
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
            percent_item = QTableWidgetItem(f"{percent_used:.1f}%")
            percent_item.setTextAlignment(Qt.AlignCenter)
            if percent_used >= 150:
                percent_item.setBackground(QColor(c.error_bg))
            elif percent_used >= 110:
                percent_item.setBackground(QColor(c.warning_bg))
            self.table.setItem(row, 5, percent_item)

            # Häufigkeit / Konsekutive Monate
            if sug and sug.consecutive_months > 0:
                freq_text = f"{sug.consecutive_months}/{self._lookback_months}"
            else:
                freq_text = f"{exceed_count}/{self._lookback_months}"
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
                if suggestion < budget:
                    sugg_item.setBackground(QColor(c.success_bg))
                    sugg_item.setForeground(QColor(c.success_text))
                elif suggestion > budget:
                    sugg_item.setBackground(QColor(c.warning_bg))
                    sugg_item.setForeground(QColor(c.warning_text))
                self.table.setItem(row, 7, sugg_item)

            # Checkbox: auto-check bei Vorschlag vorhanden + chronisch
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            is_surplus = (spent <= budget and suggestion is not None)
            is_chronic_deficit = (exceed_count >= 3) or (sug and sug.consecutive_months >= 3 and sug.direction == "deficit")
            auto = (suggestion is not None) and (is_surplus or is_chronic_deficit)
            chk.setCheckState(Qt.Checked if auto else Qt.Unchecked)
            self.table.setItem(row, 8, chk)

            if suggestion is not None and auto:
                total_adjustment += (suggestion - budget)

        self.table.resizeColumnsToContents()

        # Empfehlungstext generieren – exceedances aus merged_rows für Rückwärtskompatibilität
        exc_list = [exc for _, exc in merged_rows if exc is not None]
        self._generate_recommendations(exc_list, chronic_categories, total_adjustment)

    def _render_type_suggestions(self, type_suggestions: list[BudgetSuggestion]) -> None:
        """Zeigt Typ-Gesamt-Vorschläge separat und nicht editierbar an."""
        if not type_suggestions:
            self.type_info_group.setVisible(False)
            self.type_info_text.clear()
            return
        rows = []
        for sug in type_suggestions:
            rows.append(
                f"• {display_typ(sug.typ)}: {format_money(sug.current_budget)} → {format_money(sug.suggested_amount)}"
            )
        self.type_info_text.setPlainText("\n".join(rows))
        self.type_info_group.setVisible(True)
    def _generate_recommendations(self, exceedances: list, chronic_categories: list, 
                                  total_adjustment: float):
        """Generiert Empfehlungstext basierend auf den Daten"""
        _c = ui_colors(self)
        html = "<div style='font-family: Arial; font-size: 12px;'>"
        
        # Überschrift – differenziert nach Überschreitung und Unterschreitung
        exceeded_cats = [e for e in exceedances if e.spent > e.budget]
        surplus_cats  = [e for e in exceedances if e.spent <= e.budget and e.suggestion is not None]
        header_parts = []
        if exceeded_cats:
            header_parts.append(f"⚠️ " + trf("suggestion.exceeded_n", n=len(exceeded_cats)))
        if surplus_cats:
            header_parts.append(f"💡 " + trf("suggestion.surplus_n", n=len(surplus_cats)))
        header_txt = " &nbsp;|&nbsp; ".join(header_parts) if header_parts else f"ℹ️ {len(exceedances)} Kategorie(n) mit Hinweisen"
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
            from model.typ_constants import TYP_INCOME as _TI, TYP_EXPENSES as _TE, TYP_SAVINGS as _TS
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
                        "⚠️ Einkommenswarnung</h3>"
                        f"<p>Die vorgeschlagenen Budget-Erhöhungen übersteigen "
                        f"das budgetierte Einkommen!</p>"
                        f"<table style='margin: 5px 0;'>"
                        f"<tr><td>Einkommen (Budget):</td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"<strong>{format_money(income_budget)}</strong></td></tr>"
                        f"<tr><td>Ausgaben+Ersparnisse aktuell:</td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"{format_money(current_total)}</td></tr>"
                        f"<tr><td>Ausgaben+Ersparnisse nach Vorschlägen:</td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"<span style='color: {_c.negative}; font-weight: bold;'>"
                        f"{format_money(new_total)}</span></td></tr>"
                        f"<tr><td><strong>Fehlbetrag:</strong></td>"
                        f"<td style='text-align: right; padding-left: 15px;'>"
                        f"<span style='color: {_c.negative}; font-weight: bold;'>"
                        f"{format_money(deficit)}</span></td></tr>"
                        f"</table>"
                        f"<p style='color: {_c.warning};'><strong>"
                        f"→ Ausgaben reduzieren oder Einkommen erhöhen!</strong></p>"
                        "</div>"
                    )
        except Exception as e:
            logger.debug("%s", e)
        
        # Allgemeine Tipps
        html += "<hr/><p><strong>Allgemeine Empfehlungen:</strong></p><ul>"
        
        avg_exceed_count = (sum(e.exceed_count for e in exceedances) / len(exceedances)) if exceedances else 0
        
        if avg_exceed_count >= 3:
            html += "<li>🔴 <strong>Kritisch:</strong> Mehrere Kategorien werden regelmäßig überschritten. "
            html += tr("dlg.dlg_urgent_check") + "</li>"
        elif avg_exceed_count >= 2:
            html += "<li>🟠 <strong>Achtung:</strong> Budgets sollten angepasst werden, um realistischere Ziele zu setzen.</li>"
        else:
            html += "<li>🟡 <strong>Hinweis:</strong> Gelegentliche Überschreitungen sind normal. "
            html += tr("dlg.dlg_structural_changes") + "</li>"
        
        # Spezifische Tipps basierend auf Kategorien
        max_exceedance = max(exceedances, key=lambda x: x.percent_used)
        if max_exceedance.percent_used >= 150:
            html += f"<li>💰 Die Kategorie <strong>{max_exceedance.category}</strong> wurde um "
            html += f"{max_exceedance.percent_used:.0f}% überschritten. "
            html += "Überprüfen Sie, ob hier unerwartete Ausgaben aufgetreten sind.</li>"
        
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
            QMessageBox.information(
                self,
                tr("dlg.keine_auswahl"),
                tr("dlg.dlg_no_min_warnings_selected")
            )
            return
        
        # Frage: Nur diesen Monat oder restliche Monate?
        remaining_months_count = 12 - self.month + 1
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle(tr("dlg.confirm"))
        msg.setText(
            tr("dlg.dlg_adjust_period_question") + "\n\n"
            f"• Nur {self.month:02d}/{self.year}: Anpassung gilt nur für diesen Monat\n"
            f"• Restliche Monate: Anpassung gilt für {self.month:02d}–12/{self.year} "
            f"({remaining_months_count} Monate)"
        )
        
        btn_this_month = msg.addButton(
            f"{tr('dlg.dlg_only_this_month').format(month=self.month, year=self.year)}", QMessageBox.AcceptRole
        )
        btn_remaining = msg.addButton(
            f"{tr('dlg.dlg_remaining_months').format(n=remaining_months_count)}", QMessageBox.AcceptRole
        )
        btn_cancel = msg.addButton(tr("btn.cancel"), QMessageBox.RejectRole)
        
        msg.setDefaultButton(btn_this_month)
        msg.exec()
        
        clicked = msg.clickedButton()
        if clicked == btn_cancel:
            return
        
        apply_remaining = (clicked == btn_remaining)
        
        applied_count = 0
        total_increase = 0
        total_months_affected = 0
        
        for row in selected_rows:
            typ = self.table.item(row, 0).text()
            category = self.table.item(row, 1).text()
            new_budget_str = self.table.item(row, 7).text()
            new_budget = float(parse_money(new_budget_str))
            
            old_budget_str = self.table.item(row, 2).text()
            old_budget = float(parse_money(old_budget_str))
            
            # Budget anwenden
            months_affected = self.warnings_model.apply_budget_suggestion(
                typ, category, self.year, self.month, new_budget,
                remaining_months=apply_remaining
            )
            
            # Als angepasst markieren → session-intern + persistent (nächster Monat wieder sichtbar)
            self._applied_categories.add((typ, category))
            try:
                self.warnings_model.mark_suggestion_accepted(typ, category, self.year, self.month)
            except Exception as e:
                logger.debug("mark_suggestion_accepted: %s", e)
            
            applied_count += 1
            total_increase += (new_budget - old_budget)
            total_months_affected += months_affected
        
        if applied_count > 0:
            scope_text = (
                f"für {self.month:02d}–12/{self.year} ({total_months_affected} Monatswerte)"
                if apply_remaining
                else f"für {self.month:02d}/{self.year}"
            )
            QMessageBox.information(
                self,
                tr("header.budgets_adjusted"),
                f"✓ {applied_count} Budget(s) wurden erfolgreich angepasst {scope_text}.\n\n"
                f"{tr('dlg.dlg_increase_per_month').format(amount=format_money(total_increase, force_sign=True))}\n\n"
                f"Die neuen Budgets sind sofort wirksam.\n"
                f"Bereits angepasste Kategorien werden aus der Liste entfernt."
            )
            # Dialog NICHT schliessen – stattdessen Tabelle neu laden ohne die bereits
            # angepassten Kategorien. So sieht der Nutzer direkt, was noch offen ist.
            self._load_exceedances()
    
    @staticmethod
    def check_and_show_if_needed(parent, warnings_model: BudgetWarningsModelExtended,
                                  budget_model, year: int, month: int,
                                  auto_show_threshold: int = 2) -> bool:
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

        exceedances = warnings_model.check_warnings_extended(year, month, lookback_months=lookback)
        
        # Zähle chronische Überschreiter (≥ threshold)
        chronic_count = sum(1 for exc in exceedances if exc.exceed_count >= auto_show_threshold)
        
        if chronic_count > 0:
            dialog = BudgetAdjustmentDialog(parent, warnings_model, budget_model, year, month)
            dialog.exec()
            return True
        
        return False

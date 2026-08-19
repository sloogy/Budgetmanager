from __future__ import annotations
from utils.accessibility import configure_dialog_tab_order
from utils.notifications import show_info
import logging

logger = logging.getLogger(__name__)
import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QTextEdit,
    QDateEdit,
    QComboBox,
    QMessageBox,
    QProgressBar,
    QAbstractItemView,
    QMenu,
    QGroupBox,
)

from model.savings_goals_model import (
    SavingsGoalBoundsError,
    SavingsGoalsModel,
    SavingsGoal,
    STATUS_SAVING,
    STATUS_RELEASED,
    STATUS_COMPLETED,
    STATUS_LABELS,
    STATUS_ICONS,
)
from model.category_model import CategoryModel
from utils.icons import get_icon
from utils.money import format_money, get_symbol, currency_header
from views.ui_colors import ui_colors
from views.savings_goal_messages import show_savings_goal_bounds_warning
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


class SavingsGoalsDialog(QDialog):
    def __init__(
        self, parent, conn: sqlite3.Connection, initial_goal_id: int | None = None
    ):
        super().__init__(parent)
        self.conn = conn
        self._initial_goal_id = initial_goal_id
        self.goals_model = SavingsGoalsModel(conn)
        self.cat_model = CategoryModel(conn)

        self.setWindowTitle(tr("dlg.savings_goals"))
        self.setModal(True)
        self.resize(1050, 650)

        # Buttons
        self.btn_add = QPushButton(tr("btn.btn_new_goal"))
        self.btn_edit = QPushButton(
            tr("auto.views_savings_goals_dialog.42_bearbeiten_ba02fd7d")
        )
        self.btn_edit.setIcon(get_icon("✏️"))
        self.btn_delete = QPushButton(tr("btn.loeschen_1"))
        self.btn_add_progress = QPushButton(tr("savings.btn.deposit_correction"))
        self.btn_add_progress.setIcon(get_icon("📈"))
        self.btn_sync = QPushButton(
            tr("auto.views_savings_goals_dialog.47_sync_0d895102")
        )
        self.btn_sync.setIcon(get_icon("🔄"))
        # Lifecycle-Buttons
        self.btn_release = QPushButton(tr("savings.btn.partial_release"))
        self.btn_complete = QPushButton(
            tr("auto.views_savings_goals_dialog.51_abschliessen_dfbbbdb2")
        )
        self.btn_complete.setIcon(get_icon("✅"))
        self.btn_reopen = QPushButton(tr("btn.wieder_oeffnen"))
        self.btn_close = QPushButton(tr("btn.close"))

        # Tooltips
        self.btn_release.setToolTip(
            tr(
                "auto.views_savings_goals_dialog.58_sparziel_freigeben_der_aktuelle_sta_cc2b88a8"
            )
        )
        self.btn_complete.setToolTip(
            tr(
                "auto.views_savings_goals_dialog.62_sparziel_abschliessen_wird_archivie_010ae566"
            )
        )
        self.btn_reopen.setToolTip(
            tr(
                "auto.views_savings_goals_dialog.65_sparziel_wieder_zum_sparen_oeffnen__a747e4b3"
            )
        )
        self.btn_sync.setToolTip(tr("tip.sync_tracking"))

        # Flussbestand: Ziel, Einzahlung, Verwendung und Bestand getrennt.
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                tr("lbl.name"),
                tr("savings.column.target"),
                tr("savings.column.contributed"),
                tr("savings.column.used"),
                tr("savings.column.stock"),
                tr("savings.column.remaining_contribution"),
                tr("lbl.savings_goal_progress"),
                tr("savings.column.released_available"),
                tr("lbl.status"),
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(lambda _: self.edit_goal())
        self.table.itemSelectionChanged.connect(self._update_button_states)

        # Layout
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_add_progress)
        btn_layout.addWidget(self.btn_sync)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_release)
        btn_layout.addWidget(self.btn_complete)
        btn_layout.addWidget(self.btn_reopen)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        # Info-Label
        info = QLabel(tr("savings.workflow_hint"))
        info.setWordWrap(True)
        _c = ui_colors(self)
        info.setStyleSheet(
            f"padding: 8px; background-color: {_c.info_bg}; border-radius: 5px; font-size: 11px;"
        )

        layout = QVBoxLayout()
        layout.addWidget(info)
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # Connections
        self.btn_add.clicked.connect(self.add_goal)
        self.btn_edit.clicked.connect(self.edit_goal)
        self.btn_delete.clicked.connect(self.delete_goal)
        self.btn_add_progress.clicked.connect(self.add_progress)
        self.btn_sync.clicked.connect(self.sync_with_tracking)
        self.btn_release.clicked.connect(self._release_goal)
        self.btn_complete.clicked.connect(self._complete_goal)
        self.btn_reopen.clicked.connect(self._reopen_goal)
        self.btn_close.clicked.connect(self.accept)

        self.refresh()
        # Vorauswahl: Wenn ein Sparziel-ID übergeben wurde, entsprechende Zeile selektieren
        if self._initial_goal_id is not None:
            self._select_goal_by_id(self._initial_goal_id)
        configure_dialog_tab_order(self)

    def _select_goal_by_id(self, goal_id: int) -> None:
        """Selektiert die Zeile mit der angegebenen Sparziel-ID."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == goal_id:
                self.table.selectRow(row)
                self.table.scrollTo(self.table.model().index(row, 0))
                break

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        goal = self._selected_goal()
        if not goal:
            return

        menu = QMenu(self)
        act_edit = menu.addAction(tr("btn.edit"))
        act_edit.setIcon(get_icon("✏️"))
        act_progress = menu.addAction(tr("btn.fortschritt_hinzufuegen"))
        act_sync = menu.addAction(tr("dlg.sync_mit_tracking"))
        menu.addSeparator()

        # Lifecycle-Aktionen je nach Status
        act_release = act_complete = act_reopen = None
        if goal.is_saving:
            act_release = menu.addAction(tr("savings.btn.partial_release"))
            act_release.setIcon(get_icon("🔓"))
        if goal.is_saving or goal.is_released:
            act_complete = menu.addAction(
                tr("auto.views_savings_goals_dialog.164_abschliessen_786dc795")
            )
            act_complete.setIcon(get_icon("✅"))
        if goal.is_released or goal.is_completed:
            act_reopen = menu.addAction(tr("btn.wieder_oeffnen_1"))

        menu.addSeparator()
        act_delete = menu.addAction(tr("btn.loeschen_1"))

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self.edit_goal()
        elif chosen == act_progress:
            self.add_progress()
        elif chosen == act_sync:
            self.sync_with_tracking()
        elif chosen == act_delete:
            self.delete_goal()
        elif act_release and chosen == act_release:
            self._release_goal()
        elif act_complete and chosen == act_complete:
            self._complete_goal()
        elif act_reopen and chosen == act_reopen:
            self._reopen_goal()

    def _selected_goal(self) -> SavingsGoal | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        goal_id = item.data(Qt.UserRole)
        return self.goals_model.get(goal_id)

    def _update_button_states(self):
        """Aktiviert/deaktiviert Lifecycle-Buttons je nach Status des selektierten Ziels."""
        goal = self._selected_goal()
        has_goal = goal is not None

        self.btn_edit.setEnabled(has_goal)
        self.btn_delete.setEnabled(has_goal)
        self.btn_add_progress.setEnabled(has_goal)
        self.btn_sync.setEnabled(has_goal)

        self.btn_release.setEnabled(
            bool(
                has_goal
                and not goal.is_completed
                and goal.current_stock > goal.released_available + 0.005
            )
        )
        self.btn_complete.setEnabled(has_goal and (goal.is_saving or goal.is_released))
        self.btn_reopen.setEnabled(has_goal and (goal.is_released or goal.is_completed))

    def refresh(self):
        goals = self.goals_model.list_all()
        self.table.setRowCount(0)

        for goal in goals:
            r = self.table.rowCount()
            self.table.insertRow(r)

            name_item = QTableWidgetItem(goal.name)
            name_item.setIcon(get_icon(goal.status_icon))
            name_item.setData(Qt.UserRole, goal.id)
            tooltip_parts = [trf("savings.tooltip.status", status=goal.status_label)]
            if goal.category:
                tooltip_parts.append(
                    trf("savings.tooltip.category", category=goal.category)
                )
            if goal.deadline:
                tooltip_parts.append(
                    trf("savings.tooltip.deadline", deadline=goal.deadline)
                )
            tooltip_parts.extend(
                [
                    trf(
                        "savings.tooltip.contributed",
                        amount=format_money(goal.contributed_amount),
                    ),
                    trf(
                        "savings.tooltip.used",
                        amount=format_money(goal.withdrawn_amount),
                    ),
                    trf(
                        "savings.tooltip.stock", amount=format_money(goal.current_stock)
                    ),
                ]
            )
            if goal.notes:
                tooltip_parts.append(trf("savings.tooltip.note", note=goal.notes))
            name_item.setToolTip("\n".join(tooltip_parts))
            self.table.setItem(r, 0, name_item)

            values = [
                goal.target_amount,
                goal.contributed_amount,
                goal.withdrawn_amount,
                goal.current_stock,
                goal.remaining_contribution,
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(format_money(value))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 3 and value > 0:
                    item.setForeground(QColor(ui_colors(self).negative))
                if col == 5 and value <= 0:
                    item.setForeground(QColor(ui_colors(self).ok))
                self.table.setItem(r, col, item)

            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(int(goal.progress_percent))
            progress.setFormat(f"{goal.progress_percent:.1f}%")
            self.table.setCellWidget(r, 6, progress)

            release_text = (
                format_money(goal.released_available)
                if goal.released_available > 0
                else "-"
            )
            release_item = QTableWidgetItem(release_text)
            release_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            release_item.setToolTip(
                trf(
                    "savings.tooltip.release_flow",
                    approved=format_money(goal.released_amount),
                    used=format_money(goal.withdrawn_amount),
                    available=format_money(goal.released_available),
                )
            )
            self.table.setItem(r, 7, release_item)

            status_item = QTableWidgetItem(goal.status_label)
            status_item.setIcon(get_icon(goal.status_icon))
            status_item.setTextAlignment(Qt.AlignCenter)
            if goal.is_completed:
                status_item.setForeground(QColor(ui_colors(self).ok))
            self.table.setItem(r, 8, status_item)

            if goal.is_completed:
                for col in range(self.table.columnCount()):
                    item = self.table.item(r, col)
                    if item:
                        item.setForeground(QColor(ui_colors(self).text_dim))

        self.table.resizeColumnsToContents()
        self._update_button_states()

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────
    def add_goal(self):
        dlg = EditGoalDialog(self, self.conn)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                self.goals_model.create(
                    name=data["name"],
                    target_amount=data["target_amount"],
                    current_amount=data["current_amount"],
                    deadline=data["deadline"],
                    category=data["category"],
                    notes=data["notes"],
                )
            except SavingsGoalBoundsError as e:
                show_savings_goal_bounds_warning(self, e)
                return
            self.refresh()

    def edit_goal(self):
        goal = self._selected_goal()
        if not goal:
            show_info(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return

        dlg = EditGoalDialog(self, self.conn, goal)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                self.goals_model.update(
                    goal_id=goal.id,
                    name=data["name"],
                    target_amount=data["target_amount"],
                    current_amount=data["current_amount"],
                    deadline=data["deadline"],
                    category=data["category"],
                    notes=data["notes"],
                )
            except SavingsGoalBoundsError as e:
                show_savings_goal_bounds_warning(self, e)
                return
            self.refresh()

    def delete_goal(self):
        goal = self._selected_goal()
        if not goal:
            show_info(self, tr("msg.info"), tr("msg.please_select_goal"))
            return

        if (
            QMessageBox.question(
                self,
                tr("common.delete"),
                trf(
                    "auto.views_savings_goals_dialog.350_sparziel_value_0_wirklich_loeschen_a0a55e23",
                    value_0=(goal.name),
                ),
            )
            != QMessageBox.Yes
        ):
            return

        self.goals_model.delete(goal.id)
        self.refresh()

    def add_progress(self):
        goal = self._selected_goal()
        if not goal:
            show_info(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return

        dlg = AddProgressDialog(self, goal)
        if dlg.exec() == QDialog.Accepted:
            amount = dlg.get_amount()
            try:
                self.goals_model.add_progress(goal.id, amount)
            except SavingsGoalBoundsError as e:
                show_savings_goal_bounds_warning(self, e)
                return
            self.refresh()

    def sync_with_tracking(self):
        goal = self._selected_goal()
        if not goal:
            show_info(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return

        if not goal.category:
            show_info(
                self,
                tr("dlg.keine_kategorie"),
                tr(
                    "auto.views_savings_goals_dialog.378_dieses_sparziel_ist_mit_keiner_kate_b42a28db"
                ),
            )
            return

        old_amount = goal.current_amount
        try:
            new_amount = self.goals_model.sync_with_tracking(goal.id)
        except SavingsGoalBoundsError as e:
            show_savings_goal_bounds_warning(self, e)
            return

        show_info(
            self,
            tr("auto.views_savings_goals_dialog.386_synchronisiert_2f5168bf"),
            trf(
                "auto.views_savings_goals_dialog.387_sparziel_value_0_wurde_mit_tracking_3a7d4952",
                value_0=(goal.name),
                value_1=(goal.category),
                value_2=(format_money(old_amount)),
                value_3=(format_money(new_amount)),
                value_4=(format_money(new_amount - old_amount, force_sign=True)),
            ),
        )
        self.refresh()

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────
    def _release_goal(self):
        """Gibt einen Teil des Bestands frei, ohne das Sparziel zu verlieren."""
        goal = self._selected_goal()
        if not goal:
            show_info(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return
        if goal.is_completed:
            show_info(self, tr("msg.info"), tr("savings.msg.completed_no_release"))
            return

        dlg = PartialReleaseDialog(self, goal)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            result = self.goals_model.release_partial(goal.id, dlg.get_amount())
        except SavingsGoalBoundsError as exc:
            show_savings_goal_bounds_warning(self, exc)
            return
        if result:
            show_info(
                self,
                tr("savings.btn.partial_release"),
                trf(
                    "savings.msg.partial_release_done",
                    name=result.name,
                    amount=format_money(dlg.get_amount()),
                    available=format_money(result.released_available),
                ),
            )
        self.refresh()

    def _complete_goal(self):
        """Sparziel abschliessen."""
        goal = self._selected_goal()
        if not goal:
            show_info(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return

        extra = ""
        if goal.is_released:
            spent = self.goals_model.get_spent_amount(goal.id)
            extra = trf("savings.msg.spent_since_release", amount=format_money(spent))

        reply = QMessageBox.question(
            self,
            tr("auto.views_savings_goals_dialog.444_sparziel_abschliessen_81af1e70"),
            trf(
                "savings.msg.complete_confirm",
                name=goal.name,
                amount=format_money(goal.current_amount),
                extra=extra,
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.goals_model.complete(goal.id)
        self.refresh()

    def _reopen_goal(self):
        """Sparziel wieder zum Sparen öffnen."""
        goal = self._selected_goal()
        if not goal:
            show_info(self, tr("msg.info"), tr("savings.msg.select_goal"))
            return

        reply = QMessageBox.question(
            self,
            tr("btn.sparziel_wieder_oeffnen"),
            trf(
                "auto.views_savings_goals_dialog.465_sparziel_value_0_wieder_zum_sparen__1510830d",
                value_0=(goal.name),
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.goals_model.reopen(goal.id)
        self.refresh()


class EditGoalDialog(QDialog):
    def __init__(
        self, parent, conn: sqlite3.Connection, goal: SavingsGoal | None = None
    ):
        super().__init__(parent)
        self.conn = conn
        self.goal = goal
        self.cat_model = CategoryModel(conn)

        self.setWindowTitle(tr("dlg.savings_goals"))
        self.setModal(True)
        self.resize(500, 400)

        # Felder
        self.name_edit = QLineEdit()
        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 1000000)
        self.target_spin.setDecimals(2)
        self.target_spin.setSuffix(f" {get_symbol()}")

        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0, 1000000)
        self.current_spin.setDecimals(2)
        self.current_spin.setSuffix(f" {get_symbol()}")

        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDate(datetime.now().date())
        self.deadline_edit.setSpecialValueText("Kein Datum")

        self.category_combo = QComboBox()
        self.category_combo.addItem(
            tr("auto.views_savings_goals_dialog.506_keine_8218b1ac")
        )
        for typ in [TYP_SAVINGS, TYP_INCOME, TYP_EXPENSES]:
            pairs = []
            if hasattr(self.cat_model, "list_names_tree"):
                try:
                    pairs = self.cat_model.list_names_tree(typ)
                except Exception:
                    pairs = []
            if pairs:
                for label, real in pairs:
                    self.category_combo.addItem(
                        trf(
                            "auto.views_savings_goals_dialog.516_value_0_value_1_e61189ab",
                            value_0=(display_typ(typ)),
                            value_1=(label),
                        ),
                        real,
                    )
            else:
                for cat in self.cat_model.list_names(typ):
                    self.category_combo.addItem(
                        trf(
                            "auto.views_savings_goals_dialog.519_value_0_value_1_016e0b40",
                            value_0=(typ),
                            value_1=(cat),
                        ),
                        cat,
                    )

        self.notes_edit = QTextEdit()

        # Werte setzen
        if goal:
            self.name_edit.setText(goal.name)
            self.target_spin.setValue(goal.target_amount)
            self.current_spin.setValue(goal.contributed_amount)
            if goal.deadline:
                try:
                    d = datetime.fromisoformat(goal.deadline).date()
                    self.deadline_edit.setDate(d)
                except Exception as e:
                    logger.debug("date parse error: %s", e)
            if goal.category:
                idx = self.category_combo.findData(goal.category)
                if idx >= 0:
                    self.category_combo.setCurrentIndex(idx)
            if goal.notes:
                self.notes_edit.setPlainText(goal.notes)

        # Layout
        layout = QVBoxLayout()

        layout.addWidget(QLabel(tr("lbl.lbl_goal_name")))
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel(tr("lbl.lbl_target_amount")))
        layout.addWidget(self.target_spin)

        layout.addWidget(QLabel(tr("savings.label.contributed_amount")))
        layout.addWidget(self.current_spin)

        layout.addWidget(QLabel(tr("lbl.lbl_deadline")))
        layout.addWidget(self.deadline_edit)

        layout.addWidget(QLabel(tr("lbl.category")))
        layout.addWidget(self.category_combo)

        sync_hint = QLabel(
            tr(
                "auto.views_savings_goals_dialog.560_i_small_tipp_wenn_eine_kategorie_au_ddfbcc66"
            )
        )
        sync_hint.setWordWrap(True)
        sync_hint.setStyleSheet(f"color: {ui_colors(self).text_dim}; padding: 5px;")
        layout.addWidget(sync_hint)

        layout.addWidget(QLabel(tr("lbl.lbl_notes")))
        layout.addWidget(self.notes_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(tr("btn.ok"))
        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)
        self.setLayout(layout)
        configure_dialog_tab_order(self)

    def get_data(self):
        category = self.category_combo.currentData()
        deadline = (
            self.deadline_edit.date().toString("yyyy-MM-dd")
            if self.deadline_edit.date().isValid()
            else None
        )

        return {
            "name": self.name_edit.text().strip(),
            "target_amount": self.target_spin.value(),
            "current_amount": self.current_spin.value(),
            "deadline": deadline,
            "category": category,
            "notes": self.notes_edit.toPlainText().strip(),
        }


class PartialReleaseDialog(QDialog):
    """Betrag für eine Teilfreigabe auswählen."""

    def __init__(self, parent, goal: SavingsGoal):
        super().__init__(parent)
        self.goal = goal
        self.setWindowTitle(tr("savings.btn.partial_release"))
        self.setModal(True)

        max_additional = max(0.0, goal.current_stock - goal.released_available)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.0, max_additional)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSuffix(f" {get_symbol()}")
        self.amount_spin.setValue(max_additional)

        layout = QVBoxLayout(self)
        info = QLabel(
            trf(
                "savings.partial_release.info",
                stock=format_money(goal.current_stock),
                already=format_money(goal.released_available),
                maximum=format_money(max_additional),
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addWidget(QLabel(tr("savings.partial_release.amount")))
        layout.addWidget(self.amount_spin)

        row = QHBoxLayout()
        ok = QPushButton(tr("btn.ok"))
        cancel = QPushButton(tr("btn.cancel"))
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row.addStretch()
        row.addWidget(ok)
        row.addWidget(cancel)
        layout.addLayout(row)
        configure_dialog_tab_order(self)

    def get_amount(self) -> float:
        return float(self.amount_spin.value())


class AddProgressDialog(QDialog):
    def __init__(self, parent, goal: SavingsGoal):
        super().__init__(parent)
        self.goal = goal

        self.setWindowTitle(trf("btn.fortschritt_hinzufuegen_goalname", name=goal.name))
        self.setModal(True)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(-1000000, 1000000)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSuffix(f" {get_symbol()}")
        self.amount_spin.setValue(0)

        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                trf(
                    "auto.views_savings_goals_dialog.612_aktuell_value_0_05ac9b67",
                    value_0=(format_money(goal.contributed_amount)),
                )
            )
        )
        layout.addWidget(
            QLabel(
                trf(
                    "auto.views_savings_goals_dialog.613_ziel_value_0_3aea07af",
                    value_0=(format_money(goal.target_amount)),
                )
            )
        )
        layout.addWidget(
            QLabel(
                trf(
                    "auto.views_savings_goals_dialog.614_restbetrag_value_0_711be043",
                    value_0=(format_money(goal.remaining_contribution)),
                )
            )
        )
        if goal.is_released:
            layout.addWidget(
                QLabel(
                    trf(
                        "auto.views_savings_goals_dialog.616_status_freigegeben_eingef_value_0_6728eed9",
                        value_0=(format_money(goal.released_amount)),
                    )
                )
            )
        layout.addSpacing(10)
        layout.addWidget(QLabel(tr("btn.betrag_hinzufuegen")))
        layout.addWidget(self.amount_spin)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(tr("btn.ok"))
        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)
        self.setLayout(layout)
        configure_dialog_tab_order(self)

    def get_amount(self):
        return self.amount_spin.value()

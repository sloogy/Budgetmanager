from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from model.category_model import Category, CategoryModel
from utils.i18n import display_typ, tr, trf


@dataclass(frozen=True)
class CategoryDeleteDecision:
    action: str
    reassign_to_id: int | None = None


class CategoryDeleteDialog(QDialog):
    """Zentraler UI-Dialog für sichere Kategorie-Löschung.

    Die Datenlogik liegt bewusst in CategoryModel. Dieser Dialog sammelt nur
    die Entscheidung des Nutzers: löschen, komplett löschen oder umhängen.
    """

    def __init__(self, parent=None, *, conn: sqlite3.Connection, cat_ids: list[int]):
        super().__init__(parent)
        self.conn = conn
        self.model = CategoryModel(conn)
        self.cat_ids = sorted({int(i) for i in cat_ids})
        self._decision: CategoryDeleteDecision | None = None

        self.categories: list[Category] = [
            c for c in (self.model.get_by_id(i) for i in self.cat_ids) if c
        ]
        self.setWindowTitle(tr("category_delete.title"))
        self.setModal(True)
        self.setMinimumWidth(560)
        self._build_ui()
        self._update_target_enabled()

    @property
    def decision(self) -> CategoryDeleteDecision | None:
        return self._decision

    def _usage_summary(self) -> str:
        total = {
            "children": 0,
            "budget": 0,
            "tracking": 0,
            "favorites": 0,
            "budget_warnings": 0,
            "recurring_transactions": 0,
            "suggestion_accepted": 0,
            "savings_goals": 0,
        }
        last_dates: list[str] = []
        for cat_id in self.cat_ids:
            usage = self.model.get_category_usage(cat_id)
            for key in total:
                total[key] += int(usage.get(key, 0) or 0)
            if usage.get("last_booking_date"):
                last_dates.append(str(usage["last_booking_date"]))

        names = ", ".join(c.name for c in self.categories[:5])
        if len(self.categories) > 5:
            names += trf("category_delete.more_names", count=len(self.categories) - 5)

        last = max(last_dates) if last_dates else tr("category_delete.no_booking_date")
        return trf(
            "category_delete.summary",
            count=len(self.categories),
            names=names,
            children=total["children"],
            budget=total["budget"],
            tracking=total["tracking"],
            favorites=total["favorites"],
            warnings=total["budget_warnings"],
            recurring=total["recurring_transactions"],
            goals=total["savings_goals"],
            last=last,
        )

    def _common_typ(self) -> str | None:
        typs = {c.typ for c in self.categories}
        return next(iter(typs)) if len(typs) == 1 else None

    def _target_candidates(self) -> list[Category]:
        typ = self._common_typ()
        if not typ:
            return []
        selected = set(self.cat_ids)
        return [c for c in self.model.list(typ) if int(c.id) not in selected]

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        intro = QLabel(self._usage_summary())
        intro.setWordWrap(True)
        layout.addWidget(intro)

        note = QLabel(tr("category_delete.children_note"))
        note.setWordWrap(True)
        layout.addWidget(note)

        group = QGroupBox(tr("category_delete.choose_action"))
        group_layout = QVBoxLayout(group)

        self.rb_until_last = QRadioButton(tr("category_delete.option_until_last"))
        self.rb_reassign = QRadioButton(tr("category_delete.option_reassign"))
        self.rb_delete_all = QRadioButton(tr("category_delete.option_delete_all"))
        self.rb_until_last.setChecked(True)

        group_layout.addWidget(self.rb_until_last)
        group_layout.addWidget(self.rb_reassign)
        group_layout.addWidget(self.rb_delete_all)
        layout.addWidget(group)

        form = QFormLayout()
        self.target_combo = QComboBox()
        candidates = self._target_candidates()
        for c in candidates:
            self.target_combo.addItem(f"{display_typ(c.typ)} – {c.name}", int(c.id))
        if not candidates:
            self.target_combo.addItem(tr("category_delete.no_target"), None)
            self.rb_reassign.setEnabled(False)
            self.rb_reassign.setToolTip(tr("catdel.no_targets"))
            self.target_combo.setToolTip(tr("catdel.no_targets"))
        form.addRow(tr("category_delete.target_label"), self.target_combo)
        layout.addLayout(form)

        self.rb_until_last.toggled.connect(self._update_target_enabled)
        self.rb_reassign.toggled.connect(self._update_target_enabled)
        self.rb_delete_all.toggled.connect(self._update_target_enabled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_target_enabled(self) -> None:
        enabled = self.rb_reassign.isChecked() and self.rb_reassign.isEnabled()
        self.target_combo.setEnabled(enabled)

    def _accept(self) -> None:
        if self.rb_reassign.isChecked():
            target_id = self.target_combo.currentData()
            if target_id is None:
                return
            self._decision = CategoryDeleteDecision("reassign", int(target_id))
        elif self.rb_delete_all.isChecked():
            self._decision = CategoryDeleteDecision("delete_all", None)
        else:
            self._decision = CategoryDeleteDecision("delete_until_last_booking", None)
        self.accept()


def ask_category_delete_decision(
    parent, *, conn: sqlite3.Connection, cat_ids: list[int]
) -> CategoryDeleteDecision | None:
    dlg = CategoryDeleteDialog(parent, conn=conn, cat_ids=cat_ids)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.decision

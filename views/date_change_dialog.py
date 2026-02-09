from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QDialogButtonBox
)


class DateChangeDialog(QDialog):
    """Kleiner Dialog zum Ändern des Buchungsdatums (auch für mehrere Einträge)."""

    def __init__(self, parent=None, *, default_date: date | None = None, count: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Buchungsdatum ändern")
        self.setMinimumWidth(360)

        root = QVBoxLayout()

        msg = QLabel(
            f"Ausgewählte Einträge: <b>{int(count)}</b><br>"
            "Neues Buchungsdatum auswählen:"
        )
        msg.setWordWrap(True)
        root.addWidget(msg)

        row = QHBoxLayout()
        row.addWidget(QLabel("Datum:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setDate((default_date or date.today()))
        row.addWidget(self.date_edit, 1)
        root.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setLayout(root)

    def get_date(self) -> date:
        return self.date_edit.date().toPython()

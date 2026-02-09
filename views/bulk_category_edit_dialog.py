from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QCheckBox, QDialogButtonBox
)


class BulkCategoryEditDialog(QDialog):
    """Batch-Editor für Kategorien.

    Kann mehrere Kategorien gleichzeitig anpassen:
    - Typ
    - Fixkosten (an/aus/unverändert)
    - Wiederkehrend (an/aus/unverändert)
    - Tag (1-31, optional)
    """

    def __init__(self, parent=None, *, count: int = 1, types: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Mehrfach bearbeiten")
        self.setMinimumWidth(420)

        root = QVBoxLayout()

        info = QLabel(f"Ausgewählte Kategorien: <b>{int(count)}</b>")
        info.setWordWrap(True)
        root.addWidget(info)

        # Typ
        row_typ = QHBoxLayout()
        row_typ.addWidget(QLabel("Typ:"))
        self.cmb_typ = QComboBox()
        self.cmb_typ.addItem("(unverändert)", None)
        for t in (types or ["Ausgaben", "Einkommen", "Ersparnisse"]):
            self.cmb_typ.addItem(t, t)
        row_typ.addWidget(self.cmb_typ, 1)
        root.addLayout(row_typ)

        # Fixkosten
        row_fix = QHBoxLayout()
        row_fix.addWidget(QLabel("Fixkosten:"))
        self.cmb_fix = QComboBox()
        self.cmb_fix.addItem("(unverändert)", None)
        self.cmb_fix.addItem("An", True)
        self.cmb_fix.addItem("Aus", False)
        row_fix.addWidget(self.cmb_fix, 1)
        root.addLayout(row_fix)

        # Wiederkehrend
        row_rec = QHBoxLayout()
        row_rec.addWidget(QLabel("Wiederkehrend:"))
        self.cmb_rec = QComboBox()
        self.cmb_rec.addItem("(unverändert)", None)
        self.cmb_rec.addItem("An", True)
        self.cmb_rec.addItem("Aus", False)
        row_rec.addWidget(self.cmb_rec, 1)
        root.addLayout(row_rec)

        # Tag
        row_day = QHBoxLayout()
        self.chk_set_day = QCheckBox("Tag setzen")
        self.spin_day = QSpinBox()
        self.spin_day.setRange(1, 31)
        self.spin_day.setValue(1)
        self.spin_day.setEnabled(False)
        self.chk_set_day.toggled.connect(self.spin_day.setEnabled)
        # UX: Wer einen Tag setzen will, meint praktisch immer "Wiederkehrend".
        # Deshalb schalten wir beim Aktivieren automatisch auf "An" (sofern unverändert).
        self.chk_set_day.toggled.connect(self._on_set_day_toggled)
        row_day.addWidget(self.chk_set_day)
        row_day.addWidget(self.spin_day, 1)
        root.addLayout(row_day)

        hint = QLabel("Hinweis: Der Tag wird nur verwendet, wenn Wiederkehrend aktiv ist.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 10px;")
        root.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setLayout(root)

    def _on_set_day_toggled(self, on: bool) -> None:
        if not on:
            return
        # Wenn Wiederkehrend noch auf "(unverändert)" steht, auf "An" setzen
        try:
            if self.cmb_rec.currentData() is None:
                # Index 1 = "An" (siehe Aufbau oben)
                self.cmb_rec.setCurrentIndex(1)
        except Exception:
            pass

    def values(self) -> dict:
        def _data(cb: QComboBox):
            return cb.currentData()

        typ_val = _data(self.cmb_typ)

        set_day = bool(self.chk_set_day.isChecked())
        rec_val = _data(self.cmb_rec)
        # Wenn Tag gesetzt werden soll, aber Rec noch "unverändert" war,
        # interpretieren wir das als "Wiederkehrend an".
        if set_day and rec_val is None:
            rec_val = True

        return {
            "typ": typ_val,
            "fix": _data(self.cmb_fix),
            "rec": rec_val,
            "set_day": set_day,
            "day": int(self.spin_day.value()),
        }

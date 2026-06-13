"""Erstes-Start Sprach-Auswahl Dialog."""
from __future__ import annotations
from utils.i18n import tr, trf
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout,
    QPushButton, QListWidget, QListWidgetItem, QComboBox, QGroupBox
)
from views.ui_colors import ui_colors
from utils.money import CURRENCIES, CURRENCY_CODES


class LanguageSelectDialog(QDialog):
    """Erscheint beim ersten Start – User wählt die Sprache."""

    LANGUAGES = [
        ("de", "🇩🇪  Deutsch"),
        ("en", "🇬🇧  English"),
        ("fr", "🇫🇷  Français"),
    ]

    LANGUAGE_DEFAULTS = {
        "de": {"currency": "CHF", "recurring_day": 25},
        "en": {"currency": "USD", "recurring_day": 1},
        "fr": {"currency": "CHF", "recurring_day": 25},
    }

    def __init__(
        self,
        parent=None,
        *,
        current: str = "de",
        current_currency: str = "CHF",
        current_recurring_day: int | None = 25,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr('auto.views_language_select_dialog.22_language_sprache_langue_cec30925'))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(420)
        self.selected_code = current
        self.selected_currency = current_currency if current_currency in CURRENCIES else "CHF"
        try:
            self.selected_recurring_day = int(current_recurring_day or 0)
        except Exception:
            self.selected_recurring_day = 25
        self._currency_touched = False
        self._day_touched = False
        self._build_ui(current, self.selected_currency, self.selected_recurring_day)

    def _build_ui(
        self,
        current: str = "de",
        current_currency: str = "CHF",
        current_recurring_day: int = 25,
    ):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        c = ui_colors(self)
        lbl = QLabel(
            trf('auto.views_language_select_dialog.34_h3_style_margin_0_welcome_willkomme_eef30112', value_0=(c.text_dim))
        )
        lbl.setTextFormat(Qt.RichText)
        lay.addWidget(lbl)

        self.list = QListWidget()
        self.list.setSpacing(4)
        default_row = 0
        for i, (code, label) in enumerate(self.LANGUAGES):
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, code)
            item.setSizeHint(item.sizeHint().__class__(0, 42))
            self.list.addItem(item)
            if code == current:
                default_row = i
        self.list.setCurrentRow(default_row)
        self.list.itemDoubleClicked.connect(self._accept)
        self.list.currentItemChanged.connect(self._on_language_changed)
        lay.addWidget(self.list)

        gb_region = QGroupBox(tr("setup.region_box"))
        form = QFormLayout(gb_region)

        self.cmb_currency = QComboBox()
        for code in CURRENCY_CODES:
            self.cmb_currency.addItem(CURRENCIES[code]["label"], code)
        idx_currency = self.cmb_currency.findData(current_currency if current_currency in CURRENCIES else "CHF")
        self.cmb_currency.setCurrentIndex(max(0, idx_currency))
        self.cmb_currency.currentIndexChanged.connect(lambda _i: setattr(self, "_currency_touched", True))
        form.addRow(tr("settings.currency"), self.cmb_currency)

        self.cmb_recurring_day = QComboBox()
        self.cmb_recurring_day.addItem(tr("settings.no_preferred_day"), 0)
        for day in range(1, 29):
            self.cmb_recurring_day.addItem(str(day), day)
        self.cmb_recurring_day.addItem(tr("settings.month_end"), 31)
        idx_day = self.cmb_recurring_day.findData(current_recurring_day)
        if idx_day < 0:
            idx_day = self.cmb_recurring_day.findData(25)
        self.cmb_recurring_day.setCurrentIndex(max(0, idx_day))
        self.cmb_recurring_day.currentIndexChanged.connect(lambda _i: setattr(self, "_day_touched", True))
        self.cmb_recurring_day.setToolTip(tr("setup.preferred_day_tip"))
        form.addRow(tr("settings.recurring_preferred_day"), self.cmb_recurring_day)

        hint = QLabel(tr("setup.region_hint"))
        hint.setWordWrap(True)
        form.addRow("", hint)
        lay.addWidget(gb_region)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(tr('auto.views_language_select_dialog.57_ok_6128635b'))
        btn_ok.setDefault(True)
        btn_ok.setMinimumHeight(36)
        btn_ok.clicked.connect(self._accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

    def _on_language_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None):
        if current is None:
            return
        code = current.data(Qt.UserRole)
        defaults = self.LANGUAGE_DEFAULTS.get(code, {})
        if not self._currency_touched:
            idx = self.cmb_currency.findData(defaults.get("currency", "CHF"))
            if idx >= 0:
                blocker = QSignalBlocker(self.cmb_currency)
                self.cmb_currency.setCurrentIndex(idx)
                del blocker
        if not self._day_touched:
            idx = self.cmb_recurring_day.findData(defaults.get("recurring_day", 25))
            if idx >= 0:
                blocker = QSignalBlocker(self.cmb_recurring_day)
                self.cmb_recurring_day.setCurrentIndex(idx)
                del blocker

    def _accept(self):
        item = self.list.currentItem()
        if item:
            self.selected_code = item.data(Qt.UserRole)
        self.selected_currency = self.cmb_currency.currentData() or "CHF"
        self.selected_recurring_day = int(self.cmb_recurring_day.currentData() or 0)
        self.accept()

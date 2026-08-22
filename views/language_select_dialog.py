"""Erstes-Start Sprach-Auswahl Dialog."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from utils.i18n import set_language, tr, trf
from utils.money import (
    CURRENCIES,
    CURRENCY_CODES,
    LANGUAGE_NUMBER_FORMAT_DEFAULTS,
    NUMBER_FORMAT_CODES,
    NUMBER_FORMATS,
    normalize_number_format,
)
from views.ui_colors import ui_colors


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
        current_number_format: str = "swiss",
    ):
        super().__init__(parent)
        # Dialog ist selbst die Sprachwahl: beim Umschalten live übersetzen.
        self.setWindowTitle(
            tr("auto.views_language_select_dialog.22_language_sprache_langue_cec30925")
        )
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(420)
        self.selected_code = current
        self.selected_currency = (
            current_currency if current_currency in CURRENCIES else "CHF"
        )
        self.selected_number_format = normalize_number_format(current_number_format)
        try:
            self.selected_recurring_day = int(current_recurring_day or 0)
        except Exception:
            self.selected_recurring_day = 25
        self._currency_touched = False
        self._day_touched = False
        self._numfmt_touched = False
        self._build_ui(current, self.selected_currency, self.selected_recurring_day)

    def _build_ui(
        self,
        current: str = "de",
        current_currency: str = "CHF",
        current_recurring_day: int = 25,
    ):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        ui_colors(self)
        self.lbl_welcome = QLabel()
        self.lbl_welcome.setTextFormat(Qt.RichText)
        lay.addWidget(self.lbl_welcome)

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

        self.gb_region = QGroupBox()
        form = QFormLayout(self.gb_region)

        self.lbl_currency = QLabel()
        self.cmb_currency = QComboBox()
        for code in CURRENCY_CODES:
            self.cmb_currency.addItem(self._currency_label(code), code)
        idx_currency = self.cmb_currency.findData(
            current_currency if current_currency in CURRENCIES else "CHF"
        )
        self.cmb_currency.setCurrentIndex(max(0, idx_currency))
        self.cmb_currency.currentIndexChanged.connect(
            lambda _i: setattr(self, "_currency_touched", True)
        )
        form.addRow(self.lbl_currency, self.cmb_currency)

        self.lbl_number_format = QLabel()
        self.cmb_number_format = QComboBox()
        for code in NUMBER_FORMAT_CODES:
            self.cmb_number_format.addItem(self._number_format_label(code), code)
        idx_nf = self.cmb_number_format.findData(self.selected_number_format)
        if idx_nf < 0:
            idx_nf = self.cmb_number_format.findData("swiss")
        self.cmb_number_format.setCurrentIndex(max(0, idx_nf))
        self.cmb_number_format.currentIndexChanged.connect(
            lambda _i: setattr(self, "_numfmt_touched", True)
        )
        form.addRow(self.lbl_number_format, self.cmb_number_format)

        self.lbl_recurring_day = QLabel()
        self.cmb_recurring_day = QComboBox()
        self._fill_recurring_day_combo(current_recurring_day)
        self.cmb_recurring_day.currentIndexChanged.connect(
            lambda _i: setattr(self, "_day_touched", True)
        )
        form.addRow(self.lbl_recurring_day, self.cmb_recurring_day)

        self.lbl_region_hint = QLabel()
        self.lbl_region_hint.setWordWrap(True)
        form.addRow("", self.lbl_region_hint)
        lay.addWidget(self.gb_region)

        btn_row = QHBoxLayout()
        self.btn_ok = QPushButton()
        self.btn_ok.setDefault(True)
        self.btn_ok.setMinimumHeight(36)
        self.btn_ok.clicked.connect(self._accept)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_ok)
        lay.addLayout(btn_row)

        self._retranslate_ui()

    def _currency_label(self, code: str) -> str:
        return (
            tr(f"currency.{code}")
            if tr(f"currency.{code}") != f"currency.{code}"
            else CURRENCIES[code]["label"]
        )

    def _number_format_label(self, code: str) -> str:
        key_map = {
            "swiss": "number_format.swiss",
            "german": "number_format.german",
            "french": "number_format.french",
            "anglo": "number_format.anglo",
        }
        key = key_map.get(code, "")
        label = tr(key) if key else ""
        return label if label and label != key else NUMBER_FORMATS[code]["label"]

    def _fill_recurring_day_combo(self, current_day: int | None = None) -> None:
        current = (
            self.cmb_recurring_day.currentData()
            if self.cmb_recurring_day.count()
            else current_day
        )
        if current is None:
            current = current_day
        blocker = QSignalBlocker(self.cmb_recurring_day)
        self.cmb_recurring_day.clear()
        self.cmb_recurring_day.addItem(tr("settings.no_preferred_day"), 0)
        for day in range(1, 29):
            self.cmb_recurring_day.addItem(str(day), day)
        self.cmb_recurring_day.addItem(tr("settings.month_end"), 31)
        idx = self.cmb_recurring_day.findData(current)
        if idx < 0:
            idx = self.cmb_recurring_day.findData(25)
        self.cmb_recurring_day.setCurrentIndex(max(0, idx))
        del blocker

    def _retranslate_ui(self) -> None:
        """Übersetzt den Dialog sofort in die aktuell gewählte Sprache."""
        c = ui_colors(self)
        self.setWindowTitle(
            tr("auto.views_language_select_dialog.22_language_sprache_langue_cec30925")
        )
        self.lbl_welcome.setText(
            trf(
                "auto.views_language_select_dialog.34_h3_style_margin_0_welcome_willkomme_eef30112",
                value_0=(c.text_dim),
            )
        )
        self.gb_region.setTitle(tr("setup.region_box"))
        self.lbl_currency.setText(tr("settings.currency"))
        self.lbl_number_format.setText(tr("settings.number_format"))
        self.lbl_recurring_day.setText(tr("settings.recurring_preferred_day"))
        self.lbl_region_hint.setText(tr("setup.region_hint"))
        self.cmb_number_format.setToolTip(tr("settings.number_format_tip"))
        self.cmb_recurring_day.setToolTip(tr("setup.preferred_day_tip"))
        self.btn_ok.setText(tr("auto.views_language_select_dialog.57_ok_6128635b"))

        # Combo-Texte neu setzen, Auswahl aber behalten.
        cur_currency = self.cmb_currency.currentData()
        cur_numfmt = self.cmb_number_format.currentData()
        blocker_c = QSignalBlocker(self.cmb_currency)
        for i in range(self.cmb_currency.count()):
            code = self.cmb_currency.itemData(i)
            self.cmb_currency.setItemText(i, self._currency_label(code))
        idx = self.cmb_currency.findData(cur_currency)
        if idx >= 0:
            self.cmb_currency.setCurrentIndex(idx)
        del blocker_c

        blocker_n = QSignalBlocker(self.cmb_number_format)
        for i in range(self.cmb_number_format.count()):
            code = self.cmb_number_format.itemData(i)
            self.cmb_number_format.setItemText(i, self._number_format_label(code))
        idx = self.cmb_number_format.findData(cur_numfmt)
        if idx >= 0:
            self.cmb_number_format.setCurrentIndex(idx)
        del blocker_n
        self._fill_recurring_day_combo(self.cmb_recurring_day.currentData())

    def _on_language_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None
    ):
        if current is None:
            return
        code = current.data(Qt.UserRole)
        set_language(str(code))
        self._retranslate_ui()
        defaults = self.LANGUAGE_DEFAULTS.get(code, {})
        if not self._currency_touched:
            idx = self.cmb_currency.findData(defaults.get("currency", "CHF"))
            if idx >= 0:
                blocker = QSignalBlocker(self.cmb_currency)
                self.cmb_currency.setCurrentIndex(idx)
                del blocker
        if not self._numfmt_touched:
            idx = self.cmb_number_format.findData(
                LANGUAGE_NUMBER_FORMAT_DEFAULTS.get(code, "swiss")
            )
            if idx >= 0:
                blocker = QSignalBlocker(self.cmb_number_format)
                self.cmb_number_format.setCurrentIndex(idx)
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
        self.selected_number_format = self.cmb_number_format.currentData() or "swiss"
        self.selected_recurring_day = int(self.cmb_recurring_day.currentData() or 0)
        self.accept()

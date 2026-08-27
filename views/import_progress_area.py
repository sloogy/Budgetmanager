"""Kompakter Fortschrittsbereich fuer den Bankimport.

Die Oberflaeche ist bewusst schmal: eine 4 px hohe Leiste mittig unten im
Fenster, rechts daneben ein kleiner Abbrechen-Knopf, darunter eine dezente
Zeile mit Taetigkeit und Prozentzahl. Kein Rahmen, kein Statuspanel, keine
zweite Leiste ueber die ganze Fensterbreite - solange nichts laeuft, ist der
ganze Bereich ausgeblendet und kostet keine einzige Bildzeile Hoehe.

Dieses Modul enthaelt **keinen** Worker. Es stellt nur die Schnittstelle
bereit, die ein Analyse-Worker spaeter bedient::

    worker.status_changed.connect(area.set_activity)
    worker.progress_changed.connect(area.set_percent)
    worker.item_progress.connect(area.set_item_progress)
    worker.finished.connect(lambda _result: area.stop())
    area.cancel_requested.connect(worker.request_cancel)

Zur Fuellfarbe: Sie stammt aus dem Designprofil und ist dieselbe Farbe, mit
der die aktive Navigationsschaltflaeche der Seitenleiste hinterlegt ist
(``QPushButton#sidebarNavButton:checked`` im ThemeManager benutzt
``auswahl_hintergrund``, hier ``UIColors.selection_bg``). Sie wird nicht
zweitverdrahtet, damit ein neues Profil beide Flaechen gemeinsam aendert.

Warum die Farben nicht ueber ``palette(...)`` in QSS kommen: Der ThemeManager
setzt ausschliesslich ein Stylesheet und nie eine ``QPalette``. ``palette(...)``
loeste deshalb gegen die *System*-Palette auf - auf einem dunklen Desktop mit
hellem Profil genau die falsche Farbe.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.i18n import tr, trf
from views.ui_colors import ui_colors

# Die Vorgabe nennt "ca. 4 px". Die Zahl steht hier einmal und wird von der
# Geometrie *und* vom Test gelesen, damit beide nicht auseinanderlaufen.
BAR_HEIGHT_PX = 4

# Deckel gegen eine Leiste, die auf einem breiten Monitor ueber das halbe
# Fenster laeuft; darunter waechst und schrumpft sie frei mit.
BAR_MAX_WIDTH_PX = 520
BAR_MIN_WIDTH_PX = 90

# Verkleinerungsfaktor gegenueber der Profilschrift. Relativ statt absolut,
# damit "klein" auch bei hochgestellter Schrift noch lesbar bleibt.
_SMALL_FONT_FACTOR = 0.85
_SMALL_FONT_MIN_POINTS = 7.0
_DEFAULT_POINT_SIZE = 10.0

_STYLE_TEMPLATE = """
QProgressBar#importProgressBar {
    border: none;
    border-radius: 2px;
    background-color: %(border)s;
}
QProgressBar#importProgressBar::chunk {
    border-radius: 2px;
    background-color: %(selection_bg)s;
}
QLabel#importProgressStatus {
    color: %(text_dim)s;
    background: transparent;
    font-size: %(small_font)s;
}
QToolButton#importProgressCancel {
    border: none;
    border-radius: 4px;
    padding: 2px 8px;
    background: transparent;
    color: %(text_dim)s;
    font-size: %(small_font)s;
}
QToolButton#importProgressCancel:hover {
    background-color: %(bg_sidebar)s;
    color: %(text)s;
}
QToolButton#importProgressCancel:disabled {
    color: %(neutral)s;
}
"""


def _theme_anchor(widget: QWidget) -> QWidget:
    """Liefert das Widget, ueber das ein ThemeManager erreichbar ist.

    ``ui_colors()`` fragt ``widget.window()``. Fuer alles innerhalb eines
    Dialogs ist das der Dialog selbst - und der haelt keinen ThemeManager.
    Ohne diesen Umweg bekaeme der Fortschrittsbereich in *jedem* Profil die
    hellen Standardfarben, also im dunklen Profil die falschen. Deshalb wird
    die Elternkette hochgelaufen, bis ein Fenster mit ThemeManager auftaucht.
    """
    node: QWidget | None = widget
    for _ in range(12):  # Deckel gegen Zyklen in kaputten Hierarchien
        if node is None:
            break
        if getattr(node.window(), "theme_manager", None) is not None:
            return node
        node = node.parentWidget()
    return widget


def _profile_point_size(widget: QWidget) -> float | None:
    """Schriftgroesse des aktiven Designprofils, sofern erreichbar."""
    manager = getattr(_theme_anchor(widget).window(), "theme_manager", None)
    if manager is None:
        return None
    profile = manager.get_current_profile()
    if profile is None:
        return None
    value = profile.get("schriftgroesse", None)
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    if isinstance(value, str) and value.strip().isdigit():
        return float(value.strip())
    return None


class ImportProgressArea(QWidget):
    """Balken, Abbrechen-Knopf und Statuszeile als ein ausblendbarer Block."""

    #: Wird ausgeloest, wenn der Anwender den laufenden Vorgang abbrechen will.
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("importProgressArea")

        self._activity = ""
        self._percent: int | None = None
        self._current: int | None = None
        self._total: int | None = None
        self._active = False

        # Waagrecht mitwachsen, senkrecht nur so hoch wie noetig - sonst
        # zoege der Bereich in einem Layout ohne Dehnpartner Hoehe an sich.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._build_ui()
        self.apply_theme()
        self.stop()

    # ── Aufbau ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        # Links und rechts derselbe Dehnfaktor: der Block bleibt mittig.
        row.addStretch(1)

        # Leiste und Statuszeile stehen in einer eigenen Spalte, damit der Text
        # buendig unter dem Balkenanfang beginnt statt unter der Fenstermitte.
        self._track = QWidget(self)
        self._track.setObjectName("importProgressTrack")
        self._track.setMaximumWidth(BAR_MAX_WIDTH_PX)
        self._track.setMinimumWidth(BAR_MIN_WIDTH_PX)
        self._track.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        column = QVBoxLayout(self._track)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        self.bar = QProgressBar(self._track)
        self.bar.setObjectName("importProgressBar")
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(BAR_HEIGHT_PX)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        column.addWidget(self.bar)

        self.lbl_status = QLabel("", self._track)
        self.lbl_status.setObjectName("importProgressStatus")
        self.lbl_status.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        # Ein langer Taetigkeitsname darf das Fenster nicht breiter machen.
        self.lbl_status.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        column.addWidget(self.lbl_status)

        row.addWidget(self._track, 3)

        self.btn_cancel = QToolButton(self)
        self.btn_cancel.setObjectName("importProgressCancel")
        self.btn_cancel.setText(tr("btn.cancel"))
        self.btn_cancel.setToolTip(tr("import_progress.cancel_tip"))
        self.btn_cancel.setAutoRaise(True)
        self.btn_cancel.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        row.addWidget(self.btn_cancel, 0, Qt.AlignmentFlag.AlignTop)

        row.addStretch(1)
        root.addLayout(row)

    # ── Darstellung ───────────────────────────────────────────────

    def base_point_size(self) -> float:
        """Schriftgroesse, gegen die "klein" gemessen wird.

        Zuerst das Designprofil: Der ThemeManager schreibt dessen
        ``schriftgroesse`` als ``* { font-size: Npt; }`` ins App-Stylesheet,
        und eine QSS-Regel schlaegt jedes ``setFont``. Wer hier nur die geerbte
        Widget-Schrift befragte, bekaeme in der laufenden Anwendung eine
        andere Zahl als die, die tatsaechlich gezeichnet wird.
        """
        vom_profil = _profile_point_size(self)
        if vom_profil is not None:
            return vom_profil
        eigene = self.font().pointSizeF()
        return eigene if eigene > 0 else _DEFAULT_POINT_SIZE

    def small_point_size(self) -> float:
        """Groesse der dezenten Statuszeile und des Abbrechen-Knopfs."""
        return max(_SMALL_FONT_MIN_POINTS, self.base_point_size() * _SMALL_FONT_FACTOR)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange and hasattr(self, "lbl_status"):
            self.apply_theme()

    def apply_theme(self) -> None:
        """Zieht Farben und die kleine Schrift aus dem aktiven Designprofil.

        Das Stylesheet haengt an den drei Einzelteilen und **nicht** an dieser
        Flaeche: ``setStyleSheet`` friert die Schrift des Widgets ein, auf dem
        es sitzt. Am Bereich selbst haette das ``self.font()`` eingefroren und
        damit die Bezugsgroesse, gegen die hier verkleinert wird. Die
        Selektoren sind auf Objektnamen geschnitten, jedes Teil nimmt also nur
        seinen eigenen Block auf.
        """
        farben = ui_colors(_theme_anchor(self))
        werte = {
            name: wert for name, wert in vars(farben).items() if isinstance(wert, str)
        }
        werte["small_font"] = f"{self.small_point_size():.1f}pt"
        qss = _STYLE_TEMPLATE % werte
        for teil in (self.bar, self.lbl_status, self.btn_cancel):
            teil.setStyleSheet(qss)

    def fill_color(self) -> str:
        """Farbe des gefuellten Balkenteils - dieselbe wie die aktive Navigation."""
        return ui_colors(_theme_anchor(self)).selection_bg

    def track_color(self) -> str:
        """Neutrale Farbe des ungefuellten Balkenteils."""
        return ui_colors(_theme_anchor(self)).border

    # ── Schnittstelle fuer den spaeteren Worker ────────────────────

    def is_active(self) -> bool:
        return self._active

    def start(
        self,
        activity: str = "",
        *,
        cancellable: bool = True,
        percent: int | None = 0,
    ) -> None:
        """Blendet den Bereich ein und setzt ihn auf den Anfangszustand."""
        self._activity = activity
        self._current = None
        self._total = None
        self._active = True
        self.apply_theme()
        self.btn_cancel.setEnabled(True)
        self.set_cancellable(cancellable)
        self.set_percent(percent)
        self.setVisible(True)

    def stop(self) -> None:
        """Blendet den kompletten Bereich aus und vergisst den Zustand."""
        self._active = False
        self._activity = ""
        self._percent = None
        self._current = None
        self._total = None
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.lbl_status.setText("")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.setVisible(False)

    def set_cancellable(self, cancellable: bool) -> None:
        """Der Abbrechen-Knopf erscheint nur bei abbrechbaren Vorgaengen."""
        self.btn_cancel.setVisible(bool(cancellable) and self._active)

    def set_activity(self, activity: str) -> None:
        """Slot fuer ``status_changed(str)``."""
        self._activity = activity or ""
        self._refresh_status()

    def set_percent(self, percent: int | None) -> None:
        """Slot fuer ``progress_changed(int)``.

        ``None`` bedeutet: dieser Schritt kann keine serioese Prozentzahl
        liefern. Dann laeuft der Balken unbestimmt und die Zeile nennt nur die
        Taetigkeit - erfundene Zahlen gibt es hier nicht.
        """
        if percent is None:
            self.set_indeterminate()
            return
        value = max(0, min(100, int(percent)))
        self._percent = value
        if self.bar.maximum() == 0:
            self.bar.setRange(0, 100)
        self.bar.setValue(value)
        self._refresh_status()

    def set_item_progress(self, current: int, total: int) -> None:
        """Slot fuer ``item_progress(int, int)`` - Prozent folgt dem Verhaeltnis."""
        total = max(0, int(total))
        current = max(0, min(int(current), total)) if total else max(0, int(current))
        self._current = current
        self._total = total
        if total > 0:
            self.set_percent(round(current * 100 / total))
        else:
            self._refresh_status()

    def set_indeterminate(self) -> None:
        """Unbestimmter Balken fuer Schritte ohne belastbare Restmenge."""
        self._percent = None
        self._current = None
        self._total = None
        self.bar.setRange(0, 0)
        self._refresh_status()

    # ── Innenleben ────────────────────────────────────────────────

    def _on_cancel_clicked(self) -> None:
        # Zweimal Abbrechen ist keine zweite Aussage; der Knopf bleibt sichtbar,
        # damit der Bereich nicht springt, nimmt aber keine Klicks mehr an.
        self.btn_cancel.setEnabled(False)
        self.cancel_requested.emit()

    def status_text(self) -> str:
        """Die aktuell angezeigte Statuszeile."""
        return self.lbl_status.text()

    def _refresh_status(self) -> None:
        self.lbl_status.setText(self._compose_status())

    def _compose_status(self) -> str:
        if not self._activity:
            return ""
        if self._percent is None:
            return self._activity
        if self._current is not None and self._total:
            return trf(
                "import_progress.status_items",
                activity=self._activity,
                current=self._current,
                total=self._total,
                percent=self._percent,
            )
        return trf(
            "import_progress.status_percent",
            activity=self._activity,
            percent=self._percent,
        )

"""Was der BudgetManager an FPM weitergibt - und was nicht.

Bis v2.4.1 spiegelte die Bruecke alles: jede Kategorie, jedes Sparziel. Das
war bequem und falsch. Kategorienamen sind keine neutralen Etiketten - da
steht "Anwalt Scheidung" oder "Therapie", und Sparziele tragen Betrag und
Frist gleich mit. Ein Schwesterprogramm, das Fuellerausgaben zuordnen will,
braucht drei Kategorien, nicht vierzig.

Deshalb hier an *einer* Stelle: zwei Listen, Haekchen, fertig. Bewusst nicht
verteilt auf Kategorie-Eigenschaften und Sparziel-Dialog - wer wissen will,
was sein Rechner an das andere Programm weitergibt, soll das an einem Ort
nachsehen koennen und nicht an dreien suchen muessen.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from model.category_model import CategoryModel
from model.savings_goals_model import SavingsGoalsModel
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS
from utils.accessibility import configure_dialog_tab_order
from utils.i18n import tr, trf
from utils.money import format_money
from utils.notifications import show_info, show_warning
from views.ui_colors import ui_colors

logger = logging.getLogger(__name__)


class BridgeShareDialog(QDialog):
    """Freigabe je Kategorie und Sparziel fuer die FPM-Bruecke."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.kategorien = CategoryModel(conn)
        self.ziele = SavingsGoalsModel(conn)
        self.setWindowTitle(tr("bridge.share_title"))
        self.setMinimumSize(640, 520)
        self._build_ui()
        self._laden()

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        hinweis = QLabel(tr("bridge.share_hint"))
        hinweis.setWordWrap(True)
        _c = ui_colors(self)
        hinweis.setStyleSheet(
            f"padding: 8px; background-color: {_c.info_bg}; "
            "border-radius: 5px; font-size: 11px;"
        )

        self.tabs = QTabWidget()
        self.baum_ausgaben = self._neuer_baum()
        self.baum_sparkategorien = self._neuer_baum()
        self.baum_ziele = self._neuer_baum(spalte_betrag=True)
        self.tabs.addTab(self.baum_ausgaben, tr("bridge.share_tab_expenses"))
        self.tabs.addTab(self.baum_sparkategorien, tr("bridge.share_tab_savings_cats"))
        self.tabs.addTab(self.baum_ziele, tr("bridge.share_tab_goals"))

        self.btn_alle = QPushButton(tr("bridge.share_select_all"))
        self.btn_keine = QPushButton(tr("bridge.share_select_none"))
        self.btn_senden = QPushButton(tr("bridge.share_send_now"))
        self.btn_schliessen = QPushButton(tr("btn.close"))

        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.btn_alle)
        knoepfe.addWidget(self.btn_keine)
        knoepfe.addStretch()
        knoepfe.addWidget(self.btn_senden)
        knoepfe.addWidget(self.btn_schliessen)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {_c.info_text}; font-size: 11px;")

        layout = QVBoxLayout()
        layout.addWidget(hinweis)
        layout.addWidget(self.tabs)
        layout.addWidget(self.status)
        layout.addLayout(knoepfe)
        self.setLayout(layout)

        self.btn_alle.clicked.connect(lambda: self._alle_setzen(True))
        self.btn_keine.clicked.connect(lambda: self._alle_setzen(False))
        self.btn_senden.clicked.connect(self._jetzt_senden)
        self.btn_schliessen.clicked.connect(self.accept)

        # Ohne Absicherung wie in den anderen Dialogen: Ein Fehler hier waere
        # ein Fehler im Aufbau oben, und den soll man sehen.
        configure_dialog_tab_order(self)

    def _neuer_baum(self, *, spalte_betrag: bool = False) -> QTreeWidget:
        baum = QTreeWidget()
        if spalte_betrag:
            baum.setHeaderLabels(
                [tr("bridge.share_column_name"), tr("savings.column.target")]
            )
        else:
            baum.setHeaderLabels([tr("bridge.share_column_name")])
        baum.setRootIsDecorated(False)
        baum.setAlternatingRowColors(True)
        baum.setSelectionMode(QAbstractItemView.NoSelection)
        baum.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        baum.itemChanged.connect(self._haekchen_geaendert)
        return baum

    # ------------------------------------------------------------------
    # Laden und Speichern
    # ------------------------------------------------------------------
    def _laden(self) -> None:
        self._laedt = True
        try:
            self._kategorien_laden(self.baum_ausgaben, TYP_EXPENSES)
            self._kategorien_laden(self.baum_sparkategorien, TYP_SAVINGS)
            self._ziele_laden()
        finally:
            self._laedt = False
        self._status_aktualisieren()

    def _kategorien_laden(self, baum: QTreeWidget, typ: str) -> None:
        baum.clear()
        for name, geteilt in self.kategorien.bridge_share_flags(typ).items():
            eintrag = QTreeWidgetItem(baum, [name])
            eintrag.setCheckState(0, Qt.Checked if geteilt else Qt.Unchecked)
            # Art und Schluessel haengen am Eintrag: Beim Umschalten muss klar
            # sein, welche Zeile welcher Tabelle gemeint ist.
            eintrag.setData(0, Qt.UserRole, ("category", typ, name))

    def _ziele_laden(self) -> None:
        self.baum_ziele.clear()
        for ziel in self.ziele.list_all():
            eintrag = QTreeWidgetItem(
                self.baum_ziele, [ziel.name, format_money(ziel.target_amount)]
            )
            eintrag.setCheckState(0, Qt.Checked if ziel.bridge_share else Qt.Unchecked)
            eintrag.setData(0, Qt.UserRole, ("goal", "", ziel.id))
        self.baum_ziele.resizeColumnToContents(0)

    def _haekchen_geaendert(self, eintrag: QTreeWidgetItem, spalte: int) -> None:
        if getattr(self, "_laedt", False) or spalte != 0:
            return
        kennung = eintrag.data(0, Qt.UserRole)
        if not kennung:
            return
        art, typ, schluessel = kennung
        geteilt = eintrag.checkState(0) == Qt.Checked
        try:
            if art == "category":
                self.kategorien.set_bridge_share(typ, str(schluessel), geteilt)
            else:
                self.ziele.set_bridge_share(int(schluessel), geteilt)
        except sqlite3.Error as fehler:
            # Zurueckdrehen statt schweigen: Ein Haekchen, das nicht
            # gespeichert wurde, aber gesetzt aussieht, ist die schlimmste
            # Variante - der Nutzer glaubt, er habe etwas gesperrt.
            logger.warning("Freigabe konnte nicht gespeichert werden", exc_info=True)
            self._laedt = True
            try:
                eintrag.setCheckState(0, Qt.Unchecked if geteilt else Qt.Checked)
            finally:
                self._laedt = False
            show_warning(self, tr("msg.error"), str(fehler))
            return
        self._status_aktualisieren()

    def _alle_setzen(self, geteilt: bool) -> None:
        """Wirkt nur auf den sichtbaren Reiter.

        Absicht: "Alle abwaehlen" soll nicht nebenbei die Sparziele mit
        abraeumen, waehrend der Nutzer auf die Kategorienliste schaut.
        """
        baum = self.tabs.currentWidget()
        if not isinstance(baum, QTreeWidget):
            return
        for i in range(baum.topLevelItemCount()):
            eintrag = baum.topLevelItem(i)
            eintrag.setCheckState(0, Qt.Checked if geteilt else Qt.Unchecked)

    # ------------------------------------------------------------------
    # Anzeige und Senden
    # ------------------------------------------------------------------
    def _status_aktualisieren(self) -> None:
        def gezaehlt(baum: QTreeWidget) -> tuple[int, int]:
            gesamt = baum.topLevelItemCount()
            an = sum(
                1
                for i in range(gesamt)
                if baum.topLevelItem(i).checkState(0) == Qt.Checked
            )
            return an, gesamt

        kat_an, kat_gesamt = gezaehlt(self.baum_ausgaben)
        spar_an, spar_gesamt = gezaehlt(self.baum_sparkategorien)
        ziel_an, ziel_gesamt = gezaehlt(self.baum_ziele)
        self.status.setText(
            trf(
                "bridge.share_status",
                categories=kat_an + spar_an,
                categories_total=kat_gesamt + spar_gesamt,
                goals=ziel_an,
                goals_total=ziel_gesamt,
            )
        )

    def _jetzt_senden(self) -> None:
        """Schreibt die Brueckendateien sofort neu.

        Ohne das wirkt eine zurueckgenommene Freigabe erst beim naechsten
        Abgleich - und bis dahin steht in der Datei noch, was gerade
        abgewaehlt wurde.
        """
        from model.lifeplanner_import_service import sync_default_outboxes

        try:
            ausgaben, ziele = sync_default_outboxes(self.conn)
        except OSError as fehler:
            logger.warning("Bruecke konnte nicht geschrieben werden", exc_info=True)
            show_warning(self, tr("msg.error"), str(fehler))
            return
        show_info(
            self,
            tr("bridge.share_title"),
            trf(
                "bridge.share_sent",
                goals=ziele.count,
                expenses=ausgaben.count,
                path=str(ziele.path.parent),
            ),
        )


def open_bridge_share_dialog(conn: sqlite3.Connection, parent: QWidget | None = None):
    dlg = BridgeShareDialog(conn, parent)
    return dlg.exec()

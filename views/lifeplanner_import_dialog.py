from __future__ import annotations

import logging
import sqlite3
from dataclasses import replace
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from model.category_model import CategoryModel
from model.lifeplanner_import_service import (
    ImportDraft,
    ImportRecord,
    LifePlannerImportError,
    apply_import,
    bridge_zustand,
    default_bridge_path,
    default_draft,
    load_import_records,
    records_by_id,
    reject_import,
    sync_default_outboxes,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from utils.accessibility import configure_dialog_tab_order
from utils.i18n import tr, trf
from utils.money import get_currency
from utils.notifications import show_info, show_warning
from views.category_search_picker import CategorySearchPicker

logger = logging.getLogger(__name__)


_STATUS_TEXT = {
    "pending": "Neu",
    "changed": "Geändert",
    "orphaned": "Buchung fehlt",
    "imported": "Übernommen",
    "rejected": "Abgelehnt",
}


def _kategorie_auf_entwuerfe_setzen(
    *,
    conn: sqlite3.Connection,
    drafts: dict[str, ImportDraft],
    records_by_id: dict[str, ImportRecord],
    external_ids: list[str],
    typ: str,
    kategorie: str,
) -> int:
    """Setzt Typ und Kategorie auf die offenen Vorschlaege und zaehlt sie.

    Uebernommene und abgelehnte Datensaetze bleiben unberuehrt: Ihr Entwurf
    ist Geschichte, kein Vorschlag mehr - er nachtraeglich zu aendern wuerde
    die Buchung, die daraus entstanden ist, nicht mitziehen und beides
    auseinanderlaufen lassen.

    ``drafts`` wird an Ort und Stelle geaendert; die Entwuerfe selbst sind
    unveraenderlich und werden ersetzt.
    """
    geaendert = 0
    for external_id in external_ids:
        record = records_by_id.get(external_id)
        if record is None or record.status in {"imported", "rejected"}:
            continue
        draft = drafts.get(external_id) or default_draft(conn, record)
        drafts[external_id] = replace(draft, typ=typ, category=kategorie)
        geaendert += 1
    return geaendert


def _kategoriezeilen(
    conn: sqlite3.Connection, typ: str
) -> list[tuple[str, str, object]]:
    """Gruppierte Kategoriezeilen fuer den Picker, mit echtem Rueckfall.

    Ohne Gruppen fehlen Favoriten und Fixkosten als Kopfzeilen - waehlen kann
    man dann weiterhin. Ein leeres Ergebnis waere schlimmer als eine
    ungruppierte Liste: Dann laesst sich gar keine Kategorie setzen, und der
    Vorschlag bleibt liegen.

    Der Rueckfall liest bewusst ``list_names`` und nicht
    ``list_for_tracking_dropdown``: Letztere ruft intern dieselbe gruppierte
    Abfrage auf. Als Rueckfall gegen deren Ausfall taugt sie damit nicht -
    sie faellt mit.
    """
    modell = CategoryModel(conn)
    try:
        zeilen = modell.list_for_tracking_dropdown_grouped(typ)
    except (AttributeError, sqlite3.Error, ValueError) as fehler:
        logger.debug("gruppierte Kategorien nicht verfuegbar: %s", fehler)
        zeilen = []
    if zeilen:
        return list(zeilen)
    return [("item", name, name) for name in modell.list_names(typ)]


class LifePlannerImportEditDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        record: ImportRecord,
        draft: ImportDraft,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.conn = conn
        self.record = record
        self._result_draft: ImportDraft | None = None
        self.setWindowTitle(tr("lifeplanner_import.edit_title"))
        self.resize(620, 470)

        layout = QVBoxLayout(self)
        source = QLabel(
            trf(
                "lifeplanner_import.source_summary",
                source=record.source,
                currency=record.currency,
                amount=f"{record.amount:.2f}",
            )
        )
        source.setWordWrap(True)
        layout.addWidget(source)

        form = QFormLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setDate(
            QDate(
                draft.booking_date.year,
                draft.booking_date.month,
                draft.booking_date.day,
            )
        )
        form.addRow(tr("header.date"), self.date_edit)

        self.typ_combo = QComboBox()
        self.typ_combo.addItem(tr("typ.Ausgaben"), TYP_EXPENSES)
        self.typ_combo.addItem(tr("typ.Einkommen"), TYP_INCOME)
        self.typ_combo.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        idx = self.typ_combo.findData(draft.typ)
        self.typ_combo.setCurrentIndex(max(0, idx))
        self.typ_combo.currentIndexChanged.connect(self._reload_categories)
        form.addRow(tr("header.type"), self.typ_combo)

        # Dieselbe Auswahl wie in der Schnelleingabe: Suchfeld ueber
        # gefiltertem, gruppiertem Dropdown. Vorher stand hier eine schlichte
        # Liste - wer aus zweihundert Kategorien die richtige suchte, scrollte.
        self.category_picker = CategorySearchPicker(
            such_platzhalter=tr("quickadd.category_search_placeholder"),
            such_hinweis=tr("quickadd.category_search_tip"),
            dropdown_hinweis=tr("quickadd.category_dropdown_tip"),
            leer_hinweis=tr("quickadd.no_category_matches"),
        )
        self._requested_category = (
            draft.category
            or record.category_path.replace("›", "/").split("/")[-1].strip()
        )
        form.addRow(tr("header.category"), self.category_picker)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setDecimals(2)
        self.amount_spin.setRange(0.01, 999_999_999.0)
        self.amount_spin.setValue(float(draft.amount))
        self.amount_spin.setSuffix(f" {get_currency().upper()}")
        form.addRow(
            tr("lifeplanner_import.amount_in_budget_currency"), self.amount_spin
        )

        self.description_edit = QLineEdit(draft.details)
        self.description_edit.setMaxLength(2000)
        form.addRow(tr("header.description"), self.description_edit)
        layout.addLayout(form)

        source_details = QPlainTextEdit()
        source_details.setReadOnly(True)
        source_details.setMaximumHeight(105)
        source_details.setPlainText(
            "\n".join(
                part
                for part in [
                    record.description,
                    record.counterparty,
                    record.notes,
                    f"ID: {record.external_id}",
                ]
                if part
            )
        )
        layout.addWidget(source_details)

        self.currency_check = QCheckBox(
            trf(
                "lifeplanner_import.currency_confirm",
                source=record.currency,
                target=get_currency().upper(),
            )
        )
        self.currency_check.setChecked(bool(draft.currency_confirmed))
        self.currency_check.setVisible(
            record.currency.upper() != get_currency().upper()
        )
        layout.addWidget(self.currency_check)

        hint = QLabel(tr("lifeplanner_import.edit_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._reload_categories()
        configure_dialog_tab_order(self)

    def _reload_categories(self, *_args) -> None:
        """Baut die Auswahl nach einem Typwechsel neu auf.

        Der bisher gewaehlte Name bleibt der Wunsch: Wer von Ausgaben auf
        Ersparnisse wechselt, will nicht wieder bei der ersten Kategorie
        anfangen - existiert der Name dort auch, steht er wieder da.
        """
        typ = str(self.typ_combo.currentData() or TYP_EXPENSES)
        vorher = self.category_picker.selected_category() or self._requested_category
        self.category_picker.set_rows(
            _kategoriezeilen(self.conn, typ), bevorzugt=vorher
        )
        if vorher:
            self.category_picker.set_category(vorher)

    def _selected_category(self) -> str:
        return self.category_picker.selected_category().strip()

    def _validate_and_accept(self) -> None:
        typ = str(self.typ_combo.currentData() or TYP_EXPENSES)
        category = self._selected_category()
        model = CategoryModel(self.conn)
        resolved = model.resolve_name(typ, category)
        if resolved is None:
            if not category:
                show_warning(
                    self,
                    tr("dlg.hinweis"),
                    tr("lifeplanner_import.category_required"),
                )
                return
            answer = QMessageBox.question(
                self,
                tr("lifeplanner_import.create_category_title"),
                trf("lifeplanner_import.create_category_question", category=category),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            try:
                model.create(typ, category)
                resolved = model.resolve_name(typ, category)
            except Exception as exc:
                QMessageBox.critical(self, tr("msg.error"), str(exc))
                return
        if self.currency_check.isVisible() and not self.currency_check.isChecked():
            show_warning(
                self,
                tr("dlg.hinweis"),
                tr("lifeplanner_import.currency_required"),
            )
            return
        details = self.description_edit.text().strip()
        if not details:
            details = self.record.description or "LifePlanner Import"
        qd = self.date_edit.date()
        self._result_draft = ImportDraft(
            external_id=self.record.external_id,
            booking_date=date(qd.year(), qd.month(), qd.day()),
            typ=typ,
            category=str(resolved),
            amount=float(self.amount_spin.value()),
            details=details,
            source_currency=self.record.currency,
            currency_confirmed=(
                self.record.currency.upper() == get_currency().upper()
                or self.currency_check.isChecked()
            ),
        )
        self.accept()

    def result_draft(self) -> ImportDraft | None:
        return self._result_draft


class LifePlannerImportDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = conn
        self.records: list[ImportRecord] = []
        self._records_by_id: dict[str, ImportRecord] = {}
        self._drafts: dict[str, ImportDraft] = {}
        self.imported_count = 0
        self.setWindowTitle(tr("lifeplanner_import.title"))
        self.resize(1120, 650)

        layout = QVBoxLayout(self)
        title = QLabel(tr("lifeplanner_import.intro"))
        title.setWordWrap(True)
        layout.addWidget(title)

        path_label = QLabel(
            trf("lifeplanner_import.path", path=str(default_bridge_path()))
        )
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        controls = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItem(tr("lifeplanner_import.filter_open"), "open")
        self.filter_combo.addItem(tr("lifeplanner_import.filter_all"), "all")
        self.filter_combo.currentIndexChanged.connect(self._populate_table)
        controls.addWidget(self.filter_combo)
        controls.addStretch(1)
        self.summary_label = QLabel()
        controls.addWidget(self.summary_label)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                tr("lifeplanner_import.status"),
                tr("header.date"),
                tr("header.description"),
                tr("lifeplanner_import.vendor"),
                tr("header.amount"),
                tr("lifeplanner_import.source_currency"),
                tr("header.category"),
                tr("lifeplanner_import.source"),
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._edit_selected)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        # Kategorie direkt in der Uebersicht setzen - dieselbe Auswahl wie in
        # der Schnelleingabe. Vorher ging das nur ueber "Bearbeiten", einen
        # Datensatz nach dem anderen; wer zwanzig Zahlungen derselben Art
        # importierte, oeffnete zwanzigmal denselben Dialog.
        zuweisung = QHBoxLayout()
        zuweisung.addWidget(QLabel(tr("header.category")))

        self.bulk_typ_combo = QComboBox()
        self.bulk_typ_combo.addItem(tr("typ.Ausgaben"), TYP_EXPENSES)
        self.bulk_typ_combo.addItem(tr("typ.Einkommen"), TYP_INCOME)
        self.bulk_typ_combo.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        self.bulk_typ_combo.currentIndexChanged.connect(self._reload_bulk_categories)
        zuweisung.addWidget(self.bulk_typ_combo)

        self.bulk_category_picker = CategorySearchPicker(
            such_platzhalter=tr("quickadd.category_search_placeholder"),
            such_hinweis=tr("quickadd.category_search_tip"),
            dropdown_hinweis=tr("quickadd.category_dropdown_tip"),
            leer_hinweis=tr("quickadd.no_category_matches"),
        )
        zuweisung.addWidget(self.bulk_category_picker, 1)

        self.assign_btn = QPushButton(tr("lifeplanner_import.assign_category"))
        self.assign_btn.setToolTip(tr("lifeplanner_import.assign_category_tip"))
        self.assign_btn.clicked.connect(self._assign_category_to_selection)
        zuweisung.addWidget(self.assign_btn)
        layout.addLayout(zuweisung)

        actions = QHBoxLayout()
        self.reload_btn = QPushButton(tr("lifeplanner_import.reload"))
        self.edit_btn = QPushButton(tr("btn.edit"))
        self.accept_btn = QPushButton(tr("lifeplanner_import.accept"))
        self.reject_btn = QPushButton(tr("lifeplanner_import.reject"))
        self.sync_btn = QPushButton(tr("lifeplanner_import.sync_outboxes"))
        close_btn = QPushButton(tr("btn.close"))
        self.reload_btn.clicked.connect(self.reload)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.accept_btn.clicked.connect(self._accept_selected)
        self.reject_btn.clicked.connect(self._reject_selected)
        self.sync_btn.clicked.connect(self._sync_outboxes)
        close_btn.clicked.connect(self.accept)
        self._bridge_status = QLabel()
        self._bridge_status.setWordWrap(True)
        self._bridge_status.setObjectName("bridgeStatus")
        for button in (
            self.reload_btn,
            self.edit_btn,
            self.accept_btn,
            self.reject_btn,
            self.sync_btn,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(close_btn)
        layout.addLayout(actions)
        # Zustand der Bruecke unter den Schaltflaechen: Wer hier steht, will
        # wissen, ob und wo der Austausch stattfindet.
        titel = QLabel(tr("lifeplanner_import.bridge_status_title"))
        titel_schrift = titel.font()
        # Nur fett, keine feste Punktzahl: Die Schriftgroesse folgt seit
        # 2.2.68 der Einstellung, eine gesetzte Zahl waere davon abgekoppelt.
        titel_schrift.setBold(True)
        titel.setFont(titel_schrift)
        titel.setObjectName("bridgeStatusTitle")
        layout.addWidget(titel)
        layout.addWidget(self._bridge_status)
        hinweis = QLabel(tr("lifeplanner_import.bridge_status_hint"))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("bridgeStatusHint")
        layout.addWidget(hinweis)
        self._refresh_bridge_status()
        self.reload()
        configure_dialog_tab_order(self)

    def reload(self, *_args) -> None:
        try:
            self.records = load_import_records(self.conn)
            self._records_by_id = records_by_id(self.records)
        except LifePlannerImportError as exc:
            QMessageBox.critical(self, tr("msg.error"), str(exc))
            self.records = []
            self._records_by_id = {}
        self._populate_table()
        self._refresh_bridge_status()

    def _visible_records(self) -> list[ImportRecord]:
        if self.filter_combo.currentData() == "all":
            return self.records
        return [
            r for r in self.records if r.status in {"pending", "changed", "orphaned"}
        ]

    def _populate_table(self, *_args) -> None:
        visible = self._visible_records()
        self.table.setRowCount(0)
        for record in visible:
            draft = self._drafts.get(record.external_id) or default_draft(
                self.conn, record
            )
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                _STATUS_TEXT.get(record.status, record.status),
                draft.booking_date.strftime("%d.%m.%Y"),
                record.description,
                record.counterparty,
                f"{draft.amount:.2f}",
                record.currency,
                draft.category or record.category_path or "—",
                record.source,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.UserRole, record.external_id)
                if record.status in {"imported", "rejected"}:
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        open_count = sum(
            r.status in {"pending", "changed", "orphaned"} for r in self.records
        )
        self.summary_label.setText(
            trf("lifeplanner_import.summary", open=open_count, total=len(self.records))
        )

    def _selected_ids(self) -> list[str]:
        ids: list[str] = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 0)
            external_id = str(item.data(Qt.UserRole) or "") if item else ""
            if external_id and external_id not in ids:
                ids.append(external_id)
        return ids

    def _reload_bulk_categories(self, *_args) -> None:
        """Fuellt die Auswahl unter der Tabelle passend zum gewaehlten Typ."""
        typ = str(self.bulk_typ_combo.currentData() or TYP_EXPENSES)
        vorher = self.bulk_category_picker.selected_category()
        self.bulk_category_picker.set_rows(
            _kategoriezeilen(self.conn, typ), bevorzugt=vorher
        )

    def _assign_category_to_selection(self, *_args) -> None:
        """Setzt Typ und Kategorie auf alle markierten offenen Vorschlaege.

        Bereits uebernommene oder abgelehnte Datensaetze bleiben unberuehrt -
        ihr Entwurf ist Geschichte, nicht Vorschlag.
        """
        typ = str(self.bulk_typ_combo.currentData() or TYP_EXPENSES)
        kategorie = self.bulk_category_picker.selected_category()
        if not kategorie:
            show_info(
                self,
                tr("dlg.hinweis"),
                tr("lifeplanner_import.category_required"),
            )
            return

        # Der Name muss im Modell existieren: Die Uebersicht legt bewusst
        # keine Kategorien an - das bleibt dem Bearbeiten-Dialog mit seiner
        # ausdruecklichen Rueckfrage vorbehalten.
        aufgeloest = CategoryModel(self.conn).resolve_name(typ, kategorie)
        if not aufgeloest:
            show_info(
                self,
                tr("dlg.hinweis"),
                trf(
                    "lifeplanner_import.assign_unknown_category",
                    category=kategorie,
                ),
            )
            return

        geaendert = _kategorie_auf_entwuerfe_setzen(
            conn=self.conn,
            drafts=self._drafts,
            records_by_id=self._records_by_id,
            external_ids=self._selected_ids(),
            typ=typ,
            kategorie=str(aufgeloest),
        )

        if not geaendert:
            show_info(
                self,
                tr("dlg.hinweis"),
                tr("lifeplanner_import.select_open_records"),
            )
            return

        self._populate_table()
        self.summary_label.setText(
            trf(
                "lifeplanner_import.assigned",
                count=geaendert,
                category=str(aufgeloest),
            )
        )

    def _edit_selected(self, *_args) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            show_info(self, tr("dlg.hinweis"), tr("lifeplanner_import.select_one"))
            return
        record = self._records_by_id.get(ids[0])
        if record is None or record.status in {"imported", "rejected"}:
            return
        draft = self._drafts.get(record.external_id) or default_draft(self.conn, record)
        dialog = LifePlannerImportEditDialog(self.conn, record, draft, self)
        if dialog.exec() == QDialog.Accepted and dialog.result_draft() is not None:
            self._drafts[record.external_id] = dialog.result_draft()
            self._populate_table()

    def _prepare_draft(self, record: ImportRecord) -> ImportDraft | None:
        draft = self._drafts.get(record.external_id) or default_draft(self.conn, record)
        needs_edit = not draft.category or (
            record.currency.upper() != get_currency().upper()
            and not draft.currency_confirmed
        )
        if not needs_edit:
            return draft
        dialog = LifePlannerImportEditDialog(self.conn, record, draft, self)
        if dialog.exec() != QDialog.Accepted or dialog.result_draft() is None:
            return None
        result = dialog.result_draft()
        self._drafts[record.external_id] = result
        return result

    def _accept_selected(self, *_args) -> None:
        ids = self._selected_ids()
        if not ids:
            show_info(self, tr("dlg.hinweis"), tr("lifeplanner_import.select_rows"))
            return
        imported = 0
        updated = 0
        errors: list[str] = []
        for external_id in ids:
            record = self._records_by_id.get(external_id)
            if record is None or record.status not in {
                "pending",
                "changed",
                "orphaned",
            }:
                continue
            draft = self._prepare_draft(record)
            if draft is None:
                continue
            try:
                result = apply_import(self.conn, record, draft)
                imported += 1
                updated += int(result.updated)
            except Exception as exc:
                logger.exception("LifePlanner import failed for %s", external_id)
                errors.append(f"{record.description}: {exc}")
        self.imported_count += imported
        self.reload()
        if imported:
            show_info(
                self,
                tr("lifeplanner_import.done_title"),
                trf("lifeplanner_import.done", count=imported, updated=updated),
            )
        if errors:
            show_warning(self, tr("dlg.hinweis"), "\n".join(errors[:10]))

    def _refresh_bridge_status(self) -> None:
        """Zeigt Ordner und Inhalt der drei Brückendateien.

        Ohne diese Anzeige ist nicht zu erkennen, ob der Austausch überhaupt
        stattfindet - und vor allem nicht, welcher Ordner gerade gilt.
        """
        try:
            ordner, befunde = bridge_zustand()
        except OSError as fehler:
            self._bridge_status.setText(str(fehler))
            return
        zeilen = [trf("lifeplanner_import.bridge_status_folder", pfad=ordner)]
        for befund in befunde:
            schluessel = (
                "lifeplanner_import.bridge_status_entries"
                if befund.vorhanden
                else "lifeplanner_import.bridge_status_missing"
            )
            zeilen.append(trf(schluessel, name=befund.name, anzahl=befund.eintraege))
        self._bridge_status.setText("\n".join(zeilen))

    def _sync_outboxes(self, *_args) -> None:
        """Schreibt FPM-Ausgaben und Sparziele kontrolliert in die Bridge-Outbox."""
        try:
            expenses, savings = sync_default_outboxes(self.conn)
        except Exception as exc:
            logger.exception("LifePlanner outbox sync failed")
            show_warning(self, tr("dlg.hinweis"), str(exc))
            return
        self._refresh_bridge_status()
        show_info(
            self,
            tr("lifeplanner_import.sync_done_title"),
            trf(
                "lifeplanner_import.sync_done_body",
                expenses=expenses.count,
                savings=savings.count,
                path=str(expenses.path.parent),
            ),
        )

    def _reject_selected(self, *_args) -> None:
        ids = self._selected_ids()
        if not ids:
            show_info(self, tr("dlg.hinweis"), tr("lifeplanner_import.select_rows"))
            return
        answer = QMessageBox.question(
            self,
            tr("lifeplanner_import.reject_title"),
            trf("lifeplanner_import.reject_question", count=len(ids)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        for external_id in ids:
            record = self._records_by_id.get(external_id)
            if record is not None and record.status in {
                "pending",
                "changed",
                "orphaned",
            }:
                reject_import(self.conn, record)
        self.reload()

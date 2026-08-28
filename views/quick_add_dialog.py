from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from model.category_model import CategoryModel
from model.savings_goals_model import (
    ACTION_CORRECTION,
    ACTION_DEPOSIT,
    ACTION_WITHDRAWAL,
    SavingsGoalBoundsError,
)
from model.tags_model import TagsModel
from model.tracking_correction import TrackingCorrectionLearner
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS, normalize_typ
from settings import Settings
from utils.i18n import db_typ_from_display, tr, trf
from utils.money import currency_header, format_money
from utils.notifications import show_warning
from views.savings_goal_messages import show_savings_goal_bounds_warning

logger = logging.getLogger(__name__)


class QuickAddDialog(QDialog):
    """Schnelleingabe-Dialog für neue Tracking-Einträge (Strg+N)"""

    def __init__(
        self,
        conn: sqlite3.Connection,
        parent=None,
        *,
        preset: dict | None = None,
        edit_row_id: int | None = None,
    ):
        # v2.2.0: merkt sich je Konto (Typ) die zuletzt gebuchte Kategorie.
        # v2.2.16 (K1): Edit-Modus – derselbe Dialog fuer Neu UND Bearbeiten.
        # Vorher bekam der Nutzer beim Bearbeiten den aermeren TrackerDialog
        # (ohne Tag-Erstellung/Aktionstexte); jedes Feature musste doppelt
        # gebaut werden.
        self._settings = Settings()
        super().__init__(parent)
        self.conn = conn
        self._edit_row_id = int(edit_row_id) if edit_row_id is not None else None
        self.cats = CategoryModel(conn)
        self.tracking = TrackingModel(conn)
        self.tags_model = TagsModel(conn)
        self._fixed_category_tag_ids: set[int] = set()
        self._details_auto_from_tags = False
        self._details_user_edited = False
        self._preset_savings_action: str | None = None

        self.setWindowTitle(tr("dlg.quick_add"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Info
        info = QLabel(tr("lbl.lbl_quick_add_title"))
        layout.addWidget(info)

        # Datum (heute als Standard)
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel(tr("lbl.lbl_date")))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(date.today())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        date_row.addWidget(self.date_edit, 1)
        layout.addLayout(date_row)

        # Typ
        typ_row = QHBoxLayout()
        typ_row.addWidget(QLabel(tr("lbl.type")))
        self.typ_combo = QComboBox()
        self.typ_combo.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.typ_combo.addItem(tr("kpi.income"), TYP_INCOME)
        self.typ_combo.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        self.typ_combo.currentIndexChanged.connect(lambda _: self._on_typ_changed())
        typ_row.addWidget(self.typ_combo, 1)
        layout.addLayout(typ_row)

        # Kategorie: Suche + echtes Dropdown-Menü
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel(tr("lbl.category")))

        cat_picker_layout = QVBoxLayout()
        self.cat_search = QLineEdit()
        self.cat_search.setPlaceholderText(tr("quickadd.category_search_placeholder"))
        self.cat_search.setToolTip(tr("quickadd.category_search_tip"))
        self.cat_search.textEdited.connect(self._on_category_search_edited)
        cat_picker_layout.addWidget(self.cat_search)

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(False)
        self.cat_combo.setInsertPolicy(QComboBox.NoInsert)
        self.cat_combo.setMaxVisibleItems(18)
        self.cat_combo.setToolTip(tr("quickadd.category_dropdown_tip"))
        try:
            self.cat_combo.setPlaceholderText(tr("quickadd.no_category_matches"))
        except Exception:
            pass
        self.cat_combo.activated.connect(lambda _: self._on_category_combo_activated())
        cat_picker_layout.addWidget(self.cat_combo)

        self._all_category_rows: list[tuple[str, str, object]] = []
        self._update_categories()
        cat_row.addLayout(cat_picker_layout, 1)
        layout.addLayout(cat_row)

        # Betrag
        amount_row = QHBoxLayout()
        amount_row.addWidget(QLabel(tr("lbl.lbl_amount")))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999999.99)
        self.amount_spin.setPrefix(f"{currency_header()} ")
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(10)
        amount_row.addWidget(self.amount_spin, 1)
        layout.addLayout(amount_row)

        # Details
        details_row = QHBoxLayout()
        details_row.addWidget(QLabel(tr("lbl.lbl_details")))
        self.details_edit = QLineEdit()
        self.details_edit.setPlaceholderText(
            tr("auto.views_quick_add_dialog.83_optional_beschreibung_5622cc90")
        )
        self.details_edit.textEdited.connect(self._on_details_user_edited)
        details_row.addWidget(self.details_edit, 1)
        layout.addLayout(details_row)

        # Tags: dieselbe Schnellbuchung ist jetzt auch im Tracking-Tab aktiv.
        # Darum müssen Tags hier direkt verfügbar sein, nicht nur im alten
        # TrackerDialog.
        tags_row = QHBoxLayout()
        tags_row.addWidget(QLabel(tr("header.tags")))
        self.lst_tags = QListWidget()
        self.lst_tags.setMaximumHeight(110)
        self.lst_tags.setAlternatingRowColors(True)
        self.lst_tags.setToolTip(tr("tracking.tags_input_tip"))
        self.lst_tags.itemClicked.connect(self._on_tag_item_clicked)
        self.lst_tags.itemChanged.connect(lambda *_: self._apply_tag_action_details())
        tags_row.addWidget(self.lst_tags, 1)
        self.btn_create_tag = QPushButton(tr("tags.create_inline"))
        self.btn_create_tag.setToolTip(tr("tags.create_inline_tip"))
        self.btn_create_tag.clicked.connect(self._create_tag_inline)
        tags_row.addWidget(self.btn_create_tag)
        layout.addLayout(tags_row)
        self._fill_tags(())

        # Buttons
        btn_layout = QHBoxLayout()

        self.btn_save_add = QPushButton(tr("btn.btn_save_and_new"))
        self.btn_save_add.clicked.connect(self._save_and_new)
        btn_layout.addWidget(self.btn_save_add)

        self.btn_save_close = QPushButton(tr("btn.speichern_schliessen_1"))
        self.btn_save_close.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.btn_save_close)

        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._update_amount_range()
        self._apply_category_fixed_tags_to_selection()

        if preset:
            self._apply_preset(preset)
        if self._edit_row_id is not None:
            # Bearbeiten: kein "Speichern & weiter", eigener Titel.
            self.setWindowTitle(tr("dlg.tracking_entry"))
            self.btn_save_add.hide()

        # Enter = Speichern & Schließen
        self.amount_spin.setFocus()

    def _apply_preset(self, p: dict) -> None:
        """Belegt die Felder vor (Edit-Modus oder Vorbelegung)."""
        action = str(p.get("savings_action") or "").strip().lower()
        if action in {ACTION_DEPOSIT, ACTION_WITHDRAWAL, ACTION_CORRECTION}:
            self._preset_savings_action = action
        try:
            if p.get("date"):
                s = str(p["date"]).strip()
                d = (
                    datetime.strptime(s, "%d.%m.%Y").date()
                    if "." in s
                    else date.fromisoformat(s)
                )
                self.date_edit.setDate(d)
        except Exception as e:
            logger.debug("preset date: %s", e)
        if p.get("typ"):
            typ_db = normalize_typ(db_typ_from_display(str(p["typ"]).strip()))
            idx = self.typ_combo.findData(typ_db)
            if idx >= 0:
                self.typ_combo.setCurrentIndex(idx)
            self._update_amount_range()
            self._update_categories()
        if p.get("category"):
            wanted = str(p["category"])
            self._rebuild_category_dropdown(preferred_category=wanted)
            # v2.1.7-Blocker-Schutz (aus dem TrackerDialog uebernommen): Eine
            # Buchung auf einer Kategorie, die nicht (mehr) im Picker gelistet
            # ist (z.B. Parent-Kategorie oder umbenannt), darf beim Bearbeiten
            # nicht still auf den ersten Eintrag umgehaengt werden. Fallback:
            # die Kategorie als eigenen Eintrag einfuegen und selektieren.
            if self.cat_combo.currentData() != wanted:
                self.cat_combo.insertItem(0, wanted, wanted)
                self.cat_combo.setCurrentIndex(0)
        if p.get("amount") is not None:
            amt = float(p["amount"])
            if amt < 0:
                # Bestehende negative Buchung (z.B. Sparen-Entnahme oder
                # Alt-Korrektur) darf beim Bearbeiten nicht auf 0 geklemmt werden.
                self.amount_spin.setRange(-999999.99, 999999.99)
            self.amount_spin.setValue(amt)
        if p.get("details") is not None:
            self.details_edit.blockSignals(True)
            try:
                self.details_edit.setText(str(p["details"]))
            finally:
                self.details_edit.blockSignals(False)
            self._details_user_edited = bool(str(p["details"]).strip())
        if "tag_ids" in p:
            try:
                self._fill_tags(tuple(int(x) for x in (p.get("tag_ids") or ())))
            except Exception as e:
                logger.debug("preset tags: %s", e)

    def _fill_tags(
        self,
        selected_ids: tuple[int, ...] = (),
        fixed_ids: tuple[int, ...] | None = None,
    ) -> None:
        """Baut die Tag-Auswahl für die Schnelleingabe auf.

        fixed_ids sind Tags, die an der Kategorie hängen. Sie werden immer
        angehakt und können in der Buchung nicht versehentlich entfernt werden.
        """
        self.lst_tags.blockSignals(True)
        try:
            self.lst_tags.clear()
            fixed = set(
                self._fixed_category_tag_ids
                if fixed_ids is None
                else {int(x) for x in fixed_ids}
            )
            selected = {int(x) for x in selected_ids} | fixed
            try:
                tags = self.tags_model.list_tags(active_only=True)
            except Exception as exc:
                logger.debug("QuickAdd Tags konnten nicht geladen werden: %s", exc)
                tags = []

            if not tags:
                item = QListWidgetItem(tr("tags.no_tags_click_create"))
                item.setData(Qt.UserRole, None)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.lst_tags.addItem(item)
            else:
                for tag in tags:
                    tag_id = int(tag.get("id"))
                    name = str(tag.get("name") or "")
                    if tag_id in fixed:
                        name = f"{name}  🔒"
                    item = QListWidgetItem(name)
                    item.setData(Qt.UserRole, tag_id)
                    flags = item.flags() | Qt.ItemIsUserCheckable
                    if tag_id in fixed:
                        flags = flags & ~Qt.ItemIsUserCheckable
                        item.setToolTip(tr("tags.fixed_category_tag_tip"))
                    item.setFlags(flags)
                    item.setCheckState(
                        Qt.Checked if tag_id in selected else Qt.Unchecked
                    )
                    self.lst_tags.addItem(item)
            self.lst_tags.setVisible(True)
        finally:
            self.lst_tags.blockSignals(False)

    def _on_details_user_edited(self, _text: str) -> None:
        self._details_user_edited = True
        self._details_auto_from_tags = False

    def _on_tag_item_clicked(self, item: QListWidgetItem) -> None:
        """Wenn noch kein Tag existiert: Linksklick öffnet Tag-Erstellung."""
        if item is None:
            return
        if item.data(Qt.UserRole) is None:
            self._create_tag_inline()

    def _create_tag_inline(self) -> None:
        """Kleines Erstellungsmenü direkt aus der Schnelleingabe."""
        name, ok = QInputDialog.getText(
            self,
            tr("tags.create_title"),
            tr("tags.create_name_label"),
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if self.tags_model.name_exists(name):
            show_warning(
                self,
                tr("auto.views_tags_manager_dialog.221_tag_existiert_20291c3b"),
                trf(
                    "auto.views_tags_manager_dialog.222_ein_tag_mit_dem_namen_value_0_exist_be543b1c",
                    value_0=name,
                ),
            )
            return
        action_text, ok_action = QInputDialog.getText(
            self,
            tr("tags.action_text_title"),
            tr("tags.action_text_label"),
            text="",
        )
        if not ok_action:
            action_text = ""
        tag_id = self.tags_model.create_tag(name, action_text=action_text.strip())
        selected = set(self._selected_tag_ids()) | {int(tag_id)}
        self._fill_tags(tuple(selected), tuple(self._fixed_category_tag_ids))
        self._apply_tag_action_details(force=True)

    def _apply_category_fixed_tags_to_selection(self) -> None:
        typ = self._selected_typ()
        category = self._selected_category()
        fixed_ids = set(self.tags_model.get_tag_ids_for_category_name(typ, category))
        self._fixed_category_tag_ids = fixed_ids
        selected = set(self._selected_tag_ids()) | fixed_ids
        self._fill_tags(tuple(selected), tuple(fixed_ids))
        self._apply_tag_action_details()

    def _apply_tag_action_details(self, force: bool = False) -> None:
        """Füllt Details aus Tag-Aktionstexten, ohne Nutzertext zu überschreiben."""
        if self._details_user_edited and not self._details_auto_from_tags and not force:
            return
        tag_ids = self._selected_tag_ids()
        try:
            text = self.tags_model.render_action_texts(
                tag_ids,
                category=self._selected_category(),
                booking_date=self.date_edit.date().toPython(),
            )
        except Exception as exc:
            logger.debug("Tag-Aktionstext konnte nicht gerendert werden: %s", exc)
            text = ""
        if not text:
            if self._details_auto_from_tags and not self._details_user_edited:
                self.details_edit.blockSignals(True)
                try:
                    self.details_edit.clear()
                finally:
                    self.details_edit.blockSignals(False)
                self._details_auto_from_tags = False
            return
        current = self.details_edit.text().strip()
        if current and not self._details_auto_from_tags and not force:
            return
        self.details_edit.blockSignals(True)
        try:
            self.details_edit.setText(text)
        finally:
            self.details_edit.blockSignals(False)
        self._details_auto_from_tags = True
        self._details_user_edited = False

    def _ai_learning_enabled(self) -> bool:
        """Der P2.1-Schalter, hier nur gelesen.

        Steht er aus, wird eine Korrektur genauso wenig gelernt wie ein
        Import - Ausschalten heisst ausschalten, nicht "ausser bei
        Korrekturen".
        """
        return bool(self._settings.get("bank_import_ai_learning_enabled", True))

    def _selected_tag_ids(self) -> tuple[int, ...]:
        """Liest die angehakten Tags aus der Schnelleingabe."""
        ids: list[int] = []
        for i in range(self.lst_tags.count()):
            item = self.lst_tags.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(int(item.data(Qt.UserRole)))
        return tuple(ids)

    def _on_typ_changed(self) -> None:
        """Typwechsel: Kategorien und Betragslogik gemeinsam aktualisieren."""
        self.cat_search.clear()
        self._update_categories()
        self._update_amount_range()

    def _update_amount_range(self) -> None:
        """Negative Beträge sind nur für Ersparnisse-Entnahmen vorgesehen.

        Die normale Ausgaben-Erfassung bleibt geschützt. Für Sparziele braucht
        die Schnellerfassung aber negative Ersparnisse-Buchungen, damit Geld aus
        einem freigegebenen Ziel herausgebucht werden kann.
        """
        typ = normalize_typ(
            self.typ_combo.currentData()
            or db_typ_from_display(self.typ_combo.currentText())
        )
        if typ == TYP_SAVINGS:
            self.amount_spin.setRange(-999999.99, 999999.99)
            self.amount_spin.setToolTip(tr("quickadd.savings_negative_tip"))
        else:
            if self.amount_spin.value() < 0:
                self.amount_spin.setValue(abs(self.amount_spin.value()))
            self.amount_spin.setRange(0, 999999.99)
            self.amount_spin.setToolTip("")

    def _category_pairs_structured(self, typ: str) -> list[tuple[str, str]]:
        """Dropdown-Reihenfolge: Favoriten zuerst, danach manuelle Nutzungshäufigkeit."""
        try:
            return self.cats.list_for_tracking_dropdown(typ)
        except Exception as e:
            logger.debug("category dropdown order: %s", e)
            try:
                return self.cats.list_names_tree(typ)
            except Exception:
                return [(n, n) for n in self.cats.list_names(typ)]

    def _update_categories(self):
        """Aktualisiert Kategorien nach Typ und baut Suche + Dropdown neu auf."""
        typ = self.typ_combo.currentData() or db_typ_from_display(
            self.typ_combo.currentText()
        )

        current_data = self._selected_category_from_dropdown_only()
        if not current_data:
            current_data = (
                self.cat_combo.currentData() or self.cat_combo.currentText().strip()
            )

        try:
            grouped = self.cats.list_for_tracking_dropdown_grouped(typ)
            if not grouped:
                raise ValueError("leer")
            self._all_category_rows = grouped
        except Exception as e:
            logger.debug("gruppierter Picker, Fallback flach: %s", e)
            self._all_category_rows = [
                ("item", label, real)
                for label, real in self._category_pairs_structured(typ)
            ]

        # v2.2.0: Ohne aktuelle Auswahl die zuletzt gebuchte Kategorie dieses
        # Kontos vorschlagen – spart bei täglichen Buchungen einen Klickweg.
        if not current_data:
            try:
                last_map = self._settings.get("tracking_last_category", {}) or {}
                current_data = str(last_map.get(normalize_typ(str(typ)), "") or "")
            except Exception as e:
                logger.debug("last category restore: %s", e)

        self._rebuild_category_dropdown(
            query=self.cat_search.text().strip() if hasattr(self, "cat_search") else "",
            preferred_category=str(current_data or ""),
            show_popup=False,
        )
        if hasattr(self, "lst_tags"):
            self._apply_category_fixed_tags_to_selection()

    def _selected_category_from_dropdown_only(self) -> str:
        """Liest nur die echte Dropdown-Auswahl, ohne Suchtext zu interpretieren."""
        data = self.cat_combo.currentData()
        return data.strip() if isinstance(data, str) and data.strip() else ""

    def _rebuild_category_dropdown(
        self,
        *,
        query: str = "",
        preferred_category: str = "",
        show_popup: bool = False,
    ) -> None:
        """Filtert das Dropdown anhand des Suchfelds und erhält die Auswahl."""
        from views.category_picker import (
            filter_grouped_categories,
            populate_grouped_combo,
        )

        rows = filter_grouped_categories(self._all_category_rows, query)
        populate_grouped_combo(self.cat_combo, rows)

        selected = False
        preferred = (preferred_category or "").strip()
        if preferred:
            for i in range(self.cat_combo.count()):
                if self.cat_combo.itemData(i) == preferred:
                    self.cat_combo.setCurrentIndex(i)
                    selected = True
                    break

        if not selected:
            for i in range(self.cat_combo.count()):
                data = self.cat_combo.itemData(i)
                if isinstance(data, str) and data.strip():
                    self.cat_combo.setCurrentIndex(i)
                    selected = True
                    break

        if not selected:
            self.cat_combo.setCurrentIndex(-1)

        self.cat_combo.setEnabled(selected)
        if show_popup and self.cat_combo.count() > 0:
            QTimer.singleShot(0, self.cat_combo.showPopup)

    def _on_category_search_edited(self, text: str) -> None:
        """Suchfeld tippen: Dropdown live filtern und öffnen."""
        self._rebuild_category_dropdown(query=text.strip(), show_popup=True)

    def _on_category_combo_activated(self) -> None:
        """Dropdown-Auswahl bestätigt: Suchfeld sauber auf gewählte Kategorie setzen."""
        from views.category_picker import _clean_category_label

        category = self._selected_category_from_dropdown_only()
        if not category:
            return

        label = self.cat_combo.currentText()
        self.cat_search.blockSignals(True)
        try:
            self.cat_search.setText(_clean_category_label(label) or category)
        finally:
            self.cat_search.blockSignals(False)

        # Nach Auswahl wieder die volle Liste zeigen, Auswahl aber beibehalten.
        self._rebuild_category_dropdown(
            query="", preferred_category=category, show_popup=False
        )
        self._apply_category_fixed_tags_to_selection()

    def _selected_typ(self) -> str:
        return normalize_typ(
            self.typ_combo.currentData()
            or db_typ_from_display(self.typ_combo.currentText())
        )

    def _selected_category(self) -> str:
        from views.category_picker import resolve_combo_category

        category = resolve_combo_category(self.cat_combo)
        resolved = self.cats.resolve_name(self._selected_typ(), category)
        return resolved or category

    def _validate(self) -> bool:
        """Prüft ob alle Pflichtfelder ausgefüllt sind"""
        typ = self._selected_typ()
        category = self._selected_category()
        if not category:
            show_warning(
                self, tr("dlg.hinweis"), tr("dlg.bitte_eine_kategorie_auswaehlen")
            )
            return False

        # v2.2.1 (Bericht-Punkt 5): Wenn der Suchtext auf MEHRERE Kategorien
        # passt und keine explizite Dropdown-Auswahl vorliegt, wird nicht mehr
        # stillschweigend der erste Treffer gebucht – der Nutzer muss wählen.
        query = self.cat_search.text().strip() if hasattr(self, "cat_search") else ""
        explicit = self._selected_category_from_dropdown_only()
        if query and not explicit:
            matches = [
                real
                for kind, label, real in getattr(self, "_all_category_rows", [])
                if kind == "item" and real and query.lower() in str(label).lower()
            ]
            if len(set(matches)) > 1:
                show_warning(
                    self,
                    tr("dlg.hinweis"),
                    trf(
                        "quickadd.ambiguous_category", query=query, n=len(set(matches))
                    ),
                )
                try:
                    self.cat_combo.showPopup()
                except Exception as e:
                    logger.debug("showPopup: %s", e)
                return False

        resolved = self.cats.resolve_name(typ, category)
        if not resolved:
            show_warning(
                self, tr("dlg.hinweis"), trf("dlg.unknown_category", name=category)
            )
            return False

        amount = self.amount_spin.value()

        if abs(amount) < 1e-9:
            show_warning(
                self, tr("dlg.hinweis"), tr("quickadd.amount_must_not_be_zero")
            )
            return False

        if typ == TYP_EXPENSES and amount < 0:
            show_warning(
                self, tr("dlg.nicht_erlaubt"), tr("dlg.bei_ausgaben_sind_negative")
            )
            return False

        if typ != TYP_SAVINGS and amount < 0:
            show_warning(
                self, tr("dlg.nicht_erlaubt"), tr("quickadd.negative_only_savings")
            )
            return False

        return True

    def _save_entry(self) -> bool:
        """Speichert den Eintrag mit eindeutiger Sparziel-Buchungsart."""
        if not self._validate():
            return False

        d = self.date_edit.date().toPython()
        typ = self._selected_typ()
        category = self._selected_category()
        amount = self.amount_spin.value()
        details = self.details_edit.text().strip()
        savings_action: str | None = None

        if typ == TYP_SAVINGS:
            if amount < 0:
                conflict = self.tracking.check_savings_goal_conflict(category, amount)
                if conflict:
                    savings_action = self._confirm_negative_savings_booking(
                        conflict, amount
                    )
                    if savings_action is None:
                        return False
                else:
                    savings_action = ACTION_WITHDRAWAL
            else:
                savings_action = (
                    ACTION_CORRECTION
                    if self._preset_savings_action == ACTION_CORRECTION
                    else ACTION_DEPOSIT
                )
            try:
                self.tracking.validate_savings_goal_booking(
                    category, amount, savings_action
                )
            except SavingsGoalBoundsError as exc:
                show_savings_goal_bounds_warning(self, exc)
                return False

        tag_ids = tuple(
            sorted(set(self._selected_tag_ids()) | set(self._fixed_category_tag_ids))
        )
        if not details:
            action_details = self.tags_model.render_action_texts(
                tag_ids, category=category, booking_date=d
            )
            if action_details:
                details = action_details
        if not details:
            month_names = [tr(f"month.{i}") for i in range(1, 13)]
            details = f"{month_names[d.month - 1]} - {category}"

        try:
            if self._edit_row_id is not None:
                # Der Stand *vor* der Aenderung ist nur jetzt zu haben. Ohne
                # ihn liesse sich nicht unterscheiden, ob der Anwender der KI
                # widersprochen oder nur den Betrag berichtigt hat.
                korrektur = TrackingCorrectionLearner(self.conn)
                vorher = korrektur.snapshot(int(self._edit_row_id))
                self.tracking.update(
                    self._edit_row_id,
                    d,
                    typ,
                    category,
                    amount,
                    details,
                    savings_action=savings_action,
                )
                self.tags_model.set_entry_tags(int(self._edit_row_id), list(tag_ids))
                # Erst nach den Tags: vorher stuende der alte Tagstand noch da,
                # und die KI lernte eine Kategorie mit den Tags von gestern.
                korrektur.relearn(
                    int(self._edit_row_id),
                    vorher,
                    learn_enabled=self._ai_learning_enabled(),
                )
            else:
                new_id = self.tracking.add(
                    d,
                    typ,
                    category,
                    amount,
                    details,
                    savings_action=savings_action,
                )
                if tag_ids:
                    self.tags_model.set_entry_tags(int(new_id), list(tag_ids))
        except SavingsGoalBoundsError as exc:
            show_savings_goal_bounds_warning(self, exc)
            return False

        if self._edit_row_id is None:
            try:
                mw = self.window() if callable(getattr(self, "window", None)) else None
                parent = self.parent()
                target = parent.window() if parent is not None else mw
                if target is not None and hasattr(target, "statusBar"):
                    target.statusBar().showMessage(
                        trf("tracking.booked_undo_hint", category=str(category)), 6000
                    )
            except Exception as exc:
                logger.debug("undo hint: %s", exc)
            try:
                last_map = dict(self._settings.get("tracking_last_category", {}) or {})
                last_map[normalize_typ(str(typ))] = str(category)
                self._settings.set("tracking_last_category", last_map)
            except Exception as exc:
                logger.debug("last category persist: %s", exc)
        return True

    def _confirm_negative_savings_booking(
        self, conflict: dict, amount: float
    ) -> str | None:
        """Ordnet eine negative Ersparnisbuchung als Bezug oder Korrektur ein.

        Bezug ist bewusst der Standard. Nur die explizite Auswahl
        ``Korrektur`` verhindert, dass der Betrag als Projektverwendung zählt.
        """
        goal_name = str(conflict.get("goal_name", ""))
        current = float(conflict.get("current_amount", 0.0))
        withdrawal = abs(float(amount))
        released = float(conflict.get("released_amount", 0.0))
        used = float(conflict.get("withdrawn_amount", 0.0))
        released_available = max(0.0, released - used)

        box = QMessageBox(self)
        box.setWindowTitle(tr("tracking.title.savings_withdraw"))
        box.setIcon(QMessageBox.Question)
        box.setText(
            trf(
                "tracking.msg.savings_flow_choice",
                goal_name=goal_name,
                current=format_money(current),
                amount=format_money(withdrawal),
                released=format_money(released_available),
            )
        )
        btn_withdrawal = box.addButton(
            tr("tracking.btn.withdrawal_default"), QMessageBox.AcceptRole
        )
        btn_correction = box.addButton(
            tr("tracking.btn.correction"), QMessageBox.ActionRole
        )
        btn_cancel = box.addButton(tr("btn.cancel"), QMessageBox.RejectRole)
        box.setDefaultButton(
            btn_correction
            if self._preset_savings_action == ACTION_CORRECTION
            else btn_withdrawal
        )
        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_cancel:
            return None
        if clicked == btn_correction:
            return ACTION_CORRECTION
        return ACTION_WITHDRAWAL

    def _save_and_new(self):
        """Speichern und Dialog für neuen Eintrag vorbereiten"""
        if self._save_entry():
            # Felder zurücksetzen für nächsten Eintrag
            self.amount_spin.setValue(0)
            self.details_edit.blockSignals(True)
            try:
                self.details_edit.clear()
            finally:
                self.details_edit.blockSignals(False)
            self._details_auto_from_tags = False
            self._details_user_edited = False
            self._apply_category_fixed_tags_to_selection()
            self.amount_spin.setFocus()
            self.amount_spin.selectAll()

    def _save_and_close(self):
        """Speichern und Dialog schließen"""
        if self._save_entry():
            self.accept()

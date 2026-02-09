from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QMessageBox,
    QInputDialog,
    QLabel,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QGridLayout,
    QMenu,
    QSpinBox,
    QFormLayout,
)

from model.category_model import CategoryModel, Category


class CategoriesTab(QWidget):
    """Kategorien-Verwaltung als Baum.

    Variante 2 (gewünscht):
    - EIN Tree
    - 3 Root-Nodes (Top Level): Einkommen / Ausgaben / Ersparnisse
    - darunter: Hauptkategorien und Unterkategorien (parent_id)
    """
    
    # Signal für Schnelleingabe (wird von MainWindow abgehört)
    quick_add_requested = Signal()

    COL_NAME = 0
    COL_FIX = 1
    COL_REC = 2
    COL_DAY = 3

    ROLE_ID = int(Qt.UserRole) + 1
    ROLE_TYP = int(Qt.UserRole) + 2
    ROLE_OLD_NAME = int(Qt.UserRole) + 3

    TYPES = ["Einkommen", "Ausgaben", "Ersparnisse"]

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.model = CategoryModel(conn)
        self._loading = False

        # Buttons
        self.btn_new = QPushButton("Neu (Hauptkategorie)")
        self.btn_new_sub = QPushButton("Neu (Unterkategorie)")
        self.btn_delete = QPushButton("Löschen")
        self.btn_quick_add = QPushButton("⚡ Schnelleingabe")
        self.btn_quick_add.setToolTip("Schnell einen neuen Tracking-Eintrag erfassen (Ctrl+N)")
        
        # Filter
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Alle", "Nur Fixkosten", "Nur Wiederkehrend", "Keine Flags"])

        # Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Kategorie", "Fixkosten", "Wiederkehrend", "Tag"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setSelectionMode(self.tree.SelectionMode.ExtendedSelection)
        self.tree.setEditTriggers(
            self.tree.EditTrigger.DoubleClicked
            | self.tree.EditTrigger.SelectedClicked
            | self.tree.EditTrigger.EditKeyPressed
        )
        # Rechtsklick-Kontextmenü
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)


        top = QHBoxLayout()
        top.addWidget(QLabel("Kategorien (Baum): Einkommen / Ausgaben / Ersparnisse"))
        top.addStretch(1)
        top.addWidget(QLabel("Filter:"))
        top.addWidget(self.filter_combo)
        top.addWidget(self.btn_quick_add)
        top.addWidget(self.btn_new)
        top.addWidget(self.btn_new_sub)
        top.addWidget(self.btn_delete)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addWidget(self.tree)
        self.setLayout(root)

        self.btn_new.clicked.connect(self.add_root_category)
        self.btn_new_sub.clicked.connect(self.add_subcategory)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_quick_add.clicked.connect(self.quick_add_requested.emit)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)

        self.refresh()

    # -----------------
    # Helpers
    # -----------------
    def _set_loading(self, state: bool) -> None:
        self._loading = state

    def _mk_root(self, typ: str) -> QTreeWidgetItem:
        it = QTreeWidgetItem([typ, "", "", ""])
        f = it.font(self.COL_NAME)
        f.setBold(True)
        it.setFont(self.COL_NAME, f)
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        it.setData(self.COL_NAME, self.ROLE_ID, None)
        it.setData(self.COL_NAME, self.ROLE_TYP, typ)
        it.setExpanded(True)
        return it

    def _mk_cat_item(self, c: Category) -> QTreeWidgetItem:
        it = QTreeWidgetItem([c.name, "", "", ""])

        # Name editierbar
        it.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

        # Fix/Recurring Checkboxes
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(self.COL_FIX, Qt.CheckState.Checked if c.is_fix else Qt.CheckState.Unchecked)
        it.setCheckState(self.COL_REC, Qt.CheckState.Checked if c.is_recurring else Qt.CheckState.Unchecked)

        # Day
        it.setText(self.COL_DAY, str(int(c.recurring_day)) if c.is_recurring else "")
        # Tag-Spalte ist editierbar nur wenn recurring
        if c.is_recurring:
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)

        it.setData(self.COL_NAME, self.ROLE_ID, int(c.id))
        it.setData(self.COL_NAME, self.ROLE_TYP, c.typ)
        it.setData(self.COL_NAME, self.ROLE_OLD_NAME, c.name)
        return it

    def _collect_subtree_ids(self, item: QTreeWidgetItem) -> list[int]:
        ids: list[int] = []
        cid = item.data(self.COL_NAME, self.ROLE_ID)
        if cid:
            ids.append(int(cid))
        for i in range(item.childCount()):
            ids.extend(self._collect_subtree_ids(item.child(i)))
        return ids

    def _is_root_node(self, item: QTreeWidgetItem | None) -> bool:
        if not item:
            return False
        return item.parent() is None and item.text(self.COL_NAME) in self.TYPES

    def _nearest_typ_root(self, item: QTreeWidgetItem | None) -> QTreeWidgetItem | None:
        cur = item
        while cur is not None:
            if self._is_root_node(cur):
                return cur
            cur = cur.parent()
        return None

    # -----------------
    # Public
    # -----------------
    def refresh(self) -> None:
        self._set_loading(True)
        try:
            self.tree.clear()

            grouped = self.model.list_tree()  # typ -> list[Category]

            # Roots
            roots: dict[str, QTreeWidgetItem] = {}
            for typ in self.TYPES:
                root_item = self._mk_root(typ)
                self.tree.addTopLevelItem(root_item)
                roots[typ] = root_item

            # Build tree per typ
            for typ in self.TYPES:
                cats = grouped.get(typ, [])
                nodes = self.model.build_tree(cats)

                def add_nodes(parent_item: QTreeWidgetItem, children: list[dict]):
                    for n in children:
                        c: Category = n["cat"]
                        it = self._mk_cat_item(c)
                        parent_item.addChild(it)
                        add_nodes(it, n["children"])

                add_nodes(roots[typ], nodes)

            self.tree.expandToDepth(1)
            self.tree.resizeColumnToContents(self.COL_NAME)
        finally:
            self._set_loading(False)

    # -----------------
    # Actions
    # -----------------
    def add_root_category(self) -> None:
        sel = self.tree.currentItem()
        root = self._nearest_typ_root(sel) if sel else None
        if root is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst 'Einkommen', 'Ausgaben' oder 'Ersparnisse' auswählen.")
            return

        typ = root.text(self.COL_NAME)
        name, ok = QInputDialog.getText(self, "Neue Kategorie", f"Name der neuen Kategorie ({typ}):")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            return

        try:
            self.model.create(typ, name, is_fix=False, is_recurring=False, recurring_day=1, parent_id=None)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Konnte Kategorie nicht anlegen:\n{e}")
            return

        self.refresh()

    def add_subcategory(self) -> None:
        sel = self.tree.currentItem()
        if sel is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Kategorie auswählen.")
            return

        if self._is_root_node(sel):
            parent_id = None
        else:
            parent_id = sel.data(self.COL_NAME, self.ROLE_ID)
            if not parent_id:
                QMessageBox.information(self, "Hinweis", "Bitte eine echte Kategorie auswählen (nicht nur den Typ-Header).")
                return

        root = self._nearest_typ_root(sel)
        if root is None:
            return
        typ = root.text(self.COL_NAME)

        name, ok = QInputDialog.getText(self, "Neue Unterkategorie", f"Name der Unterkategorie ({typ}):")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            return

        try:
            self.model.create(typ, name, is_fix=False, is_recurring=False, recurring_day=1, parent_id=(int(parent_id) if parent_id else None))
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Konnte Unterkategorie nicht anlegen:\n{e}")
            return

        self.refresh()

    def delete_selected(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst Kategorien auswählen.")
            return

        # Root-Nodes nie löschen
        deletable = [it for it in items if not self._is_root_node(it) and it.data(self.COL_NAME, self.ROLE_ID)]
        if not deletable:
            QMessageBox.information(self, "Hinweis", "Bitte nur Kategorien auswählen (nicht die Typ-Header).")
            return

        # IDs sammeln (inkl. Unterbaum)
        ids: list[int] = []
        for it in deletable:
            ids.extend(self._collect_subtree_ids(it))
        ids = sorted(set(ids))

        if len(ids) > 1:
            txt = f"{len(ids)} Kategorie(n) inklusive Unterkategorien löschen?"
        else:
            txt = "Kategorie löschen?"

        if QMessageBox.question(self, "Bestätigen", txt) != QMessageBox.StandardButton.Yes:
            return

        try:
            self.model.delete_by_ids(ids)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Konnte nicht löschen:\n{e}")
            return

        self.refresh()

    # -----------------
    # Editing
    # -----------------
    # -----------------
    # Kontextmenü (Rechtsklick)
    # -----------------
    def _selected_editable_category_items(self) -> list[QTreeWidgetItem]:
        items = self.tree.selectedItems()
        return [
            it for it in items
            if not self._is_root_node(it) and it.data(self.COL_NAME, self.ROLE_ID)
        ]

    def _show_tree_context_menu(self, pos) -> None:
        clicked = self.tree.itemAt(pos)
        if clicked is not None and not clicked.isSelected():
            # Rechtsklick soll das Item fokussieren, damit Aktionen konsistent sind
            self.tree.clearSelection()
            clicked.setSelected(True)
            self.tree.setCurrentItem(clicked)

        editable = self._selected_editable_category_items()
        menu = QMenu(self)

        act_new_root = menu.addAction("➕ Neu (Hauptkategorie)")
        act_new_sub = menu.addAction("➕ Neu (Unterkategorie)")
        menu.addSeparator()
        act_rename = menu.addAction("✏️ Umbenennen")
        act_delete = menu.addAction("🗑️ Löschen")
        act_mass = menu.addAction("🧰 Massenbearbeitung…")
        menu.addSeparator()
        act_fix_toggle = menu.addAction("Fixkosten aktivieren")
        act_rec_toggle = menu.addAction("Wiederkehrend aktivieren")
        act_set_day = menu.addAction("Fälligkeitstag (Tag im Monat) setzen…")

        act_new_sub.setEnabled(len(editable) == 1)
        act_rename.setEnabled(len(editable) == 1)
        act_delete.setEnabled(len(editable) >= 1)
        act_mass.setEnabled(len(editable) >= 2)

        has_editable = len(editable) >= 1
        act_fix_toggle.setEnabled(has_editable)
        act_rec_toggle.setEnabled(has_editable)
        act_set_day.setEnabled(has_editable)

        if has_editable:
            all_fix = all(it.checkState(self.COL_FIX) == Qt.CheckState.Checked for it in editable)
            all_rec = all(it.checkState(self.COL_REC) == Qt.CheckState.Checked for it in editable)
            act_fix_toggle.setText("Fixkosten deaktivieren" if all_fix else "Fixkosten aktivieren")
            act_rec_toggle.setText("Wiederkehrend deaktivieren" if all_rec else "Wiederkehrend aktivieren")

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == act_new_root:
            self.add_root_category()
            return

        if chosen == act_new_sub:
            self.add_subcategory()
            return

        if chosen == act_rename and len(editable) == 1:
            self.tree.editItem(editable[0], self.COL_NAME)
            return

        if chosen == act_delete:
            self.delete_selected()
            return

        if chosen == act_mass:
            self.mass_edit()
            return

        if not has_editable:
            return

        if chosen == act_fix_toggle:
            target = not all(it.checkState(self.COL_FIX) == Qt.CheckState.Checked for it in editable)
            self._set_loading(True)
            try:
                for it in editable:
                    cat_id = int(it.data(self.COL_NAME, self.ROLE_ID))
                    self.model.update_flags(cat_id, is_fix=target)
                    it.setCheckState(self.COL_FIX, Qt.CheckState.Checked if target else Qt.CheckState.Unchecked)
            finally:
                self._set_loading(False)
            return

        if chosen == act_rec_toggle:
            target = not all(it.checkState(self.COL_REC) == Qt.CheckState.Checked for it in editable)
            self._set_loading(True)
            try:
                for it in editable:
                    cat_id = int(it.data(self.COL_NAME, self.ROLE_ID))
                    self.model.update_flags(cat_id, is_recurring=target)
                    it.setCheckState(self.COL_REC, Qt.CheckState.Checked if target else Qt.CheckState.Unchecked)
                    if not target:
                        it.setText(self.COL_DAY, "")
                    else:
                        # wenn leer, default 1 anzeigen
                        if not (it.text(self.COL_DAY) or "").strip():
                            it.setText(self.COL_DAY, "1")
            finally:
                self._set_loading(False)
            return

        if chosen == act_set_day:
            cur = 1
            t0 = (editable[0].text(self.COL_DAY) or "").strip()
            if t0.isdigit():
                cur = max(1, min(31, int(t0)))

            day, ok = QInputDialog.getInt(
                self,
                "Fälligkeitstag",
                "Tag im Monat (1–31):",
                cur,
                1,
                31,
                1,
            )
            if not ok:
                return

            self._set_loading(True)
            try:
                for it in editable:
                    cat_id = int(it.data(self.COL_NAME, self.ROLE_ID))
                    self.model.update_flags(cat_id, is_recurring=True, recurring_day=int(day))
                    it.setCheckState(self.COL_REC, Qt.CheckState.Checked)
                    it.setText(self.COL_DAY, str(int(day)))
            finally:
                self._set_loading(False)
            return

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._loading:
            return

        if self._is_root_node(item):
            return

        cat_id = item.data(self.COL_NAME, self.ROLE_ID)
        typ = item.data(self.COL_NAME, self.ROLE_TYP)
        if not cat_id or not typ:
            return

        cat_id = int(cat_id)
        typ = str(typ)

        # Name geändert
        if column == self.COL_NAME:
            new_name = (item.text(self.COL_NAME) or "").strip()
            old_name = str(item.data(self.COL_NAME, self.ROLE_OLD_NAME) or "")
            if not new_name or new_name == old_name:
                return
            try:
                self.model.rename_and_cascade(cat_id, typ=typ, old_name=old_name, new_name=new_name)
                item.setData(self.COL_NAME, self.ROLE_OLD_NAME, new_name)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Umbenennen fehlgeschlagen:\n{e}")
                self._set_loading(True)
                try:
                    item.setText(self.COL_NAME, old_name)
                finally:
                    self._set_loading(False)
            return

        # Fixkosten / Wiederkehrend
        if column in (self.COL_FIX, self.COL_REC):
            is_fix = item.checkState(self.COL_FIX) == Qt.CheckState.Checked
            is_rec = item.checkState(self.COL_REC) == Qt.CheckState.Checked
            try:
                self.model.update_flags(cat_id, is_fix=is_fix, is_recurring=is_rec)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen:\n{e}")
                return

            # Tag-Text
            self._set_loading(True)
            try:
                if not is_rec:
                    item.setText(self.COL_DAY, "")
            finally:
                self._set_loading(False)
            return

        # Tag geändert
        if column == self.COL_DAY:
            raw = (item.text(self.COL_DAY) or "").strip()
            if not raw:
                return
            try:
                day = max(1, min(31, int(raw)))
            except Exception:
                day = 1
            try:
                # Day macht nur Sinn wenn recurring
                if item.checkState(self.COL_REC) != Qt.CheckState.Checked:
                    self._set_loading(True)
                    try:
                        item.setCheckState(self.COL_REC, Qt.CheckState.Checked)
                    finally:
                        self._set_loading(False)
                self.model.update_flags(cat_id, is_recurring=True, recurring_day=day)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen:\n{e}")
                return

            self._set_loading(True)
            try:
                item.setText(self.COL_DAY, str(day))
            finally:
                self._set_loading(False)

    # -----------------
    # Filter
    # -----------------
    def _apply_filter(self) -> None:
        """Filtert die Tree-Ansicht basierend auf Filterauswahl.

        Erwartetes Verhalten (UX):
        - 'Alle' / 'Keine Flags': zeigt nur passende Knoten, behält aber Eltern zur Orientierung.
        - 'Nur Fixkosten' / 'Nur Wiederkehrend': zeigt passende Knoten **inkl. ganzer Unterbäume**
          (also auch untergeordnete Kategorien, selbst wenn diese nicht geflaggt sind).
        """
        filter_mode = self.filter_combo.currentText()

        def matches(item: QTreeWidgetItem) -> bool:
            if self._is_root_node(item):
                return True

            is_fix = item.checkState(self.COL_FIX) == Qt.CheckState.Checked
            is_rec = item.checkState(self.COL_REC) == Qt.CheckState.Checked

            if filter_mode == "Alle":
                return True
            if filter_mode == "Nur Fixkosten":
                return is_fix
            if filter_mode == "Nur Wiederkehrend":
                return is_rec
            if filter_mode == "Keine Flags":
                return (not is_fix) and (not is_rec)
            return True

        # Nur bei Fix/Wiederkehrend sollen Unterbäume komplett sichtbar bleiben
        subtree_mode = filter_mode in ("Nur Fixkosten", "Nur Wiederkehrend")

        def show_subtree(item: QTreeWidgetItem) -> None:
            item.setHidden(False)
            for i in range(item.childCount()):
                show_subtree(item.child(i))

        def filter_tree(item: QTreeWidgetItem, force_show: bool = False) -> bool:
            """Rekursiv filtern. Gibt True zurück wenn Item (oder Nachkommen) sichtbar sind."""
            if self._is_root_node(item):
                item.setHidden(False)
                any_visible = False
                for i in range(item.childCount()):
                    if filter_tree(item.child(i), False):
                        any_visible = True
                return any_visible

            this_match = matches(item)

            # Wenn Subtree-Mode und dieser Knoten passt: alles darunter sichtbar lassen
            if subtree_mode and (this_match or force_show):
                show_subtree(item)
                return True

            any_visible = False
            for i in range(item.childCount()):
                if filter_tree(item.child(i), False):
                    any_visible = True

            show = this_match or any_visible
            item.setHidden(not show)
            return show

        for i in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(i)
            filter_tree(root)

    # -----------------
    # Massenbearbeitung
    # -----------------
    def mass_edit(self) -> None:
        """Öffnet Dialog zur Massenbearbeitung ausgewählter Kategorien"""
        editable = self._selected_editable_category_items()

        if not editable:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst Kategorien auswählen (nicht die Typ-Header).")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Massenbearbeitung ({len(editable)} Kategorien)")
        dlg.setMinimumWidth(420)

        layout = QVBoxLayout(dlg)
        info = QLabel(f"Änderungen auf <b>{len(editable)}</b> ausgewählte Kategorie(n) anwenden:")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self._mass_fix = QComboBox()
        self._mass_fix.addItems(["Nicht ändern", "Setzen: Ja", "Setzen: Nein"])
        form.addRow("Fixkosten:", self._mass_fix)

        self._mass_rec = QComboBox()
        self._mass_rec.addItems(["Nicht ändern", "Setzen: Ja", "Setzen: Nein"])
        form.addRow("Wiederkehrend:", self._mass_rec)

        day_row = QHBoxLayout()
        self._mass_day_mode = QComboBox()
        self._mass_day_mode.addItems(["Nicht ändern", "Tag setzen…"])
        self._mass_day = QSpinBox()
        self._mass_day.setRange(1, 31)
        self._mass_day.setValue(1)
        self._mass_day.setEnabled(False)
        self._mass_day_mode.currentIndexChanged.connect(lambda i: self._mass_day.setEnabled(i == 1))
        day_row.addWidget(self._mass_day_mode, 1)
        day_row.addWidget(self._mass_day, 0)
        form.addRow("Fälligkeitstag:", day_row)

        layout.addLayout(form)

        hint = QLabel("Hinweis: Wenn du einen Tag setzt, wird <b>Wiederkehrend</b> automatisch aktiviert.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        changed = 0
        fix_choice = self._mass_fix.currentIndex()
        rec_choice = self._mass_rec.currentIndex()
        set_day = self._mass_day_mode.currentIndex() == 1
        day_val = int(self._mass_day.value())

        self._set_loading(True)
        try:
            for item in editable:
                cat_id = int(item.data(self.COL_NAME, self.ROLE_ID))

                kwargs = {}
                if fix_choice == 1:
                    kwargs["is_fix"] = True
                elif fix_choice == 2:
                    kwargs["is_fix"] = False

                if rec_choice == 1:
                    kwargs["is_recurring"] = True
                elif rec_choice == 2:
                    kwargs["is_recurring"] = False

                if set_day:
                    kwargs["is_recurring"] = True
                    kwargs["recurring_day"] = day_val

                if not kwargs:
                    continue

                try:
                    self.model.update_flags(cat_id, **kwargs)
                    changed += 1

                    if "is_fix" in kwargs:
                        item.setCheckState(self.COL_FIX, Qt.CheckState.Checked if kwargs["is_fix"] else Qt.CheckState.Unchecked)

                    if "is_recurring" in kwargs:
                        item.setCheckState(self.COL_REC, Qt.CheckState.Checked if kwargs["is_recurring"] else Qt.CheckState.Unchecked)
                        if not kwargs["is_recurring"]:
                            item.setText(self.COL_DAY, "")

                    if "recurring_day" in kwargs:
                        item.setText(self.COL_DAY, str(kwargs["recurring_day"]))
                except Exception:
                    pass
        finally:
            self._set_loading(False)

        if changed > 0:
            QMessageBox.information(self, "OK", f"{changed} Kategorie(n) aktualisiert.")
            self.refresh()
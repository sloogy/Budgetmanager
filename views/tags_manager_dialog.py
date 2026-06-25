from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

"""
Tag-Verwaltungsdialog für Budgetmanager
Ermöglicht das Erstellen, Bearbeiten, Löschen und Zusammenführen von Tags
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QAbstractItemView,
    QColorDialog, QLabel, QLineEdit, QDialogButtonBox, QMenu
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
import sqlite3

from model.tags_model import TagsModel
from utils.icons import get_icon
from utils.money import format_money


class TagsManagerDialog(QDialog):
    """Dialog zur Verwaltung von Tags"""
    
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.tags_model = TagsModel(conn)
        
        self.setWindowTitle(tr("dlg.tags_manager"))
        self.setMinimumSize(700, 500)
        
        self._setup_ui()
        self._load_tags()
        
    def _setup_ui(self):
        """Erstellt das UI"""
        layout = QVBoxLayout()
        
        # Info-Label
        info = QLabel(
            tr('auto.views_tags_manager_dialog.45_tags_ermoeglichen_eine_zusaetzliche_115e8eae')
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Tabelle mit Tags
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([tr('lbl.day'), tr('lbl.color'), tr('auto.views_tags_manager_dialog.54_anzahl_verwendungen_838041ae'), tr('auto.views_tags_manager_dialog.54_aktionen_3bb76da2')])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(1, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(lambda _: self._edit_tag())
        layout.addWidget(self.table)
        
        # Button-Leiste
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton(tr('btn.new_theme'))
        self.btn_add.setIcon(get_icon("➕"))
        self.btn_add.setToolTip(tr('auto.views_tags_manager_dialog.75_neues_tag_erstellen_08b57a81'))
        self.btn_add.clicked.connect(self._add_tag)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton(tr('auto.views_tags_manager_dialog.79_bearbeiten_86a45c89'))
        self.btn_edit.setIcon(get_icon("✏️"))
        self.btn_edit.setToolTip(tr("dlg.ausgewaehltes_tag_bearbeiten"))
        self.btn_edit.clicked.connect(self._edit_tag)
        self.btn_edit.setEnabled(False)
        btn_layout.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton(tr("btn.loeschen_1"))
        self.btn_delete.setToolTip(tr("btn.ausgewaehltes_tag_loeschen"))
        self.btn_delete.clicked.connect(self._delete_tag)
        self.btn_delete.setEnabled(False)
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        
        self.btn_merge = QPushButton(tr("dlg.zusammenfuehren"))
        self.btn_merge.setToolTip(tr("dlg.mehrere_tags_zu_einem"))
        self.btn_merge.clicked.connect(self._merge_tags)
        btn_layout.addWidget(self.btn_merge)
        
        self.btn_stats = QPushButton(tr('auto.views_tags_manager_dialog.99_statistiken_6940bacd'))
        self.btn_stats.setIcon(get_icon("📊"))
        self.btn_stats.setToolTip(tr('auto.views_tags_manager_dialog.101_tag_statistiken_anzeigen_48ad4b4e'))
        self.btn_stats.clicked.connect(self._show_stats)
        btn_layout.addWidget(self.btn_stats)
        
        layout.addLayout(btn_layout)
        
        # Standardbuttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
        # Selektions-Handler
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def _show_context_menu(self, pos):
        """Rechtsklick-Kontextmenü auf der Tags-Tabelle."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self)
        act_edit = menu.addAction(tr('btn.edit'))
        act_edit.setIcon(get_icon("✏️"))
        act_color = menu.addAction(tr("dlg.farbe_aendern_1"))
        menu.addSeparator()
        act_delete = menu.addAction(tr("btn.loeschen_1"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self._edit_tag()
        elif chosen == act_color:
            item = self.table.item(row, 0)
            if item:
                tag_id = item.data(Qt.UserRole)
                self._change_color(tag_id)
        elif chosen == act_delete:
            self._delete_tag()

    def _load_tags(self):
        """Lädt alle Tags in die Tabelle"""
        self.table.setRowCount(0)
        
        tags = self.tags_model.get_all_tags()
        
        for tag in tags:
            tag_id = tag["id"]
            tag_name = tag["name"]
            color = tag.get("color", "")
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Tag-Name
            name_item = QTableWidgetItem(tag_name)
            name_item.setData(Qt.UserRole, tag_id)
            self.table.setItem(row, 0, name_item)
            
            # Farbe
            color_item = QTableWidgetItem()
            if color:
                qcolor = QColor(color)
                color_item.setBackground(QBrush(qcolor))
                # Dunkle Farben → weißer Text
                if qcolor.lightness() < 128:
                    color_item.setForeground(QBrush(Qt.white))
                color_item.setText(color)
            else:
                color_item.setText(tr('auto.views_tags_manager_dialog.168_keine_8f599208'))
            self.table.setItem(row, 1, color_item)
            
            # Anzahl Verwendungen
            usage_count = self._get_tag_usage_count(tag_id)
            usage_item = QTableWidgetItem(str(usage_count))
            usage_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, usage_item)
            
            # Aktionen-Container
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            
            # Farbe ändern Button
            btn_color = QPushButton("")
            btn_color.setIcon(get_icon("🎨"))
            btn_color.setFixedSize(30, 24)
            btn_color.setToolTip(tr("dlg.farbe_aendern"))
            btn_color.clicked.connect(lambda checked, tid=tag_id: self._change_color(tid))
            actions_layout.addWidget(btn_color)
            
            self.table.setCellWidget(row, 3, actions_widget)
            
    def _get_tag_usage_count(self, tag_id: int) -> int:
        """Ermittelt wie oft ein Tag verwendet wird"""
        return self.tags_model.usage_count(tag_id)
        
    def _on_selection_changed(self):
        """Aktiviert/deaktiviert Buttons basierend auf Selektion"""
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        
    def _add_tag(self):
        """Fügt ein neues Tag hinzu"""
        name, ok = QInputDialog.getText(
            self,
            tr('auto.views_tags_manager_dialog.207_neues_tag_ef65ca35'),
            tr('auto.views_tags_manager_dialog.208_tag_name_3d6e24ad'),
            text=""
        )
        
        if not ok or not name.strip():
            return
            
        name = name.strip()
        
        # Prüfen ob Name schon existiert
        if self._tag_name_exists(name):
            QMessageBox.warning(
                self,
                tr('auto.views_tags_manager_dialog.221_tag_existiert_20291c3b'),
                trf('auto.views_tags_manager_dialog.222_ein_tag_mit_dem_namen_value_0_exist_be543b1c', value_0=(name))
            )
            return
            
        # Optional: Farbe wählen
        reply = QMessageBox.question(
            self,
            tr("dlg.farbe_waehlen_1"),
            tr("dlg.moechten_sie_eine_farbe"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        color = None
        if reply == QMessageBox.Yes:
            qcolor = QColorDialog.getColor(QColor(ui_colors(self).accent), self, tr("msg.tag_farbe_waehlen"))
            if qcolor.isValid():
                color = qcolor.name()
                
        # Tag erstellen
        tag_id = self.tags_model.create_tag(name, color)
        
        if tag_id:
            self._load_tags()
            QMessageBox.information(
                self,
                tr('msg.success'),
                trf('auto.views_tags_manager_dialog.249_tag_value_0_wurde_erstellt_3d280c8d', value_0=(name))
            )
        else:
            QMessageBox.warning(
                self,
                tr('msg.error'),
                tr('auto.views_tags_manager_dialog.255_tag_konnte_nicht_erstellt_werden_955e67d7')
            )
            
    def _edit_tag(self):
        """Bearbeitet das ausgewählte Tag"""
        current_row = self.table.currentRow()
        if current_row < 0:
            return
            
        tag_id = self.table.item(current_row, 0).data(Qt.UserRole)
        old_name = self.table.item(current_row, 0).text()
        
        new_name, ok = QInputDialog.getText(
            self,
            tr('auto.views_tags_manager_dialog.269_tag_bearbeiten_5fd01a35'),
            tr('auto.views_tags_manager_dialog.270_neuer_name_ada4af32'),
            text=old_name
        )
        
        if not ok or not new_name.strip():
            return
            
        new_name = new_name.strip()
        
        # Prüfen ob neuer Name schon existiert (außer es ist der alte)
        if new_name != old_name and self._tag_name_exists(new_name):
            QMessageBox.warning(
                self,
                tr('auto.views_tags_manager_dialog.283_tag_existiert_1725866c'),
                trf('auto.views_tags_manager_dialog.284_ein_tag_mit_dem_namen_value_0_exist_126d57ed', value_0=(new_name))
            )
            return
            
        # Tag umbenennen
        success = self.tags_model.update_tag(tag_id, new_name)
        
        if success:
            self._load_tags()
            QMessageBox.information(
                self,
                tr('msg.success'),
                trf('auto.views_tags_manager_dialog.296_tag_wurde_umbenannt_in_value_0_a29907d3', value_0=(new_name))
            )
        else:
            QMessageBox.warning(
                self,
                tr('msg.error'),
                tr('auto.views_tags_manager_dialog.302_tag_konnte_nicht_umbenannt_werden_a89177d2')
            )
            
    def _delete_tag(self):
        """Löscht das ausgewählte Tag"""
        current_row = self.table.currentRow()
        if current_row < 0:
            return
            
        tag_id = self.table.item(current_row, 0).data(Qt.UserRole)
        tag_name = self.table.item(current_row, 0).text()
        usage_count = int(self.table.item(current_row, 2).text())
        
        # Warnung wenn Tag verwendet wird
        if usage_count > 0:
            reply = QMessageBox.warning(
                self,
                tr("btn.tag_loeschen"),
                trf("tags.msg.delete_used_confirm", tag=tag_name, count=usage_count),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return
        else:
            reply = QMessageBox.question(
                self,
                tr("btn.tag_loeschen"),
                trf("msg.tag_loeschen_frage", tag_name=tag_name),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return
                
        # Tag löschen
        success = self.tags_model.delete_tag(tag_id)
        
        if success:
            self._load_tags()
            QMessageBox.information(
                self,
                tr('msg.success'),
                trf('auto.views_tags_manager_dialog.349_tag_value_0_wurde_geloescht_b148924f', value_0=(tag_name))
            )
        else:
            QMessageBox.warning(
                self,
                tr('msg.error'),
                tr('auto.views_tags_manager_dialog.355_tag_konnte_nicht_geloescht_werden_8f83bd72')
            )
            
    def _change_color(self, tag_id: int):
        """Ändert die Farbe eines Tags"""
        # Aktuellen Tag finden
        tag_name = None
        current_color = None
        
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.UserRole) == tag_id:
                tag_name = self.table.item(row, 0).text()
                color_text = self.table.item(row, 1).text()
                if color_text and color_text != "(keine)":
                    current_color = QColor(color_text)
                break
                
        if not tag_name:
            return
            
        # Farbdialog
        initial_color = current_color if current_color else QColor(ui_colors(self).accent)
        qcolor = QColorDialog.getColor(initial_color, self, trf("tags.dialog.color_title", tag=tag_name))
        
        if not qcolor.isValid():
            return
            
        # Farbe aktualisieren
        success = self.tags_model.update_tag_color(tag_id, qcolor.name())
        
        if success:
            self._load_tags()
        else:
            QMessageBox.warning(
                self,
                tr('msg.error'),
                tr('auto.views_tags_manager_dialog.391_farbe_konnte_nicht_gespeichert_werd_124397e4')
            )
            
    def _merge_tags(self):
        """Führt mehrere Tags zu einem zusammen"""
        # Liste aller Tags holen
        tags = self.tags_model.get_all_tags()
        
        if len(tags) < 2:
            QMessageBox.information(
                self,
                tr("dlg.nicht_genug_tags"),
                tr('auto.views_tags_manager_dialog.403_es_muessen_mindestens_2_tags_vorhan_656a7014')
            )
            return
            
        # Dialog für Tag-Auswahl
        from PySide6.QtWidgets import QComboBox, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dlg.tags_merge"))
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        info = QLabel(
            tr('auto.views_tags_manager_dialog.417_waehlen_sie_die_tags_aus_die_zusamm_8f9053ec')
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        form = QFormLayout()
        
        # Ziel-Tag
        target_combo = QComboBox()
        for tag in tags:
            target_combo.addItem(tag["name"], tag["id"])
        form.addRow(tr("tags.target_tag_label"), target_combo)
        
        # Quell-Tags (mehrere)
        source_combo = QComboBox()
        source_combo.setEditable(False)
        for tag in tags:
            source_combo.addItem(tag["name"], tag["id"])
        form.addRow(tr("dlg.zusammenfuehren_von"), source_combo)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() != QDialog.Accepted:
            return
            
        target_id = target_combo.currentData()
        source_id = source_combo.currentData()
        
        if target_id == source_id:
            QMessageBox.warning(
                self,
                tr("dlg.ungueltige_auswahl"),
                tr('auto.views_tags_manager_dialog.459_ziel_und_quelle_duerfen_nicht_ident_8347b5bc')
            )
            return
            
        # Zusammenführen
        success = self.tags_model.merge_tags([source_id], target_id)
        
        if success:
            self._load_tags()
            QMessageBox.information(
                self,
                tr('msg.success'),
                tr('auto.views_tags_manager_dialog.471_tags_wurden_erfolgreich_zusammengef_c25182ec')
            )
        else:
            QMessageBox.warning(
                self,
                tr('msg.error'),
                tr('auto.views_tags_manager_dialog.477_tags_konnten_nicht_zusammengefuehrt_5b23f4a0')
            )
            
    def _show_stats(self):
        """Zeigt Tag-Statistiken"""
        stats = self.tags_model.get_tag_stats()
        
        if not stats:
            QMessageBox.information(
                self,
                tr("dlg.keine_statistiken"),
                tr('auto.views_tags_manager_dialog.488_es_sind_noch_keine_tags_mit_buchung_502ddf34')
            )
            return
            
        # Statistik-Dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("dlg.tags_stats"))
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([tr('lbl.day'), tr('auto.views_tags_manager_dialog.501_anzahl_buchungen_d50207ae'), tr('auto.views_tags_manager_dialog.501_gesamtbetrag_034bb324')])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        
        for tag_name, count, total in stats:
            row = table.rowCount()
            table.insertRow(row)
            
            table.setItem(row, 0, QTableWidgetItem(tag_name))
            
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 1, count_item)
            
            total_item = QTableWidgetItem(format_money(total))
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 2, total_item)
            
        layout.addWidget(table)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.accept)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        dialog.exec()
        
    def _tag_name_exists(self, name: str) -> bool:
        """Prüft ob ein Tag-Name bereits existiert"""
        return self.tags_model.name_exists(name)


from PySide6.QtWidgets import QWidget
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from views.ui_colors import ui_colors

from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QLabel, QAbstractItemView
)
from PySide6.QtCore import Qt


class ShortcutsDialog(QDialog):
    """Zeigt alle verfügbaren Tastenkürzel an (F1)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ Tastenkürzel-Übersicht")
        self.setMinimumSize(500, 600)
        
        layout = QVBoxLayout()
        
        # Titel
        title = QLabel("<h2>Tastenkürzel</h2>")
        layout.addWidget(title)
        
        # Tabelle mit Shortcuts
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Tastenkürzel", "Aktion"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # Shortcuts definieren
        shortcuts = [
            ("F1", "Diese Hilfe anzeigen"),
            ("F5", "Aktuelle Ansicht aktualisieren"),
            ("Strg+S", "Budget speichern"),
            ("Strg+,", "Einstellungen öffnen"),
            ("Strg+Q", "Programm beenden"),
            ("", ""),
            ("Strg+1", "Zum Budget-Tab wechseln"),
            ("Strg+2", "Zum Kategorien-Tab wechseln"),
            ("Strg+3", "Zum Tracking-Tab wechseln"),
            ("Strg+4", "Zur Übersicht wechseln"),
            ("", ""),
            ("Strg+Y", "Aktuelles Jahr laden"),
            ("Strg+F", "Globale Suche öffnen"),
            ("Strg+N", "Schnelleingabe (Quick-Add)"),
            ("Strg+Z", "Rückgängig (Undo)"),
            ("Strg+Shift+Z", "Wiederholen (Redo)"),
            ("", ""),
            ("Strg+E", "Export-Dialog öffnen"),
            ("Strg+I", "Import-Dialog öffnen"),
            ("", ""),
            ("Enter", "In Tabelle: Nächste Zelle"),
            ("Tab", "Zum nächsten Feld"),
            ("Escape", "Dialog schließen"),
        ]
        
        self.table.setRowCount(len(shortcuts))
        for i, (key, action) in enumerate(shortcuts):
            key_item = QTableWidgetItem(key)
            key_item.setTextAlignment(Qt.AlignCenter)
            if key:
                key_item.setFont(self._bold_font())
            self.table.setItem(i, 0, key_item)
            
            action_item = QTableWidgetItem(action)
            self.table.setItem(i, 1, action_item)
        
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.table)
        
        # Tipp
        tip = QLabel("💡 <i>Tipp: Die Tab-Reihenfolge kann per Drag & Drop angepasst werden.</i>")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def _bold_font(self):
        from PySide6.QtGui import QFont
        font = QFont()
        font.setBold(True)
        return font

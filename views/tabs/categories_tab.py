"""Sidebar-Seite „Kategorien".

v2.2.16 (K8, Variante B): Diese Seite und der Kategorie-Manager-Dialog teilen
sich EINEN Widget-Kern (``CategoryManagerWidget`` in
``views/category_manager_dialog.py``). Vorher waren es zwei getrennt
implementierte Verwaltungen (740 + 971 Zeilen) fuer den fehleranfaelligsten
Bereich der Datenschicht (Kategorie-Kaskade ueber acht Tabellen). Jetzt gibt es
nur noch eine Implementierung, zwei Rahmen.

Dieser Re-Export haelt bestehende Importe (``from views.tabs.categories_tab
import CategoriesTab``) stabil.
"""

from __future__ import annotations

from views.category_manager_dialog import CategoriesTab

__all__ = ["CategoriesTab"]

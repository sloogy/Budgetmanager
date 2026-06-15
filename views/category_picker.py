"""Gemeinsamer Helfer für die gruppierte, durchsuchbare Kategorieauswahl im Tracker.

Kombiniert vier Wünsche in einem Picker:
1. Gruppen (Favoriten / Fixkosten / Wiederkehrend / Übrige) als Kopfzeilen
2. Baum-Pfade (Ober-/Unterkategorien als "Eltern › Kind")
3. Häufigkeit (manuelle Buchungen) zuerst innerhalb der Gruppe
4. Suchfeld (editierbare ComboBox + Completer mit MatchContains)

Die Kopfzeilen sind nicht auswählbar und tauchen nicht in der Suche auf.
"""
from __future__ import annotations

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter

logger = logging.getLogger("budgetmanager")


def populate_grouped_combo(combo: QComboBox, grouped: list[tuple[str, str, object]]) -> None:
    """Befüllt eine editierbare ComboBox mit gruppierten Einträgen.

    grouped: Liste aus ("header", titel, None) und ("item", label, echter_name).
    """
    combo.blockSignals(True)
    try:
        combo.clear()
        model = combo.model()
        item_labels: list[str] = []
        label_to_index: dict[str, int] = {}
        first_item_index: int | None = None

        for kind, label, value in grouped:
            idx = combo.count()
            if kind == "header":
                combo.addItem(label, None)
                try:
                    it = model.item(idx)
                    if it is not None:
                        it.setFlags(Qt.NoItemFlags)  # deaktiviert + nicht auswählbar
                        f = it.font()
                        f.setBold(True)
                        it.setFont(f)
                except Exception as e:
                    logger.debug("Header-Formatierung im Picker: %s", e)
            else:
                combo.addItem(label, value)
                item_labels.append(label)
                label_to_index[label] = idx
                if first_item_index is None:
                    first_item_index = idx

        if first_item_index is not None:
            combo.setCurrentIndex(first_item_index)

        # Completer nur über echte Einträge (Kopfzeilen ausgeschlossen)
        comp = QCompleter(item_labels, combo)
        comp.setCompletionMode(QCompleter.PopupCompletion)
        comp.setFilterMode(Qt.MatchContains)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        combo.setCompleter(comp)

        # Auswahl per Completer -> korrekten Combo-Index setzen, damit currentData() stimmt
        def _on_completer_activated(text: str) -> None:
            i = label_to_index.get(text)
            if i is not None:
                combo.setCurrentIndex(i)

        try:
            comp.activated[str].connect(_on_completer_activated)
        except Exception as e:
            logger.debug("Completer-activated-Verdrahtung: %s", e)
    finally:
        combo.blockSignals(False)


def resolve_combo_category(combo: QComboBox) -> str:
    """Liefert den echten Kategorienamen aus der ComboBox (robust).

    Bevorzugt itemData (echter Name). Fällt sonst auf den getippten Text zurück
    und entfernt Picker-Marker (★, Baum-Pfad), damit nie ein Label gebucht wird.
    """
    data = combo.currentData()
    if isinstance(data, str) and data.strip():
        return data.strip()

    text = (combo.currentText() or "").strip()
    if not text:
        return ""

    # Falls der getippte Text exakt einem Item-Label entspricht -> dessen Daten
    for i in range(combo.count()):
        if combo.itemText(i) == text:
            d = combo.itemData(i)
            if isinstance(d, str) and d.strip():
                return d.strip()

    # Marker entfernen (★, Eltern-Pfad)
    cleaned = text.replace("★", "").strip()
    if "›" in cleaned:
        cleaned = cleaned.split("›")[-1].strip()
    return cleaned

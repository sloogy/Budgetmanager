"""Gemeinsamer Helfer für die gruppierte, durchsuchbare Kategorieauswahl im Tracker.

Kombiniert vier Wünsche in einem Picker:
1. Gruppen (Favoriten / Fixkosten / Wiederkehrend / Übrige) als Kopfzeilen
2. Baum-Pfade (Ober-/Unterkategorien als "Eltern › Kind")
3. Häufigkeit (manuelle Buchungen) zuerst innerhalb der Gruppe
4. Suchfeld + Dropdown oder editierbare ComboBox mit MatchContains-Suche

Die Kopfzeilen sind nicht auswählbar und tauchen nicht als Kategorie auf.
"""
from __future__ import annotations

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter

logger = logging.getLogger("budgetmanager")


def _clean_category_label(text: str) -> str:
    """Entfernt reine Anzeige-Marker aus Kategorie-Labels.

    Beispiele:
    - "★ Wohnen › Miete" -> "Miete"
    - "  Krankenkasse › Selbstbehalt" -> "Selbstbehalt"
    """
    cleaned = (text or "").replace("★", "").strip()
    while cleaned.startswith("  "):
        cleaned = cleaned[2:].strip()
    if "›" in cleaned:
        cleaned = cleaned.split("›")[-1].strip()
    return cleaned


def _same_text(a: object, b: object) -> bool:
    return str(a or "").strip().casefold() == str(b or "").strip().casefold()


def _search_text(value: object) -> str:
    """Normalisiert Text für robuste Contains-Suche."""
    text = str(value or "").replace("★", " ")
    text = text.replace("›", " ").replace(">", " ").replace("/", " ")
    return " ".join(text.casefold().split())


def category_matches_query(label: str, value: object, query: str) -> bool:
    """True, wenn Suchbegriff zu Label, echtem Namen oder Kindnamen passt."""
    q = _search_text(query)
    if not q:
        return True
    haystacks = (
        _search_text(label),
        _search_text(value),
        _search_text(_clean_category_label(label)),
    )
    return any(q in h for h in haystacks)


def filter_grouped_categories(
    grouped: list[tuple[str, str, object]], query: str
) -> list[tuple[str, str, object]]:
    """Filtert gruppierte Kategorien, ohne leere Gruppenköpfe stehen zu lassen.

    Bei leerer Suche wird die Liste unverändert zurückgegeben. Bei aktiver Suche
    bleiben die Gruppen erhalten, aber nur dann, wenn darunter mindestens ein
    Treffer liegt. So bekommt die Schnelleingabe beides: Suche und ein echtes
    Dropdown-Menü mit klarer Auswahl.
    """
    q = _search_text(query)
    if not q:
        return list(grouped)

    out: list[tuple[str, str, object]] = []
    pending_header: tuple[str, str, object] | None = None
    header_added = False

    for kind, label, value in grouped:
        if kind == "header":
            pending_header = (kind, label, value)
            header_added = False
            continue

        if kind != "item" or not value:
            continue

        if not category_matches_query(label, value, q):
            continue

        if pending_header is not None and not header_added:
            out.append(pending_header)
            header_added = True
        out.append((kind, label, value))

    return out


def populate_grouped_combo(combo: QComboBox, grouped: list[tuple[str, str, object]]) -> None:
    """Befüllt eine ComboBox mit gruppierten Einträgen.

    grouped: Liste aus ("header", titel, None) und ("item", label, echter_name).
    Funktioniert für editierbare und nicht-editierbare ComboBoxen. Bei editierbaren
    Boxen wird zusätzlich ein Completer über echte Einträge gesetzt.
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
        else:
            combo.setCurrentIndex(-1)

        # Completer nur über echte Einträge (Kopfzeilen ausgeschlossen) und nur
        # relevant, wenn die ComboBox editierbar ist. Nicht-editierbare Dropdowns
        # nutzen stattdessen ein separates Suchfeld.
        if combo.isEditable():
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
        else:
            combo.setCompleter(None)
    finally:
        combo.blockSignals(False)


def resolve_combo_category(combo: QComboBox) -> str:
    """Liefert den echten Kategorienamen aus einer ComboBox.

    Wichtig: Bei editierbaren ComboBoxen bleibt ``currentData()`` in Qt oft auf
    dem vorherigen Eintrag stehen, während der Benutzer bereits einen anderen
    Text ins Suchfeld tippt. Deshalb darf ``currentData()`` nur dann blind
    verwendet werden, wenn der sichtbare Text noch zum aktuellen Index passt.
    Ansonsten wird zuerst der getippte Text gegen alle echten Einträge geprüft.
    Kopfzeilen haben ``itemData(None)`` und werden nie als Kategorie geliefert.
    """
    text = (combo.currentText() or "").strip()
    current_index = combo.currentIndex()
    current_data = combo.currentData()
    current_label = combo.itemText(current_index) if current_index >= 0 else ""

    # Nicht-editierbare Dropdowns sind eindeutig: Nur itemData zählt.
    try:
        if not combo.isEditable():
            if isinstance(current_data, str) and current_data.strip():
                return current_data.strip()
            return ""
    except Exception:
        pass

    # 1) Exakte Label-Auswahl / Completer-Auswahl gewinnt.
    #    Dadurch wird ein getippter Text wie "Miete" nicht fälschlich als
    #    vorherige currentData-Kategorie gespeichert.
    if text:
        for i in range(combo.count()):
            d = combo.itemData(i)
            if not isinstance(d, str) or not d.strip():
                continue
            label = combo.itemText(i)
            if _same_text(label, text) or _same_text(_clean_category_label(label), text):
                return d.strip()

    # 2) currentData ist nur vertrauenswürdig, wenn der Text zum aktuellen
    #    Eintrag passt oder das Suchfeld leer ist.
    if isinstance(current_data, str) and current_data.strip():
        if not text or _same_text(text, current_label) or _same_text(text, _clean_category_label(current_label)):
            return current_data.strip()

    # 3) Direkter Treffer auf itemData (Benutzer tippt den echten Namen).
    if text:
        for i in range(combo.count()):
            d = combo.itemData(i)
            if isinstance(d, str) and d.strip() and _same_text(d, text):
                return d.strip()

    # 4) Letzter Fallback: Anzeige-Marker entfernen. Die aufrufende View muss
    #    danach gegen das Kategorie-Modell validieren.
    return _clean_category_label(text)

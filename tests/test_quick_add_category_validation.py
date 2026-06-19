"""Regression: Schnelleingabe/Tracker dürfen keine verwaisten Buchungen erzeugen.

Kategorien werden in der Tracking-Tabelle ausschließlich per Name referenziert.
Ein frei getippter Tippfehler oder eine Kategorie eines anderen Typs würde sonst
als „verwaiste" Buchung gespeichert und verschwände aus allen kategoriebasierten
Auswertungen und Budgets.

Geprüft wird:
1. Die Datenschicht ``CategoryModel.resolve_name`` (Qt-frei).
2. Per Quelltext-Marker, dass Schnelleingabe (QuickAddDialog) und TrackerDialog die
   Auflösung tatsächlich in ihrem Speicherpfad nutzen (kann ohne PySide6 nicht
   instanziiert werden, daher Marker-Assertion analog zu den übrigen UI-Regressionstests).

Läuft ohne Qt/PySide6.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.database import open_db  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.category_model import CategoryModel  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME  # noqa: E402


def _fresh():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = open_db(p)
    migrate_all(conn, db_path=p)
    return conn, p


def test_resolve_name_exact_case_insensitive_and_trim():
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        c.create(TYP_EXPENSES, "Lebensmittel")
        assert c.resolve_name(TYP_EXPENSES, "Lebensmittel") == "Lebensmittel"
        # case-insensitiv -> kanonische Schreibweise zurück
        assert c.resolve_name(TYP_EXPENSES, "lebensMITTEL") == "Lebensmittel"
        # umschließende Leerzeichen werden ignoriert
        assert c.resolve_name(TYP_EXPENSES, "  Lebensmittel  ") == "Lebensmittel"
    finally:
        conn.close()
        os.remove(p)


def test_resolve_name_rejects_typo_crosstype_and_empty():
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        c.create(TYP_EXPENSES, "Lebensmittel")
        c.create(TYP_INCOME, "Lohn")
        # Tippfehler -> None (würde sonst verwaiste Buchung erzeugen)
        assert c.resolve_name(TYP_EXPENSES, "Lebensmttel") is None
        # Kategorie des anderen Typs -> None
        assert c.resolve_name(TYP_EXPENSES, "Lohn") is None
        # leer/None -> None
        assert c.resolve_name(TYP_EXPENSES, "") is None
        assert c.resolve_name(TYP_EXPENSES, "   ") is None
        assert c.resolve_name(TYP_EXPENSES, None) is None  # type: ignore[arg-type]
    finally:
        conn.close()
        os.remove(p)


def test_resolve_name_handles_subcategories():
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        c.create(TYP_EXPENSES, "Wohnen")
        parent = [x for x in c.list(TYP_EXPENSES) if x.name == "Wohnen"][0]
        c.create(TYP_EXPENSES, "Miete", parent_id=parent.id, is_fix=True, is_recurring=True)
        # Unterkategorie wird per echtem Namen aufgelöst (Picker bucht den echten Namen,
        # nicht den Baum-Pfad "Wohnen › Miete").
        assert c.resolve_name(TYP_EXPENSES, "Miete") == "Miete"
        assert c.resolve_name(TYP_EXPENSES, "miete") == "Miete"
    finally:
        conn.close()
        os.remove(p)


def test_quick_add_and_tracker_dialog_validate_category_in_save_path():
    """Quelltext-Marker: beide Buchungsdialoge lösen die Kategorie vor dem Speichern auf."""
    qa = (ROOT / "views" / "quick_add_dialog.py").read_text(encoding="utf-8")
    td = (ROOT / "views" / "tracker_dialog.py").read_text(encoding="utf-8")
    for name, src in (("quick_add_dialog", qa), ("tracker_dialog", td)):
        assert "resolve_name(" in src, f"{name}: ruft resolve_name nicht auf"
        assert "dlg.unknown_category" in src, f"{name}: zeigt keine Unbekannt-Kategorie-Warnung"


if __name__ == "__main__":
    test_resolve_name_exact_case_insensitive_and_trim()
    test_resolve_name_rejects_typo_crosstype_and_empty()
    test_resolve_name_handles_subcategories()
    test_quick_add_and_tracker_dialog_validate_category_in_save_path()
    print("OK")

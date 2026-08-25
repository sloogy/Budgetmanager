"""Massenbearbeitung im aktiven Bankimport (V4).

Bis v3.0.6 sicherte diese Datei den Quelltext von ``bank_import_dialog.py``
zu - inklusive des ``CheckableTagCombo``, den es in V4 nicht mehr gibt. Von
den elf Zusicherungen beschrieben vier eine fachliche Invariante; die uebrigen
beschrieben Steuerelemente. Die vier Invarianten stehen jetzt als
Verhaltenstests gegen die ausgefuehrte V4-Klasse, der Laufzeittest des
geloeschten Kombinationsfeldes gilt jetzt dem ``TagSelectionDialog``.
"""

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from model.twint_import_policy import TYP_TWINT_AI
from model.typ_constants import TYP_EXPENSES
from tests.conftest import V4_KATEGORIE, V4_KATEGORIE_ZWEI


def _kategorie_tag(conn, typ: str, kategorie: str, tag_name: str) -> None:
    """Haengt einen fixen Kategorie-Tag an typ/kategorie."""
    from model.tags_model import TagsModel

    tags = TagsModel(conn)
    tags.create_tag(tag_name, action_text="")
    tag_id = int(
        conn.execute("SELECT id FROM tags WHERE name=?", (tag_name,)).fetchone()[0]
    )
    category_id = int(
        conn.execute(
            "SELECT id FROM categories WHERE typ=? AND name=?", (typ, kategorie)
        ).fetchone()[0]
    )
    tags.assign_to_category(category_id, tag_id)


def _tagdialog_beantworten(monkeypatch, entscheidungen: dict[str, Qt.CheckState]):
    """Faehrt den echten TagSelectionDialog und setzt die genannten Haken.

    Der Dialog wird nicht ersetzt, nur sein ``exec`` - so laufen Aufbau,
    Dreizustands-Vorbelegung und ``tag_states()`` wirklich durch.
    """
    import views.bank_import_dialog_v4 as v4

    gesehen: dict[str, object] = {}

    class _AutoDialog(v4.TagSelectionDialog):
        def exec(self):  # type: ignore[override]
            gesehen["dialog"] = self
            gesehen["vorher"] = dict(self.tag_states())
            for row in range(self.list.count()):
                item = self.list.item(row)
                name = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if name in entscheidungen:
                    item.setCheckState(entscheidungen[name])
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(v4, "TagSelectionDialog", _AutoDialog)
    return gesehen


def test_pflicht_tags_der_kategorie_lassen_sich_nicht_wegklicken(
    v4_conn, v4_dialog, v4_tx, v4_helfer, monkeypatch
):
    """Kategorie-Tags haengen an der Kategorie, nicht an der Zeile."""
    _kategorie_tag(v4_conn, TYP_EXPENSES, V4_KATEGORIE, "Haushalt")

    dialog = v4_dialog([v4_tx(0, description="Migros Zuerich", amount="-45.20")])
    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    assert dialog._all_tags(0) == ("Haushalt",)

    _tagdialog_beantworten(monkeypatch, {"Haushalt": Qt.CheckState.Unchecked})
    dialog._edit_tags_for_checked()

    assert dialog.states[0].manual_tags == set()
    assert dialog._all_tags(0) == ("Haushalt",)
    item = dialog._build_item(0)
    assert item is not None
    assert item.tags == ("Haushalt",)


def test_kategoriewechsel_verwirft_alte_pflicht_tags_und_haelt_manuelle(
    v4_conn, v4_dialog, v4_tx, v4_helfer, monkeypatch
):
    _kategorie_tag(v4_conn, TYP_EXPENSES, V4_KATEGORIE, "Haushalt")
    _kategorie_tag(v4_conn, TYP_EXPENSES, V4_KATEGORIE_ZWEI, "Freizeit")

    dialog = v4_dialog([v4_tx(0, description="Migros Zuerich", amount="-45.20")])
    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)

    _tagdialog_beantworten(monkeypatch, {"Freizeit": Qt.CheckState.Checked})
    dialog._edit_tags_for_checked()
    assert dialog.states[0].manual_tags == {"Freizeit"}
    assert dialog._all_tags(0) == ("Freizeit", "Haushalt")

    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE_ZWEI)

    # "Haushalt" hing nur an der alten Kategorie und faellt weg; das manuell
    # gesetzte "Freizeit" bleibt - obwohl es jetzt zugleich Pflicht-Tag ist.
    assert dialog.states[0].manual_tags == {"Freizeit"}
    assert dialog._all_tags(0) == ("Freizeit",)


def test_massenkategorie_bricht_die_twint_sicherheitsregel_nicht(
    v4_dialog, v4_tx, v4_helfer
):
    """Auch die Massenaktion darf einen TWINT-Eingang nie zur Buchung machen."""
    dialog = v4_dialog(
        [
            v4_tx(0, description="TWINT Gutschrift Anna", amount="25.00"),
            v4_tx(1, description="Migros Zuerich", amount="-45.20"),
        ]
    )
    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.haken_setzen(dialog, 1, True)

    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)

    assert dialog.states[0].category == V4_KATEGORIE
    assert dialog.states[0].typ == TYP_TWINT_AI
    assert dialog._build_item(0) is None

    assert dialog.states[1].category == V4_KATEGORIE
    assert dialog.states[1].typ == TYP_EXPENSES
    assert dialog._build_item(1) is not None


def test_twint_verrechnung_ist_opt_in(v4_dialog, v4_tx, v4_helfer):
    """Ohne bewusstes Einschalten bleibt der volle Ausgabebetrag stehen."""
    dialog = v4_dialog(
        [
            v4_tx(
                0,
                description="Restaurant Bern",
                amount="-80.00",
                booking_date=date(2026, 3, 17),
            ),
            v4_tx(
                1,
                description="TWINT Gutschrift Anna",
                amount="40.00",
                booking_date=date(2026, 3, 18),
            ),
        ]
    )
    v4_helfer.kategorie_setzen(dialog, TYP_EXPENSES, V4_KATEGORIE)
    assert 0 in dialog.matches

    assert dialog.act_net_twint.isChecked() is False
    assert dialog._effective_amount(0) == (80.0, "")
    item = dialog._build_item(0)
    assert item is not None
    assert item.amount == 80.0
    # Ein unverrechneter Treffer bleibt ein Pruefall, keine fertige Zeile.
    assert dialog._state_kind(0) == "review"

    dialog.act_net_twint.setChecked(True)
    assert dialog._effective_amount(0) == (40.0, "twint")
    verrechnet = dialog._build_item(0)
    assert verrechnet is not None
    assert verrechnet.amount == 40.0
    assert "TWINT-Erstattung 40.00" in verrechnet.details


def test_tagdialog_haelt_gemischte_zeilen_im_dritten_zustand(
    v4_conn, v4_dialog, v4_tx, v4_helfer, monkeypatch
):
    """Ersetzt den Laufzeittest des geloeschten CheckableTagCombo."""
    from model.tags_model import TagsModel

    tags = TagsModel(v4_conn)
    for name in ("Ferien", "Buero"):
        tags.create_tag(name, action_text="")

    dialog = v4_dialog(
        [
            v4_tx(0, description="Alpha", amount="-10.00"),
            v4_tx(1, description="Beta", amount="-20.00"),
        ]
    )
    dialog.states[0].manual_tags = {"Ferien"}
    v4_helfer.haken_setzen(dialog, 0, True)
    v4_helfer.haken_setzen(dialog, 1, True)

    gesehen = _tagdialog_beantworten(monkeypatch, {"Buero": Qt.CheckState.Checked})
    dialog._edit_tags_for_checked()

    # "Ferien" gilt nur fuer eine der beiden Zeilen: teilweise gesetzt.
    assert gesehen["vorher"]["Ferien"] == Qt.CheckState.PartiallyChecked
    assert gesehen["vorher"]["Buero"] == Qt.CheckState.Unchecked

    # Der dritte Zustand bleibt unangetastet, das gesetzte Tag greift ueberall.
    assert dialog.states[0].manual_tags == {"Ferien", "Buero"}
    assert dialog.states[1].manual_tags == {"Buero"}

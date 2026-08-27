"""Der 4-px-Fortschrittsbereich des Bankimports.

Geprueft wird die echte Oberflaeche offscreen, nicht ihr Quelltext: Geometrie,
Farbherkunft, Sichtbarkeit, Knopfposition, Statuszeile und Tab-Kette. Eine
Zusicherung der Bauart ``"4px" in DATEI.read_text()`` haette hier keinen Wert -
sie stimmt auch dann noch, wenn das Layout die Leiste gar nicht mehr anzeigt.

Der Worker, der diesen Bereich spaeter bedient, gehoert nicht in diesen Schritt.
Getestet ist deshalb die Schnittstelle, die er bedienen wird.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODUL = ROOT / "views" / "import_progress_area.py"
LOCALES = ROOT / "locales"

TAETIGKEIT = "KI-Kategorisierung"


class _Settings(dict):
    """Settings-Ersatz: der ThemeManager braucht davon nur `get` und `set`."""

    def set(self, key, value):
        self[key] = value


@pytest.fixture
def bereich(v4_app):
    """Fortschrittsbereich in einem sichtbaren Fenster, ohne Designprofil."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from views.import_progress_area import ImportProgressArea

    fenster = QWidget()
    fenster.resize(900, 200)
    layout = QVBoxLayout(fenster)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    flaeche = ImportProgressArea(fenster)
    layout.addWidget(flaeche)
    layout.addStretch(1)
    fenster.show()
    v4_app.processEvents()
    yield flaeche
    fenster.deleteLater()
    v4_app.processEvents()


@pytest.fixture
def gestartet(bereich, v4_app):
    """Laufender, abbrechbarer Vorgang bei 68 %."""
    bereich.start(TAETIGKEIT)
    bereich.set_percent(68)
    v4_app.processEvents()
    return bereich


@pytest.fixture
def dialog_mit_bereich(v4_app, v4_conn):
    """Sichtbarer V4-Dialog samt Fortschrittsbereich."""
    from views.bank_import_dialog_v4 import BankImportDialog

    dialog = BankImportDialog(v4_conn)
    dialog.show()
    v4_app.processEvents()
    yield dialog
    dialog.deleteLater()
    v4_app.processEvents()


@pytest.fixture
def profilwechsel(v4_app, tmp_path, monkeypatch):
    """Liefert eine Funktion, die den Bereich unter einem Designprofil zeigt."""
    from PySide6.QtWidgets import QDialog, QWidget

    import theme_manager as tmod
    from views.import_progress_area import ImportProgressArea
    from views.ui_colors import invalidate_color_cache

    monkeypatch.setattr("model.app_paths.data_dir", lambda: tmp_path)
    manager = tmod.ThemeManager(_Settings())

    # Bewusst mit Zwischendialog: In der echten Anwendung haengt der Bereich in
    # einem QDialog, und dessen window() ist der Dialog selbst - nicht das
    # Hauptfenster mit dem ThemeManager.
    host = QWidget()
    host.theme_manager = manager
    dialog = QDialog(host)
    flaeche = ImportProgressArea(dialog)

    def _mit_profil(name: str):
        assert manager.set_current_profile(name), f"Profil {name} fehlt"
        invalidate_color_cache()
        flaeche.apply_theme()
        return flaeche, manager

    yield _mit_profil
    invalidate_color_cache()
    host.deleteLater()
    v4_app.processEvents()


def _links_in(flaeche, kind) -> int:
    return kind.mapTo(flaeche, kind.rect().topLeft()).x()


def _oben_in(flaeche, kind) -> int:
    return kind.mapTo(flaeche, kind.rect().topLeft()).y()


# ── Balken ──────────────────────────────────────────────────────────────────


def test_balken_ist_vier_pixel_hoch(gestartet):
    """Die Vorgabe nennt ca. 4 px - und die Konstante ist dieselbe Quelle."""
    from views.import_progress_area import BAR_HEIGHT_PX

    assert BAR_HEIGHT_PX == 4
    assert gestartet.bar.height() == 4
    assert gestartet.bar.minimumHeight() == gestartet.bar.maximumHeight() == 4


def test_balken_ist_eine_kompakte_leiste_ohne_zahl_rahmen_und_panel(gestartet):
    """Keine Prozentzahl im Balken, kein Standardrahmen, kein Statuspanel."""
    from PySide6.QtWidgets import QFrame, QGroupBox

    assert gestartet.bar.isTextVisible() is False
    qss = gestartet.bar.styleSheet()
    assert "QProgressBar#importProgressBar" in qss
    assert "border: none" in qss
    # Ein Panel waere ein gerahmter Container - der Bereich hat keinen.
    assert gestartet.findChildren(QGroupBox) == []
    assert [
        rahmen
        for rahmen in gestartet.findChildren(QFrame)
        if rahmen.frameShape() != QFrame.Shape.NoFrame
    ] == []
    # Balken + Statuszeile bleiben zusammen unter einer Panelhoehe.
    assert gestartet.sizeHint().height() <= 40


def test_balken_und_abbrechen_stehen_mittig(gestartet):
    """Der Block ist waagrecht zentriert, nicht links angeschlagen."""
    links = _links_in(gestartet, gestartet.bar)
    rechts = gestartet.btn_cancel.x() + gestartet.btn_cancel.width()
    mitte_block = (links + rechts) / 2
    assert abs(mitte_block - gestartet.width() / 2) <= 2
    assert links > 0, "Die Leiste beginnt am linken Rand statt mittig"


def test_bereich_sitzt_unten_im_importfenster(dialog_mit_bereich, v4_app):
    """Zwischen Tabelle und Aktionsleiste, also im unteren Fensterdrittel."""
    dialog = dialog_mit_bereich
    dialog.progress_area.start(TAETIGKEIT)
    dialog.progress_area.set_percent(10)
    v4_app.processEvents()

    flaeche = dialog.progress_area
    assert flaeche.y() > dialog.height() * 2 / 3
    assert flaeche.y() > dialog.table.y() + dialog.table.height() - 1
    assert flaeche.y() + flaeche.height() <= dialog.btn_import.y() + 1


def test_fuellfarbe_folgt_der_aktiven_navigationsfarbe_in_beiden_profilen(
    profilwechsel,
):
    """Fuellfarbe = ``auswahl_hintergrund`` = Hinterlegung der aktiven Navigation."""
    gesehen = []
    for name in ("Standard Hell", "Standard Dunkel"):
        flaeche, manager = profilwechsel(name)
        profil = manager.get_current_profile()
        erwartet = profil.get("auswahl_hintergrund")
        assert flaeche.fill_color().lower() == erwartet.lower()
        assert erwartet.lower() in flaeche.bar.styleSheet().lower()
        gesehen.append(erwartet.lower())

    assert gesehen[0] != gesehen[1], "Hell und Dunkel liefern dieselbe Fuellfarbe"


def test_hintergrundtrack_ist_neutral_und_nicht_die_fuellfarbe(profilwechsel):
    """Der ungefuellte Teil bleibt eine ruhige Trennfarbe."""
    for name in ("Standard Hell", "Standard Dunkel"):
        flaeche, manager = profilwechsel(name)
        profil = manager.get_current_profile()
        assert flaeche.track_color().lower() == profil.get("tabelle_gitter").lower()
        assert flaeche.track_color().lower() != flaeche.fill_color().lower()


def test_keine_farbe_ist_im_modul_hart_kodiert():
    """Jede Farbe kommt aus dem Designprofil, keine steht im Quelltext."""
    from views.import_progress_area import _STYLE_TEMPLATE

    quelle = MODUL.read_text(encoding="utf-8")
    assert re.search(r"#[0-9A-Fa-f]{3,8}\b", quelle) is None
    # QSS-``palette(...)`` loest gegen die System-Palette auf, nicht gegen das
    # Designprofil - auf einem dunklen Desktop mit hellem Profil also falsch.
    assert "palette(" not in _STYLE_TEMPLATE
    assert "%(selection_bg)s" in _STYLE_TEMPLATE


def test_leiste_schrumpft_mit_einem_schmalen_fenster(gestartet, v4_app):
    """Responsiv: nichts laeuft aus dem Fenster, nichts verschwindet."""
    breit = gestartet.bar.width()
    gestartet.window().resize(360, 200)
    v4_app.processEvents()

    assert gestartet.bar.width() < breit
    assert gestartet.bar.width() > 0
    assert gestartet.bar.height() == 4
    rechter_rand = gestartet.btn_cancel.x() + gestartet.btn_cancel.width()
    assert rechter_rand <= gestartet.width()


# ── Abbrechen ───────────────────────────────────────────────────────────────


def test_abbrechen_steht_direkt_rechts_neben_dem_balken(gestartet):
    balken_rechts = _links_in(gestartet, gestartet.bar) + gestartet.bar.width()
    abstand = gestartet.btn_cancel.x() - balken_rechts
    assert 0 < abstand <= 16, f"Abstand zum Balken betraegt {abstand} px"
    # Auf Balkenhoehe, nicht darunter in einer eigenen Zeile.
    assert gestartet.btn_cancel.y() <= _oben_in(gestartet, gestartet.bar)


def test_abbrechen_ist_kleiner_als_die_hauptaktionen(dialog_mit_bereich, v4_app):
    dialog = dialog_mit_bereich
    dialog.progress_area.start(TAETIGKEIT)
    v4_app.processEvents()

    klein = dialog.progress_area.btn_cancel.sizeHint()
    for haupt in (dialog.btn_import, dialog.btn_close):
        assert klein.height() < haupt.sizeHint().height()
    assert (
        dialog.progress_area.btn_cancel.font().pointSizeF()
        < dialog.btn_import.font().pointSizeF()
    )


def test_abbrechen_erscheint_nur_bei_abbrechbarem_vorgang(bereich, v4_app):
    assert bereich.btn_cancel.isVisible() is False

    bereich.start(TAETIGKEIT, cancellable=False)
    v4_app.processEvents()
    assert bereich.isVisible() is True
    assert bereich.btn_cancel.isVisible() is False

    bereich.set_cancellable(True)
    v4_app.processEvents()
    assert bereich.btn_cancel.isVisible() is True

    bereich.stop()
    v4_app.processEvents()
    assert bereich.btn_cancel.isVisible() is False


def test_abbrechen_traegt_keine_warnoptik(gestartet):
    """Im Normalzustand dezent: kein Rot, kein gefuellter Hintergrund."""
    from views.ui_colors import ui_colors

    farben = ui_colors(gestartet)
    qss = gestartet.btn_cancel.styleSheet()
    knopf = qss.split("QToolButton#importProgressCancel")[1].split("}")[0]
    assert "background: transparent" in knopf
    assert farben.danger.lower() not in qss.lower()
    assert farben.negative.lower() not in qss.lower()


def test_abbrechen_meldet_den_wunsch_genau_einmal(gestartet, v4_app):
    rufe = []
    gestartet.cancel_requested.connect(lambda: rufe.append(1))

    gestartet.btn_cancel.click()
    v4_app.processEvents()
    assert rufe == [1]
    assert gestartet.btn_cancel.isEnabled() is False

    gestartet.btn_cancel.click()
    v4_app.processEvents()
    assert rufe == [1], "Zweimal Abbrechen ist keine zweite Aussage"


# ── Statuszeile ─────────────────────────────────────────────────────────────


def test_statuszeile_nennt_die_taetigkeit_und_endet_mit_prozent(gestartet):
    text = gestartet.status_text()
    assert text.startswith(TAETIGKEIT)
    assert text.endswith("68 %")
    assert text == "KI-Kategorisierung · 68 %"


def test_statuszeile_kann_zusaetzlich_current_und_total_zeigen(bereich):
    bereich.start("Duplikate prüfen")
    bereich.set_item_progress(742, 1086)

    assert bereich.status_text() == "Duplikate prüfen · 742 / 1086 · 68 %"
    assert bereich.bar.value() == 68


def test_statuszeile_ist_klein_und_dezent(gestartet):
    from views.ui_colors import ui_colors

    label = gestartet.lbl_status
    assert gestartet.small_point_size() < gestartet.base_point_size()
    assert label.font().pointSizeF() < gestartet.base_point_size()
    zeile = label.styleSheet().split("QLabel#importProgressStatus")[1].split("}")[0]
    assert ui_colors(gestartet).text_dim.lower() in zeile.lower()
    assert f"font-size: {gestartet.small_point_size():.1f}pt" in zeile


def test_kleine_schrift_folgt_der_profilschrift(profilwechsel, v4_app):
    """Die kleine Schrift bleibt relativ zur eingestellten Profilschrift.

    Der ThemeManager schreibt die Profilschrift als ``* { font-size: Npt; }``
    ins App-Stylesheet, und eine QSS-Regel schlaegt jedes ``setFont``. Waere
    die kleine Schrift einmal im Konstruktor eingefroren, wuerde sie beim
    Hochstellen der Profilschrift nicht mitwachsen - der Abbrechen-Knopf saehe
    dann neben gewachsenen Hauptaktionen falsch aus.
    """
    from views.ui_colors import invalidate_color_cache

    flaeche, manager = profilwechsel("Standard Hell")
    profil = manager.get_current_profile()
    gemessen = []
    for punkte in (10, 16):
        daten = profil.to_dict()
        daten["schriftgroesse"] = punkte
        assert manager.update_profile("Standard Hell", daten)
        manager._current_profile = None
        assert manager.set_current_profile("Standard Hell")
        invalidate_color_cache()
        flaeche.apply_theme()
        v4_app.processEvents()

        assert flaeche.base_point_size() == pytest.approx(punkte)
        assert flaeche.small_point_size() < punkte
        gemessen.append(flaeche.small_point_size())

    assert gemessen[1] > gemessen[0], "Die kleine Schrift waechst nicht mit"


def test_statuszeile_steht_unter_dem_balken_und_nicht_ueber_die_ganze_breite(gestartet):
    label = gestartet.lbl_status
    assert _links_in(gestartet, label) == _links_in(gestartet, gestartet.bar)
    assert _oben_in(gestartet, label) > _oben_in(gestartet, gestartet.bar)
    assert label.width() <= gestartet.bar.width()
    assert label.width() < gestartet.width(), "zweite Leiste ueber die Fensterbreite"


def test_ohne_serioese_prozentzahl_laeuft_der_balken_unbestimmt(bereich):
    """Regel 1.7: lieber unbestimmt als eine erfundene Zahl."""
    bereich.start("Datei lesen", percent=None)

    assert bereich.bar.minimum() == 0 and bereich.bar.maximum() == 0
    assert bereich.status_text() == "Datei lesen"
    assert "%" not in bereich.status_text()

    bereich.set_percent(40)
    assert bereich.bar.maximum() == 100
    assert bereich.status_text().endswith("40 %")


@pytest.mark.parametrize("sprache", ["de", "en", "fr"])
def test_statuszeile_ist_in_allen_drei_sprachen_uebersetzbar(sprache):
    werte = json.loads((LOCALES / f"{sprache}.json").read_text(encoding="utf-8"))
    block = werte["import_progress"]
    assert set(block) >= {"cancel_tip", "status_percent", "status_items"}
    assert "{activity}" in block["status_percent"]
    assert block["status_percent"].rstrip().endswith("{percent} %")
    for platzhalter in ("{activity}", "{current}", "{total}", "{percent}"):
        assert platzhalter in block["status_items"]


# ── Inaktiv ─────────────────────────────────────────────────────────────────


def test_inaktiver_bereich_ist_ausgeblendet_und_kostet_keine_hoehe(bereich, v4_app):
    layout = bereich.parentWidget().layout()

    assert bereich.is_active() is False
    assert bereich.isVisible() is False
    assert layout.sizeHint().height() == 0, "ausgeblendet, aber Hoehe reserviert"

    bereich.start(TAETIGKEIT)
    v4_app.processEvents()
    aktiv = layout.sizeHint().height()
    assert aktiv > 0

    bereich.stop()
    v4_app.processEvents()
    assert bereich.isVisible() is False
    assert bereich.status_text() == ""
    assert layout.sizeHint().height() == 0


def test_dialog_startet_mit_ausgeblendetem_fortschrittsbereich(dialog_mit_bereich):
    dialog = dialog_mit_bereich
    assert dialog.progress_area.is_active() is False
    assert dialog.progress_area.isVisible() is False


# ── Tab-Reihenfolge ─────────────────────────────────────────────────────────


def _fokus_kette(dialog) -> list:
    kette = []
    knoten = dialog
    for _ in range(500):
        knoten = knoten.nextInFocusChain()
        if knoten is dialog:
            break
        kette.append(knoten)
    return kette


def test_abbrechen_liegt_in_der_tab_kette_zwischen_tabelle_und_hauptaktionen(
    dialog_mit_bereich, v4_app
):
    dialog = dialog_mit_bereich
    dialog.progress_area.start(TAETIGKEIT)
    v4_app.processEvents()

    kette = _fokus_kette(dialog)
    for widget in (dialog.table, dialog.progress_area.btn_cancel, dialog.btn_close):
        assert widget in kette, f"{widget.objectName()} fehlt in der Tab-Kette"

    assert (
        kette.index(dialog.table)
        < kette.index(dialog.progress_area.btn_cancel)
        < kette.index(dialog.btn_close)
        < kette.index(dialog.btn_import)
    )

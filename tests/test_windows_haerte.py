"""Windows-Haerte: Zusicherungen, die auf Fedora sonst niemand bemerkt.

Entwickelt wird diese App auf Fedora, benutzt wird sie auf Windows. Alles in
dieser Datei prueft Verhalten, das ausschliesslich unter Windows schiefgeht -
und zwar so, dass die Pruefung auf jeder Plattform aussagekraeftig ist:
Slug-Funktionen, Pfaderkennung und erzeugte Batch-Texte sind reine
Zeichenketten-Logik und brauchen kein Windows.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "installer" / "budgetmanager_setup.iss"


def _iss() -> str:
    return ISS.read_text(encoding="utf-8")


def test_installer_schlaegt_keinen_onedrive_ordner_vor() -> None:
    """Der Dokumente-Ordner liegt bei aktivem Microsoft-Konto in OneDrive.

    OneDrive haelt Sperren auf .db, -wal und -shm, synchronisiert die drei
    Dateien unabhaengig voneinander und legt bei Konflikt Kopien an. Das
    erzeugt "database is locked", "disk image is malformed" oder still einen
    alten -wal ueber einer neueren .db. LocalAppData wird nie synchronisiert.
    """
    iss = _iss()
    assert "{localappdata}\\BudgetManager" in iss
    assert "{userdocs}" not in iss


def test_bestandsinstallationen_behalten_ihren_datenordner() -> None:
    """Der neue Default darf nur bei einer Neuinstallation greifen.

    ``DATA_DIR`` von der Kommandozeile und der Marker der bestehenden
    Installation muessen im Quelltext vor dem Default stehen, sonst wuerde ein
    Update den Ordner unter den Fuessen des Nutzers wegziehen.
    """
    iss = _iss()
    beginn = iss.index("function InitialDataDir: String;")
    ende = iss.index("procedure InitializeWizard;", beginn)
    block = iss[beginn:ende]

    pos_param = block.index("ParamDataDir <> ''")
    pos_previous = block.index("PreviousDataDir <> ''")
    pos_default = block.index("{localappdata}")
    assert pos_param < pos_previous < pos_default


# ──────────────────────────────────────────────────────────────────────────
# K1b: OneDrive-Erkennung fuer die bereits ausgelieferten Installationen
# ──────────────────────────────────────────────────────────────────────────
# Alle Faelle laufen mit windows=True und einer gestellten Umgebung. Die
# Erkennung ist reine Zeichenkettenlogik, deshalb ist die Aussage dieser Tests
# auf Fedora dieselbe wie auf Windows.
WIN_ENV = {
    "OneDrive": r"C:\Users\Anna\OneDrive",
    "OneDriveConsumer": r"C:\Users\Anna\OneDrive",
}


def test_datenordner_unter_onedrive_wird_erkannt() -> None:
    from model.app_paths import onedrive_root_for

    treffer = onedrive_root_for(
        r"C:\Users\Anna\OneDrive\Dokumente\BudgetManager",
        environ=WIN_ENV,
        windows=True,
    )
    assert treffer == r"C:\Users\Anna\OneDrive"


def test_der_onedrive_ordner_selbst_zaehlt_mit() -> None:
    from model.app_paths import onedrive_root_for

    assert (
        onedrive_root_for(r"C:\Users\Anna\OneDrive", environ=WIN_ENV, windows=True)
        is not None
    )
    assert (
        onedrive_root_for(r"C:\Users\Anna\OneDrive\\", environ=WIN_ENV, windows=True)
        is not None
    )


def test_gross_kleinschreibung_und_schraegstrich_sind_egal() -> None:
    """Windows-Pfade kommen mal mit / mal mit \\ und in beliebiger Schreibweise."""
    from model.app_paths import onedrive_root_for

    for kandidat in (
        r"c:\users\anna\onedrive\Dokumente\BudgetManager",
        "C:/Users/Anna/OneDrive/Dokumente/BudgetManager",
        r"C:\Users\Anna\OneDrive/Dokumente\BudgetManager",
    ):
        assert onedrive_root_for(kandidat, environ=WIN_ENV, windows=True), kandidat


def test_namensaehnliche_nachbarordner_sind_kein_treffer() -> None:
    """Ein Praefixvergleich ohne Trennzeichen wuerde hier falsch anschlagen."""
    from model.app_paths import onedrive_root_for

    assert (
        onedrive_root_for(
            r"C:\Users\Anna\OneDriveArchiv\BudgetManager",
            environ=WIN_ENV,
            windows=True,
        )
        is None
    )


def test_ordner_ausserhalb_von_onedrive_ist_kein_treffer() -> None:
    from model.app_paths import onedrive_root_for

    assert (
        onedrive_root_for(
            r"C:\Users\Anna\AppData\Local\BudgetManager",
            environ=WIN_ENV,
            windows=True,
        )
        is None
    )


def test_geschaeftskonto_wird_ueber_eigene_variable_erkannt() -> None:
    from model.app_paths import onedrive_root_for

    env = {"OneDriveCommercial": r"C:\Users\Anna\OneDrive - Contoso AG"}
    assert (
        onedrive_root_for(
            r"C:\Users\Anna\OneDrive - Contoso AG\Dokumente\BudgetManager",
            environ=env,
            windows=True,
        )
        == r"C:\Users\Anna\OneDrive - Contoso AG"
    )


def test_ohne_windows_gibt_es_kein_onedrive() -> None:
    """Auf Linux darf die Pruefung nie anschlagen, auch bei gesetzter Variable."""
    from model.app_paths import onedrive_root_for

    assert (
        onedrive_root_for(
            r"C:\Users\Anna\OneDrive\Dokumente\BudgetManager",
            environ=WIN_ENV,
            windows=False,
        )
        is None
    )


def test_leere_oder_fehlende_variablen_werden_ignoriert() -> None:
    from model.app_paths import onedrive_root_for

    for env in ({}, {"OneDrive": ""}, {"OneDrive": "   "}):
        assert (
            onedrive_root_for(r"C:\irgendwo\BudgetManager", environ=env, windows=True)
            is None
        )


class _FakeSettings:
    def __init__(self, **werte: object) -> None:
        self.werte = dict(werte)

    def get(self, key: str, default: object = None) -> object:
        return self.werte.get(key, default)

    def set(self, key: str, value: object) -> None:
        self.werte[key] = value


class _FakeFenster:
    """Nur die Teile des Hauptfensters, die der Hinweis wirklich anfasst."""

    def __init__(self, **werte: object) -> None:
        self.settings = _FakeSettings(**werte)
        self._is_closing = False
        self.gewechselt_nach: str | None = None

    def _handle_data_directory_change(self, neu: str) -> bool:
        self.gewechselt_nach = neu
        return True


def test_der_hinweis_kommt_nach_dem_wegklicken_nicht_wieder(monkeypatch) -> None:
    """Sonst waere er kein Hinweis, sondern eine Belaestigung bei jedem Start."""
    import model.app_paths as app_paths
    import views.main_window_onedrive as onedrive

    gerufen: list[str] = []
    monkeypatch.setattr(
        app_paths, "data_dir_onedrive_root", lambda: gerufen.append("x") or "C:\\OD"
    )

    fenster = _FakeFenster(onedrive_warning_shown=True)
    onedrive.schedule_warning(fenster, delay_ms=0)
    assert gerufen == [], "das Merkflag wurde nicht beachtet"


def test_ohne_onedrive_passiert_gar_nichts(monkeypatch) -> None:
    import model.app_paths as app_paths
    import views.main_window_onedrive as onedrive

    monkeypatch.setattr(app_paths, "data_dir_onedrive_root", lambda: None)
    fenster = _FakeFenster()
    onedrive.schedule_warning(fenster, delay_ms=0)
    assert fenster.settings.get("onedrive_warning_shown", False) is False


class _FakeBox:
    """Ersetzt QMessageBox: merkt sich die Knoepfe und waehlt einen davon."""

    letzte: _FakeBox | None = None

    def __init__(self, gewaehlt_index: int) -> None:
        self.gewaehlt_index = gewaehlt_index
        self.buttons: list[str] = []
        self.informativ = ""

    def setIcon(self, _icon: object) -> None: ...

    def setWindowTitle(self, _text: str) -> None: ...

    def setText(self, _text: str) -> None: ...

    def setInformativeText(self, text: str) -> None:
        self.informativ = text

    def addButton(self, label: str, _rolle: object) -> str:
        self.buttons.append(label)
        return label

    def exec(self) -> None: ...

    def clickedButton(self) -> str:
        return self.buttons[self.gewaehlt_index]


def _stelle_dialog(monkeypatch, gewaehlt_index: int) -> _FakeBox:
    import model.app_paths as app_paths
    import views.main_window_onedrive as onedrive

    box = _FakeBox(gewaehlt_index)

    class _Fabrik:
        Warning = object()
        AcceptRole = object()
        RejectRole = object()

        def __new__(cls, _parent: object) -> _FakeBox:  # type: ignore[misc]
            return box

    monkeypatch.setattr(onedrive, "QMessageBox", _Fabrik)
    monkeypatch.setattr(app_paths, "data_dir", lambda: Path(r"C:/OD/Dokumente/BM"))
    monkeypatch.setattr(
        app_paths, "recommended_local_data_dir", lambda: Path(r"C:/Local/BudgetManager")
    )
    return box


def test_ein_abgelehnter_wechsel_setzt_das_merkflag_trotzdem(monkeypatch) -> None:
    import views.main_window_onedrive as onedrive

    _stelle_dialog(monkeypatch, gewaehlt_index=1)
    fenster = _FakeFenster()
    onedrive.show_warning_dialog(fenster, r"C:\OD")

    assert fenster.settings.get("onedrive_warning_shown") is True
    assert fenster.gewechselt_nach is None


def test_der_wechsel_laeuft_ueber_die_bestehende_datenuebernahme(monkeypatch) -> None:
    """Kein zweiter Kopierpfad: derselbe Weg wie im Einstellungsdialog."""
    import views.main_window_onedrive as onedrive

    box = _stelle_dialog(monkeypatch, gewaehlt_index=0)
    fenster = _FakeFenster()
    onedrive.show_warning_dialog(fenster, r"C:\OD")

    assert fenster.gewechselt_nach == str(Path(r"C:/Local/BudgetManager"))
    assert r"C:\OD" in box.informativ
    assert len(box.buttons) == 2


def test_der_hinweis_bietet_alle_platzhalter_in_allen_sprachen() -> None:
    """Fehlt ein Platzhalter, zeigt der Dialog eine unvollstaendige Warnung."""
    import json

    for lang in ("de", "en", "fr"):
        daten = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        block = daten["onedrive"]
        assert set(block) == {"title", "text", "info", "move_now", "keep"}, lang
        for platzhalter in ("{folder}", "{onedrive}", "{target}"):
            assert platzhalter in block["info"], (lang, platzhalter)

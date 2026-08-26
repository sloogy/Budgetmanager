"""Windows-Haerte: Zusicherungen, die auf Fedora sonst niemand bemerkt.

Entwickelt wird diese App auf Fedora, benutzt wird sie auf Windows. Alles in
dieser Datei prueft Verhalten, das ausschliesslich unter Windows schiefgeht -
und zwar so, dass die Pruefung auf jeder Plattform aussagekraeftig ist:
Slug-Funktionen, Pfaderkennung und erzeugte Batch-Texte sind reine
Zeichenketten-Logik und brauchen kein Windows.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import verbindung_merken

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


# ──────────────────────────────────────────────────────────────────────────
# M5: DPI-Einstellungen duerfen nicht an der Startdatei haengen
# ──────────────────────────────────────────────────────────────────────────
# tools/build_release_assets.py setzt die drei Variablen in start-windows.cmd.
# Drei Startwege gehen daran vorbei: Doppelklick auf die EXE (die erzeugte
# README nennt ihn ausdruecklich als gleichwertig), die Startmenue-Verknuepfung
# der Installer-Installation und der Neustart durch den Updater. Nur weil der
# Code sie selbst setzt, sind alle vier Wege gleich - diese Tests halten das
# fest.
DPI_VARIABLEN = {
    "QT_ENABLE_HIGHDPI_SCALING": "1",
    "QT_AUTO_SCREEN_SCALE_FACTOR": "1",
    "QT_SCALE_FACTOR_ROUNDING_POLICY": "PassThrough",
}


def test_die_dpi_variablen_werden_im_code_gesetzt(monkeypatch) -> None:
    import os

    from utils.ui_scaling import configure_qt_scaling_environment

    for name in DPI_VARIABLEN:
        monkeypatch.delenv(name, raising=False)

    configure_qt_scaling_environment()

    for name, wert in DPI_VARIABLEN.items():
        assert os.environ.get(name) == wert, name


def test_eine_vorgabe_des_nutzers_bleibt_stehen(monkeypatch) -> None:
    """setdefault, nicht ueberschreiben - wie beim Wayland-Workaround."""
    import os

    from utils.ui_scaling import configure_qt_scaling_environment

    monkeypatch.setenv("QT_SCALE_FACTOR_ROUNDING_POLICY", "Round")
    configure_qt_scaling_environment()
    assert os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] == "Round"


def test_die_dpi_vorbereitung_laeuft_vor_der_qapplication() -> None:
    """Danach gesetzt haetten die Variablen keine Wirkung mehr."""
    quelle = (ROOT / "main.py").read_text(encoding="utf-8")
    vorbereitung = quelle.index("configure_qt_scaling_environment()")
    erzeugung = quelle.index("app = QApplication(sys.argv)")
    assert vorbereitung < erzeugung


# ──────────────────────────────────────────────────────────────────────────
# M3 + M4: reservierte Windows-Geraetenamen in Dateinamen
# ──────────────────────────────────────────────────────────────────────────
# Auf Linux sind con, nul, aux und prn gewoehnliche Dateien. Ein Test, der die
# Datei wirklich anlegt, waere hier deshalb immer gruen - geprueft wird die
# Namensbildung.
GERAETENAMEN = ["con", "prn", "aux", "nul", "com1", "com9", "lpt1", "lpt9"]


def test_kontodateien_treffen_keinen_geraetenamen() -> None:
    """Ein Konto namens Con ergab con.enc - fuer Windows das Konsolengeraet, keine Datei."""
    from model.user_model import _make_slug

    for name in GERAETENAMEN:
        for schreibweise in (name, name.upper(), name.capitalize()):
            slug = _make_slug(schreibweise)
            assert slug == name + "_", (schreibweise, slug)


def test_themedateien_treffen_keinen_geraetenamen() -> None:
    """Ein Theme namens Nul ergab nul.json - Schreiben meldet Erfolg, gespeichert wird nichts."""
    from theme_manager import _slugify

    for name in GERAETENAMEN:
        for schreibweise in (name, name.upper(), name.capitalize()):
            slug = _slugify(schreibweise)
            assert slug == name + "_", (schreibweise, slug)


def test_harmlose_namen_bleiben_unveraendert() -> None:
    """Die Entschaerfung darf nur die abgeschlossene Liste treffen."""
    from model.user_model import _make_slug
    from theme_manager import _slugify

    for name in ("anna", "console", "com", "com10", "lpt0", "nulll", "auxiliar"):
        assert _make_slug(name) == name, name
        assert _slugify(name) == name, name


def test_der_helfer_haengt_genau_einen_unterstrich_an() -> None:
    from utils.safe_filenames import RESERVIERTE_GERAETENAMEN, entschaerfe_geraetenamen

    assert len(RESERVIERTE_GERAETENAMEN) == 22
    assert entschaerfe_geraetenamen("CON") == "CON_"
    assert entschaerfe_geraetenamen("con_") == "con_"
    assert entschaerfe_geraetenamen("") == ""


# ──────────────────────────────────────────────────────────────────────────
# H3: kein Gate gegen open() ohne encoding=, kein UTF-8 im gebauten Stand
# ──────────────────────────────────────────────────────────────────────────
def test_das_encoding_gate_ist_scharf() -> None:
    """Der Bestand war konform - aber aus Disziplin, nicht durch Mechanismus.

    Ohne explizites encoding= waehlt Python auf Windows die ANSI-Codepage.
    Auf dem Fedora-Entwicklungsrechner faellt das nie auf, weil dort UTF-8
    die Locale-Vorgabe ist.
    """
    ruff = (ROOT / "ruff.toml").read_text(encoding="utf-8")
    assert '"PLW1514"' in ruff
    # PLW1514 steht bei ruff in der Vorschau und gilt sonst nicht.
    assert "preview = true" in ruff
    # Ohne diese Zeile kaemen die Vorschaufassungen aller uebrigen
    # Regelgruppen mit und koennten den Prueflauf unangekuendigt aendern.
    assert "explicit-preview-rules = true" in ruff


def test_der_gebaute_stand_laeuft_im_utf8_modus() -> None:
    """PYTHONUTF8 stand nur in den CI-Env-Bloecken, nie beim Nutzer.

    Die drei Startwege unter Windows (Doppelklick auf die EXE,
    Startmenue-Verknuepfung, Neustart durch den Updater) setzen keine
    Umgebungsvariablen. Deshalb als Interpreter-Option im Build.
    """
    spec = (ROOT / "BudgetManager.spec").read_text(encoding="utf-8")
    assert '("X utf8=1", None, "OPTION")' in spec
    assert "runtime_options," in spec, "die Optionsliste erreicht EXE() nicht"


def test_der_konsolen_logger_kodiert_utf8(monkeypatch) -> None:
    """Sonst wird jede Logzeile mit Umlaut zu "--- Logging error ---".

    Der StreamHandler erbt die Kodierung von sys.stderr - auf einer
    Windows-Konsole cp850/cp1252. Der Datei-Handler daneben hat seit jeher
    encoding="utf-8".
    """
    import io
    import logging
    import sys

    class _Konsole(io.StringIO):
        def __init__(self) -> None:
            super().__init__()
            self.kodierung: tuple[str, str] | None = None

        def reconfigure(self, *, encoding: str, errors: str) -> None:  # type: ignore[override]
            self.kodierung = (encoding, errors)

    konsole = _Konsole()
    monkeypatch.setattr(sys, "stderr", konsole)

    wurzel = logging.getLogger()
    alte = list(wurzel.handlers)
    for h in alte:
        wurzel.removeHandler(h)
    try:
        from model.logging_config import setup_logging

        setup_logging()
    finally:
        for h in list(wurzel.handlers):
            wurzel.removeHandler(h)
        for h in alte:
            wurzel.addHandler(h)

    assert konsole.kodierung == ("utf-8", "replace")


def test_es_gibt_nur_eine_fassung_der_konsolenumstellung() -> None:
    """Der Updater darf im Startpfad des Logging nicht mitgezogen werden.

    updater/common.py importiert requests und packaging auf Modulebene. Wuerde
    setup_logging von dort importieren, haenge beides an jeder
    Logging-Einrichtung.
    """
    logging_config = (ROOT / "model" / "logging_config.py").read_text(encoding="utf-8")
    assert "from utils.console_encoding import enable_utf8_console" in logging_config
    assert "from updater" not in logging_config
    assert "import updater" not in logging_config

    common = (ROOT / "updater" / "common.py").read_text(encoding="utf-8")
    assert "from utils.console_encoding import enable_utf8_console" in common


def test_die_app_reicht_utf8_an_ihre_kindprozesse_weiter() -> None:
    """Der Updater laeuft als eigener Prozess und gibt Emojis aus."""
    quelle = (ROOT / "main.py").read_text(encoding="utf-8")
    beginn = quelle.index("def _configure_utf8_runtime")
    ende = quelle.index("def _setup_emoji_fonts", beginn)
    block = quelle[beginn:ende]
    assert 'os.environ.setdefault("PYTHONUTF8", "1")' in block
    assert 'os.environ.setdefault("PYTHONIOENCODING", "utf-8")' in block
    assert "enable_utf8_console()" in block
    # Sehr frueh: vor jedem Kindprozess und vor der ersten Ausgabe.
    assert quelle.index("_configure_utf8_runtime()", ende) < quelle.index(
        "_install_crash_diagnostics()", ende
    )


# ──────────────────────────────────────────────────────────────────────────
# H1 + M1: Update-Semantik und Quoting im portablen Batch-Helfer
# ──────────────────────────────────────────────────────────────────────────
def _portabler_helfer_batch(
    dst: str = r"C:/Programme/BudgetManager",
) -> str:
    """Der erzeugte Batch-Text - reine Zeichenkette, kein Windows noetig."""
    from updater.apply_update import _build_windows_helper_batch

    return _build_windows_helper_batch(
        src_root=Path(r"C:/staging/BudgetManager"),
        dst_dir=Path(dst),
        wait_exe="BudgetManager.exe",
        launch_exe="BudgetManager.exe",
        log_path=Path(dst) / "updates" / "update_apply.log",
    )


def test_prozentzeichen_im_pfad_wird_maskiert() -> None:
    """cmd.exe las C:\\Tools\\100%Backup als Variablenreferenz.

    %SRC% zeigte danach ins Leere - und das del /f /q im Kopierschritt haette
    ein falsches Ziel treffen koennen.
    """
    batch = _portabler_helfer_batch(r"C:/Tools/100%Backup/BudgetManager")
    zeile = next(z for z in batch.splitlines() if z.startswith('set "DST='))
    assert "100%%Backup" in zeile
    assert "100%Backup" not in zeile.replace("100%%Backup", "")


def test_sonderzeichen_im_pfad_werden_maskiert() -> None:
    """Die Installer-Variante quotet seit jeher, der portable Helfer nicht."""
    batch = _portabler_helfer_batch(r"C:/A&B/Budget<Manager>")
    zeile = next(z for z in batch.splitlines() if z.startswith('set "DST='))
    assert "^&" in zeile and "^<" in zeile and "^>" in zeile


def test_alle_vier_werte_laufen_durch_dasselbe_escaping() -> None:
    """Vorher standen Log-, Quell-, Ziel- und EXE-Pfad roh im Template."""
    quelle = (ROOT / "updater" / "apply_update.py").read_text(encoding="utf-8")
    beginn = quelle.index("def _build_windows_helper_batch")
    ende = quelle.index("    template = r", beginn)
    block = quelle[beginn:ende]
    for name in ("src", "dst", "exe", "launch", "launch_path", "log"):
        assert f"{name} = _windows_cmd_quote(" in block, name


def test_das_update_raeumt_alte_dateien_weg() -> None:
    """Ohne /PURGE blieb alter Inhalt in _internal\\ liegen.

    Nach zwei, drei Updates stand dort ein Mischbestand aus alten und neuen
    Qt-DLLs - Startabbruch ohne verwertbare Meldung. Der Linux-Pfad derselben
    Datei ersetzt den Baum dagegen sauber per os.replace mit Rollback.
    """
    zeile = next(
        z for z in _portabler_helfer_batch().splitlines() if z.startswith("robocopy ")
    )
    assert "/PURGE" in zeile


def test_der_loeschlauf_verschont_daten_und_installer_marker() -> None:
    """Ein falsch gesetztes /PURGE loescht Nutzerdaten.

    /XD und /XF gelten auch fuer den Loeschlauf. data und updates waren schon
    ausgeschlossen; installation.json - der Marker, ueber den die App ihren
    Datenordner findet - liegt im Programmordner und ist in keinem
    Portable-Staging enthalten, wuerde also ohne /XF geloescht.
    """
    zeile = next(
        z for z in _portabler_helfer_batch().splitlines() if z.startswith("robocopy ")
    )
    ausschluss = zeile.split("/PURGE", 1)[1]
    for name in ("data", "updates", "installation.json"):
        assert name in ausschluss, name
    assert "/XD" in ausschluss
    assert "/XF" in ausschluss


# ──────────────────────────────────────────────────────────────────────────
# K2: Backup und Datenuebernahme ignorierten die WAL-Datei
# ──────────────────────────────────────────────────────────────────────────
def _db_mit_ungeschriebenem_wal(pfad: Path):
    """Legt eine WAL-DB an, deren letzte Buchung nur im -wal steht.

    Genau diese Lage hat die App waehrend eines Backups: Connection offen,
    Transaktion committet, WAL noch nicht ausgecheckpointet.
    """
    from model.database import open_db

    conn = open_db(str(pfad))
    conn.execute("CREATE TABLE buchung (id INTEGER PRIMARY KEY, text TEXT)")
    conn.execute("INSERT INTO buchung (text) VALUES ('alt')")
    conn.commit()
    from model.database import checkpoint_wal

    checkpoint_wal(conn)
    conn.execute("INSERT INTO buchung (text) VALUES ('zuletzt gebucht')")
    conn.commit()
    # Die Verbindung bleibt absichtlich offen - genau das ist die nachgestellte
    # Lage. Geschlossen wird sie am Testende, sonst haelt sie unter Windows das
    # Aufraeumen von tmp_path auf.
    return verbindung_merken(conn)


def test_die_letzte_buchung_steht_wirklich_nur_im_wal(tmp_path: Path) -> None:
    """Vorbedingung des naechsten Tests - sonst wuerde der nichts beweisen."""
    import sqlite3

    db = tmp_path / "budgetmanager.db"
    conn = _db_mit_ungeschriebenem_wal(db)
    try:
        assert (tmp_path / "budgetmanager.db-wal").exists()
        roh = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
        try:
            texte = {z[0] for z in roh.execute("SELECT text FROM buchung")}
        finally:
            roh.close()
        assert "zuletzt gebucht" not in texte
    finally:
        conn.close()


def test_das_backup_enthaelt_die_letzte_buchung(tmp_path: Path) -> None:
    """Vorher landete ein veralteter Stand im Bundle - mit passender Pruefsumme.

    Der SHA-256 im Manifest wird ueber genau die Datei gebildet, die auch
    eingepackt wird. War die veraltet, war das Manifest dazu konsistent: weder
    das Erstellen noch verify_bundle konnte etwas bemerken.
    """
    import sqlite3
    import zipfile

    from model.restore_bundle import create_bundle

    db = tmp_path / "budgetmanager.db"
    conn = _db_mit_ungeschriebenem_wal(db)
    try:
        bundle = create_bundle(
            source_db=db,
            out_path=tmp_path / "sicherung.bmr",
            app="BudgetManager",
            app_version="0.0.0-test",
        )
    finally:
        conn.close()

    entpackt = tmp_path / "aus_bundle.db"
    with zipfile.ZipFile(bundle) as zf:
        entpackt.write_bytes(zf.read("database.db"))

    geprueft = sqlite3.connect(str(entpackt))
    try:
        texte = {z[0] for z in geprueft.execute("SELECT text FROM buchung")}
    finally:
        geprueft.close()
    assert "zuletzt gebucht" in texte


def test_die_momentaufnahme_bleibt_nicht_liegen(tmp_path: Path) -> None:
    """Sie enthaelt dieselben Daten wie die DB und darf nicht ueberdauern."""
    from model.restore_bundle import create_bundle

    db = tmp_path / "budgetmanager.db"
    conn = _db_mit_ungeschriebenem_wal(db)
    try:
        create_bundle(
            source_db=db,
            out_path=tmp_path / "sicherung.bmr",
            app="BudgetManager",
            app_version="0.0.0-test",
        )
    finally:
        conn.close()

    assert not list(tmp_path.glob("*.snapshot_tmp"))


def _verbindung_ist_offen(conn) -> bool:
    import sqlite3

    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False  # "Cannot operate on a closed database"
    except sqlite3.Error:
        return True  # offen, aber die Datei ist keine Datenbank
    return True


def test_eine_quelle_ohne_datenbank_faellt_auf_die_dateikopie_zurueck(
    tmp_path: Path, monkeypatch
) -> None:
    """Nicht jede .db ist eine SQLite-Datei - und Windows sperrt offene Dateien.

    Zwei Zusicherungen in einem Durchlauf, weil beide an derselben Stelle
    haengen: Eine Quelle, die ``Connection.backup()`` nicht lesen kann, darf
    nicht durchschlagen, sondern muss auf die rohe Dateikopie zurueckfallen
    (``None``). Und die Zwischendatei darf erst geloescht werden, wenn beide
    Verbindungen zu sind - unter Windows scheitert das Loeschen sonst mit
    WinError 32. Auf Linux faellt die Reihenfolge nie auf, dort verschwindet
    der Verzeichniseintrag auch bei offenem Handle. Geprueft wird deshalb die
    Reihenfolge selbst.
    """
    import sqlite3

    from model import restore_bundle

    erzeugte: list[sqlite3.Connection] = []
    echtes_connect = sqlite3.connect

    def merkendes_connect(*args, **kwargs):
        conn = echtes_connect(*args, **kwargs)
        erzeugte.append(conn)
        return conn

    offen_beim_loeschen: list[int] = []
    echtes_unlink = Path.unlink

    def pruefendes_unlink(self: Path, *args, **kwargs):
        if self.name.endswith(".snapshot_tmp"):
            offen_beim_loeschen.append(
                sum(1 for conn in erzeugte if _verbindung_ist_offen(conn))
            )
        return echtes_unlink(self, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", merkendes_connect)
    monkeypatch.setattr(Path, "unlink", pruefendes_unlink)

    keine_datenbank = tmp_path / "altbestand.db"
    keine_datenbank.write_bytes(b"\0" * 4096)

    assert restore_bundle._wal_consistent_snapshot(keine_datenbank) is None
    assert offen_beim_loeschen, "die Zwischendatei wurde nie aufgeraeumt"
    assert all(anzahl == 0 for anzahl in offen_beim_loeschen)
    assert not list(tmp_path.glob("*.snapshot_tmp"))
    assert keine_datenbank.read_bytes() == b"\0" * 4096


def test_checkpoint_schreibt_das_wal_in_die_datei(tmp_path: Path) -> None:
    """Der Weg fuer die Datenuebernahme: die kopiert Dateien, kein Bundle."""
    import sqlite3

    from model.database import checkpoint_wal

    db = tmp_path / "budgetmanager.db"
    conn = _db_mit_ungeschriebenem_wal(db)
    try:
        assert checkpoint_wal(conn) is True
        roh = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
        try:
            texte = {z[0] for z in roh.execute("SELECT text FROM buchung")}
        finally:
            roh.close()
        assert "zuletzt gebucht" in texte
    finally:
        conn.close()


def test_die_datenuebernahme_checkpointet_vorher() -> None:
    """Die Allowlist in data_location nimmt -wal bewusst nicht mit.

    Ohne Checkpoint kaeme im neuen Ordner ein aelterer Stand an - und weil der
    alte Ordner unangetastet bleibt, faellt das erst Tage spaeter auf.
    """
    quelle = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    beginn = quelle.index("def _handle_data_directory_change")
    ende = quelle.index("migrate_data_dir(old_eff, new_eff", beginn)
    assert "checkpoint_wal(conn)" in quelle[beginn:ende]


# ──────────────────────────────────────────────────────────────────────────
# N2 bis N6: Kleinigkeiten mit Windows-Bezug
# ──────────────────────────────────────────────────────────────────────────
def test_backups_werden_unabhaengig_von_der_schreibweise_gefunden(
    tmp_path: Path,
) -> None:
    """Windows-Dateisysteme unterscheiden keine Schreibweise, der Filter tat es."""
    from model.database_management_model import DatabaseManagementModel

    backups = tmp_path / "backups"
    backups.mkdir()
    for name in ("klein.bmr", "GROSS.BMR", "Gemischt.Bmr", "kein_backup.txt"):
        (backups / name).write_bytes(b"x")

    modell = DatabaseManagementModel(str(tmp_path / "budgetmanager.db"))
    gefunden = {eintrag["filename"] for eintrag in modell.get_available_backups()}
    assert gefunden == {"klein.bmr", "GROSS.BMR", "Gemischt.Bmr"}


def test_sonderzeichen_im_backup_pfad_brechen_die_uri_nicht(tmp_path: Path) -> None:
    """#, ? und % aendern die Bedeutung einer URI, wenn sie roh hineingehen.

    Geprueft wird das Verhalten, nicht die verwendete Funktion: Die URI muss
    prozentkodiert sein, den Laufwerksbuchstaben in der Form ``file:///C:/``
    tragen und schreibgeschuetzt oeffnen. Womit sie gebaut wird, ist Sache der
    Umsetzung.
    """
    import os
    import sqlite3
    from pathlib import PureWindowsPath

    from utils.sqlite_uri import read_only_uri

    # Der rohe Zusammenbau aus as_posix() darf nirgends zurueckkehren: Er
    # laesst #, ? und % ungeschuetzt und verliert unter Windows das ///.
    for modul in ("backup_restore_dialog", "startup_wizard"):
        quelle = (ROOT / "views" / f"{modul}.py").read_text(encoding="utf-8")
        assert "read_only_uri(" in quelle
        assert "as_posix()}?mode=ro" not in quelle

    # Windows-Teil, auf jeder Plattform pruefbar: PureWindowsPath macht
    # dieselbe Umsetzung, die Path dort machen wuerde.
    assert (
        PureWindowsPath(r"C:\Sicherungen\Stand#1 100%.db").as_uri()
        == "file:///C:/Sicherungen/Stand%231%20100%25.db"
    )
    # ... und die Option haengt hinter der fertigen URI, nicht mittendrin.
    einfach = tmp_path / "einfach.db"
    assert read_only_uri(einfach) == einfach.as_uri() + "?mode=ro"

    # ? ist unter Windows kein zulaessiges Zeichen in einem Dateinamen; dort
    # laesst sich der Fall gar nicht herstellen.
    namen = ["a#b.db", "100%e.db"] + ([] if os.name == "nt" else ["c?d.db"])
    for name in namen:
        pfad = tmp_path / name
        sqlite3.connect(str(pfad)).close()
        conn = sqlite3.connect(read_only_uri(pfad), uri=True)
        try:
            assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            try:
                conn.execute("CREATE TABLE probe (x)")
            except sqlite3.OperationalError:
                pass
            else:  # pragma: no cover - mode=ro haette gegriffen
                raise AssertionError(f"mode=ro nicht wirksam fuer {name}")
        finally:
            conn.close()


def test_das_installer_update_startet_keine_fremde_exe() -> None:
    """Der Rueckfall war unerreichbar, aber scharf.

    Fand sich kein BudgetManager_Setup*.exe, wurde die alphabetisch erste
    beliebige .exe mit /SILENT /SUPPRESSMSGBOXES gestartet - ohne Rueckfrage
    und ohne sichtbares Fenster.
    """
    quelle = (ROOT / "updater" / "apply_update.py").read_text(encoding="utf-8")
    beginn = quelle.index("def _apply_via_windows_installer")
    ende = quelle.index("\ndef ", beginn + 1)
    block = quelle[beginn:ende]
    assert 'rglob("*.exe")' not in block
    assert 'rglob("BudgetManager_Setup*.exe")' in block


def test_csv_export_trennt_fuer_deutsches_excel_mit_semikolon(
    v4_app, v4_conn, tmp_path, monkeypatch
) -> None:
    """Mit Komma landet die Datei in deutschem Excel vollstaendig in Spalte A."""
    import views.export_dialog as export_dialog
    from views.export_dialog import ExportDialog

    monkeypatch.setattr(export_dialog, "get_language", lambda: "de")
    dialog = ExportDialog(v4_conn)
    try:
        assert dialog.chk_semicolon.isChecked() is True

        ziel = tmp_path / "export.csv"
        dialog._export_to_file(str(ziel))
        assert ";" in ziel.read_text(encoding="utf-8-sig")

        # Die Entscheidung bleibt beim Nutzer: Wer die Datei an ein
        # englischsprachiges Werkzeug weiterreicht, braucht das Komma.
        dialog.chk_semicolon.setChecked(False)
        dialog._export_to_file(str(ziel))
        assert ";" not in ziel.read_text(encoding="utf-8-sig")
    finally:
        dialog.deleteLater()


def test_csv_export_bleibt_englisch_beim_komma(v4_app, v4_conn, monkeypatch) -> None:
    import views.export_dialog as export_dialog
    from views.export_dialog import ExportDialog

    monkeypatch.setattr(export_dialog, "get_language", lambda: "en")
    dialog = ExportDialog(v4_conn)
    try:
        assert dialog.chk_semicolon.isChecked() is False
    finally:
        dialog.deleteLater()


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

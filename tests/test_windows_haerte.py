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

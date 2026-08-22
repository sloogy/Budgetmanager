"""Der BudgetManager meldet dem Host, was gerade schieflaeuft.

Bis Loop 47 zeigte das LifePlanner-Dashboard nur, ob die Module laufen und
wie viele Zeilen in den Brueckendateien stehen. Ein ueberzogenes Budget sah
nur, wer den BudgetManager oeffnete - obwohl der Host das Fenster ist, das
ohnehin offen steht.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from model.lifeplanner_notices import (
    DRINGLICHKEITEN,
    HOECHSTZAHL,
    MANIFEST_SCHEMA,
    NOTICE_SCHEMA,
    Meldung,
    kennung,
    schreibe_meldungen,
)


def _meldung(nr: int = 1, dringlichkeit: str = "info") -> Meldung:
    return Meldung(
        kennung=kennung("probe", nr),
        dringlichkeit=dringlichkeit,
        ueberschrift=f"Probe {nr}",
        zusatz="Zusatz",
        bereich="test",
    )


def _lies(pfad) -> tuple[dict, list[dict]]:
    zeilen = [
        json.loads(z)
        for z in pfad.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    return zeilen[0], zeilen[1:]


def test_datei_beginnt_mit_einem_manifest(tmp_path) -> None:
    ziel = tmp_path / "notices.jsonl"
    schreibe_meldungen([_meldung()], ziel)
    kopf, eintraege = _lies(ziel)
    assert kopf["schema"] == MANIFEST_SCHEMA
    assert kopf["count"] == 1
    assert eintraege[0]["schema"] == NOTICE_SCHEMA


def test_schreiben_ersetzt_statt_anzuhaengen(tmp_path) -> None:
    """Die Datei ist eine Momentaufnahme.

    Wuerde angehaengt, bliebe eine behobene Warnung im Dashboard stehen,
    bis jemand aufraeumt - und niemand raeumt auf.
    """
    ziel = tmp_path / "notices.jsonl"
    schreibe_meldungen([_meldung(1), _meldung(2)], ziel)
    schreibe_meldungen([_meldung(3)], ziel)
    _, eintraege = _lies(ziel)
    assert [e["headline"] for e in eintraege] == ["Probe 3"]


def test_dringlichstes_steht_oben(tmp_path) -> None:
    ziel = tmp_path / "notices.jsonl"
    schreibe_meldungen(
        [
            _meldung(1, "info"),
            _meldung(2, "kritisch"),
            _meldung(3, "warnung"),
        ],
        ziel,
    )
    _, eintraege = _lies(ziel)
    assert [e["urgency"] for e in eintraege] == ["kritisch", "warnung", "info"]


def test_die_zahl_der_meldungen_ist_gedeckelt(tmp_path) -> None:
    """Ein Modul darf das Dashboard nicht fluten."""
    ziel = tmp_path / "notices.jsonl"
    geschrieben = schreibe_meldungen(
        [_meldung(nr, "warnung") for nr in range(HOECHSTZAHL + 5)], ziel
    )
    _, eintraege = _lies(ziel)
    assert geschrieben == len(eintraege) == HOECHSTZAHL + 1
    assert eintraege[-1]["area"] == "sammel"
    assert "5 weitere" in eintraege[-1]["headline"]


def test_kennung_ist_stabil_und_kein_klartext() -> None:
    """Dieselbe Sache bleibt dieselbe Meldung - ohne den Namen zu verraten.

    Die Datei liegt im Brueckenordner und ist fuer jedes Modul lesbar. Eine
    Kategorie kann "Therapie" heissen.
    """
    a = kennung("budget", 2026, 8, "Ausgaben", "Therapie")
    b = kennung("budget", 2026, 8, "Ausgaben", "Therapie")
    c = kennung("budget", 2026, 8, "Ausgaben", "Miete")
    assert a == b != c
    assert "Therapie" not in a


def test_eine_meldung_ohne_ueberschrift_wird_abgelehnt() -> None:
    with pytest.raises(ValueError):
        Meldung(kennung="x", dringlichkeit="info", ueberschrift="   ")


def test_unbekannte_dringlichkeit_wird_abgelehnt() -> None:
    with pytest.raises(ValueError):
        Meldung(kennung="x", dringlichkeit="dringend", ueberschrift="Probe")


def test_dringlichkeiten_sind_aufsteigend_geordnet() -> None:
    """Die Reihenfolge der Konstante ist die Sortierung - nicht Zufall."""
    assert DRINGLICHKEITEN == ("info", "warnung", "kritisch")


def _db_mit_sparziel(tmp_path, faellig_in_tagen: int, anteil: float):
    from model.database import open_db
    from model.migrations import migrate_all
    from model.savings_goals_model import SavingsGoalsModel

    pfad = str(tmp_path / "test.db")
    conn = open_db(pfad)
    migrate_all(conn, db_path=pfad, backup_dir=str(tmp_path / "migration_backups"))
    modell = SavingsGoalsModel(conn)
    frist = (date.today() + timedelta(days=faellig_in_tagen)).isoformat()
    modell.create(
        name="Wunschfüller",
        target_amount=1000.0,
        current_amount=1000.0 * anteil,
        deadline=frist,
    )
    return conn


def test_sparziel_kurz_vor_dem_termin_meldet_sich(tmp_path) -> None:
    from model.lifeplanner_notices import _sparziel_meldungen

    conn = _db_mit_sparziel(tmp_path, faellig_in_tagen=10, anteil=0.4)
    try:
        meldungen = _sparziel_meldungen(conn)
    finally:
        conn.close()
    assert len(meldungen) == 1
    assert "endet bald" in meldungen[0].ueberschrift
    assert meldungen[0].dringlichkeit == "info"


def test_sparziel_mit_abgelaufenem_termin_ist_eine_warnung(tmp_path) -> None:
    from model.lifeplanner_notices import _sparziel_meldungen

    conn = _db_mit_sparziel(tmp_path, faellig_in_tagen=-5, anteil=0.4)
    try:
        meldungen = _sparziel_meldungen(conn)
    finally:
        conn.close()
    assert len(meldungen) == 1
    assert meldungen[0].dringlichkeit == "warnung"


def test_sparziel_mit_fernem_termin_meldet_nichts(tmp_path) -> None:
    """Sonst steht ein Ziel ein Jahr lang im Dashboard, ohne dass es eilt."""
    from model.lifeplanner_notices import _sparziel_meldungen

    conn = _db_mit_sparziel(tmp_path, faellig_in_tagen=200, anteil=0.4)
    try:
        meldungen = _sparziel_meldungen(conn)
    finally:
        conn.close()
    assert meldungen == []


# ── Kontrakt: was hier geschrieben wird, muss der Host lesen können ────────


def test_geschriebene_datei_passt_zum_host_schema(tmp_path) -> None:
    """Die Feldnamen sind der Vertrag, nicht die Bequemlichkeit.

    Schreib- und Leseseite liegen in verschiedenen Repositories. Wer hier
    ``ueberschrift`` statt ``headline`` schreibt, merkt es erst, wenn das
    Dashboard leer bleibt - und das sieht aus wie "es ist nichts los".
    """
    ziel = tmp_path / "budgetmanager_notices.jsonl"
    schreibe_meldungen([_meldung(1, "kritisch")], ziel)
    kopf, eintraege = _lies(ziel)

    # Kopfzeile: der Host nimmt daraus den Absendernamen.
    assert kopf["schema"] == "lifeplanner.notice.manifest.v1"
    assert kopf["module"]
    assert kopf["module_version"]

    # Meldungszeile: genau die Felder, die lifeplanner_core/notices.py liest.
    (eintrag,) = eintraege
    assert set(eintrag) == {"schema", "id", "urgency", "headline", "detail", "area"}
    assert eintrag["schema"] == "lifeplanner.notice.v1"
    assert eintrag["urgency"] in ("info", "warnung", "kritisch")


def test_der_dateiname_passt_zum_suchmuster_des_hosts() -> None:
    """Der Host sucht ``*_notices.jsonl`` im Brückenordner."""
    from model.lifeplanner_notices import NOTICES_FILE

    assert NOTICES_FILE.endswith("_notices.jsonl")


def test_meldungen_tragen_keine_betraege(tmp_path) -> None:
    """Nur Ergebnisse, keine Rohdaten - so steht es im Modul-Host-Vertrag.

    Die Datei liegt im Brückenordner und ist für jedes Modul lesbar.
    """
    ziel = tmp_path / "notices.jsonl"
    schreibe_meldungen([_meldung(1, "kritisch")], ziel)
    inhalt = ziel.read_text(encoding="utf-8")
    for verboten in ("amount", "betrag", "saldo", "balance"):
        assert verboten not in inhalt.lower()

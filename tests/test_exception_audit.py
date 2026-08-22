"""Der Ausnahmen-Ratchet greift und wird nicht blind.

Bis Loop 21 suchte er per Textsuche in einer handgepflegten Positivliste von
Paketen. Das ging zweimal schief: im BudgetManager stand eine Datei mit 19
breiten Handlern ausserhalb der Liste, im LifePlanner ausgerechnet der
Update-Pfad. Beide waren nie geprueft worden. Seitdem wird alles geprueft,
was nicht ausdruecklich ausgenommen ist, und ueber den Syntaxbaum statt ueber
Zeilen.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
WERKZEUG = WURZEL / "tools" / "exception_audit.py"


def _laden():
    spec = importlib.util.spec_from_file_location("exception_audit", WERKZEUG)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def audit():
    return _laden()


def _pruefe(audit, tmp_path: Path, quelltext: str):
    """Laesst den Scanner ueber eine einzelne erfundene Datei laufen."""
    (tmp_path / "beispiel.py").write_text(quelltext, encoding="utf-8")
    original = audit.ROOT
    audit.ROOT = tmp_path
    try:
        return audit.scan()
    finally:
        audit.ROOT = original


def test_das_werkzeug_gibt_es(audit) -> None:
    assert WERKZEUG.is_file()


def test_der_bestand_liegt_innerhalb_der_grenzen(audit) -> None:
    """Das eigentliche Gate. Schlaegt fehl, sobald jemand nachlegt."""
    assert audit.main([]) == 0


def test_nacktes_except_wird_gefunden(audit, tmp_path: Path) -> None:
    ergebnis = _pruefe(
        audit,
        tmp_path,
        "try:\n    tu_was()\nexcept:\n    pass\n",
    )
    assert len(ergebnis.bare) == 1


def test_base_exception_wird_gefunden(audit, tmp_path: Path) -> None:
    """Die ausgeschriebene Form rutschte frueher durch."""
    ergebnis = _pruefe(
        audit,
        tmp_path,
        "try:\n    tu_was()\nexcept BaseException:\n    melde()\n",
    )
    assert len(ergebnis.base) == 1
    assert ergebnis.broad == 0


def test_base_exception_auch_im_tupel(audit, tmp_path: Path) -> None:
    ergebnis = _pruefe(
        audit,
        tmp_path,
        "try:\n    tu_was()\nexcept (OSError, BaseException):\n    melde()\n",
    )
    assert len(ergebnis.base) == 1


def test_stummer_schlucker_wird_erkannt(audit, tmp_path: Path) -> None:
    ergebnis = _pruefe(
        audit,
        tmp_path,
        "try:\n    tu_was()\nexcept Exception:\n    pass\n",
    )
    assert ergebnis.broad == 1
    assert len(ergebnis.silent) == 1


def test_nur_ein_docstring_ist_genauso_stumm(audit, tmp_path: Path) -> None:
    ergebnis = _pruefe(
        audit,
        tmp_path,
        'try:\n    tu_was()\nexcept Exception:\n    "darf ruhig scheitern"\n',
    )
    assert len(ergebnis.silent) == 1


def test_wer_protokolliert_gilt_nicht_als_stumm(audit, tmp_path: Path) -> None:
    ergebnis = _pruefe(
        audit,
        tmp_path,
        "try:\n    tu_was()\nexcept Exception as f:\n    log.warning('%s', f)\n",
    )
    assert ergebnis.broad == 1
    assert ergebnis.silent == []


def test_praezise_ausnahmen_zaehlen_nicht(audit, tmp_path: Path) -> None:
    ergebnis = _pruefe(
        audit,
        tmp_path,
        "try:\n    tu_was()\nexcept (OSError, ValueError):\n    pass\n",
    )
    assert ergebnis.broad == 0
    assert ergebnis.silent == []


def test_beispiele_in_docstrings_zaehlen_nicht_mit(audit, tmp_path: Path) -> None:
    """Die alte Textsuche zaehlte hier mit - der Syntaxbaum nicht."""
    ergebnis = _pruefe(
        audit,
        tmp_path,
        '"""So bitte nicht:\n\nexcept Exception:\n    pass\n"""\n',
    )
    assert ergebnis.broad == 0
    assert ergebnis.bare == []


def test_eine_neue_datei_wird_mitgeprueft(audit, tmp_path: Path) -> None:
    """Der Kern der Umstellung: keine Positivliste mehr.

    Frueher wurde nur geprueft, was in PACKAGES stand. Eine neu angelegte
    Datei daneben blieb ungeprueft - genau so entstanden die Luecken im
    BudgetManager und im LifePlanner.
    """
    (tmp_path / "brandneu.py").write_text(
        "try:\n    tu_was()\nexcept:\n    pass\n", encoding="utf-8"
    )
    original = audit.ROOT
    audit.ROOT = tmp_path
    try:
        ergebnis = audit.scan()
    finally:
        audit.ROOT = original
    assert len(ergebnis.bare) == 1


def test_tests_und_werkzeuge_bleiben_aussen_vor(audit, tmp_path: Path) -> None:
    for ordner in ("tests", "tools", "build", "__pycache__"):
        (tmp_path / ordner).mkdir()
        (tmp_path / ordner / "x.py").write_text(
            "try:\n    tu_was()\nexcept:\n    pass\n", encoding="utf-8"
        )
    original = audit.ROOT
    audit.ROOT = tmp_path
    try:
        ergebnis = audit.scan()
    finally:
        audit.ROOT = original
    assert ergebnis.bare == []


def test_grenzen_sind_scharf_gezogen(audit) -> None:
    """Ein Ratchet mit Luft darin misst nichts.

    Die Grenzen muessen dem gemessenen Bestand entsprechen, sonst kann
    jemand nachlegen, ohne dass das Gate anschlaegt.
    """
    ergebnis = audit.scan()
    assert audit.BARE_EXCEPT_LIMIT == 0
    assert audit.BASE_EXCEPTION_LIMIT == 0
    assert ergebnis.broad == audit.BROAD_EXCEPTION_LIMIT
    assert len(ergebnis.silent) == audit.SILENT_EXCEPT_LIMIT

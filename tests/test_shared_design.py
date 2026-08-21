"""Der gemeinsame Designkatalog.

Warum es diesen Test gibt: Die vier Programme lieferten jeweils eigene
Profildateien aus, und sie liefen auseinander - andere Anzahl, andere Rollen,
fuer dasselbe Design andere Namen. Sichtbar wurde das erst im Betrieb: Wer im
LifePlanner ein Design waehlte, das dieses Programm nicht selbst mitbrachte,
bekam dessen Hintergrund, aber die Akzent-, Karten- und Statusfarben des
eingebauten Standardprofils.

Dieser Test haelt den Katalog zusammen. Er prueft dieselben Regeln, die auch
``tools/design_sync.py build`` durchsetzt - schlaegt er an, ist eine Profildatei
von Hand geaendert worden, ohne den Katalog nachzuziehen.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_design_sync():
    path = ROOT / "tools" / "design_sync.py"
    if not path.is_file():
        pytest.skip("tools/design_sync.py fehlt")
    spec = importlib.util.spec_from_file_location("design_sync", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("design_sync", module)
    spec.loader.exec_module(module)
    return module


ds = _load_design_sync()

# Die 26 Designs, die alle vier Programme gemeinsam anbieten.
EXPECTED = {
    "Dracula - Dunkel", "Dunkel - Blau", "Dunkel - Grün",
    "Dunkel - OLED (Kontrastarm)", "Dunkel - Warm (Sepia)", "Gruvbox - Dunkel",
    "Gruvbox - Hell", "Hell - Grün", "Hell - Warm (Sepia)",
    "Kontrast - Schwarz/Weiß", "Mitternacht - Violett", "Modern Cyan (V2)",
    "Monokai - Dunkel", "Nord - Dunkel", "Ocean - Dunkel", "Pastell - Sanft",
    "Solarized - Dunkel", "Solarized - Hell", "Standard - Dunkel",
    "Standard - Hell", "V2 Dunkel – Graphite Cyan", "V2 Dunkel – Purple Night",
    "V2 Hell – Neon Cyan", "V2 Hell – Pastel Mint", "V2 Hell – Warm Sand",
    "Warm - Hell",
}


@pytest.fixture(scope="module")
def profiles() -> dict:
    directory = ds.local_profile_dir()
    assert directory is not None, "Profilverzeichnis nicht gefunden"
    found = ds.read_profiles(directory)
    assert found, f"keine Profile in {directory}"
    return found


def test_alle_designs_sind_da(profiles):
    """Fehlt ein Design, faellt das Modul beim Hostwechsel auf Standard zurueck."""
    assert set(profiles) == EXPECTED


def test_jedes_design_fuehrt_jede_rolle(profiles):
    """Eine fehlende Rolle wird nicht gemeldet, sie wird stillschweigend grau."""
    missing: list[str] = []
    for name, profile in sorted(profiles.items()):
        for role in ds.ALL_ROLES:
            if not ds.is_hex_color(profile.get(role)):
                missing.append(f"{name}/{role}")
    assert not missing, "Rollen fehlen:\n  " + "\n  ".join(missing)


def test_kontraste_und_helligkeit_stimmen(profiles):
    """Dieselbe Pruefung wie im Werkzeug - 4.5:1 fuer jede Schrift."""
    problems: list[str] = []
    for _, profile in sorted(profiles.items()):
        problems.extend(ds.audit(profile))
    assert not problems, "Designkatalog beanstandet:\n  " + "\n  ".join(problems)


def test_dateinamen_folgen_dem_namen(profiles):
    """Sonst liest ein Programm dieselbe Datei unter zwei Namen ein."""
    directory = ds.local_profile_dir()
    for name in profiles:
        expected = directory / f"{ds.slugify(name)}.json"
        assert expected.is_file(), f"{name}: erwartet {expected.name}"
    assert len(list(directory.glob("*.json"))) == len(profiles)


def test_schriftgroesse_ist_der_gemeinsame_bezugswert(profiles):
    """10 heisst in allen vier Programmen 'normal'."""
    for name, profile in sorted(profiles.items()):
        assert profile.get("schriftgroesse") == ds.DEFAULT_FONT_SIZE, name
